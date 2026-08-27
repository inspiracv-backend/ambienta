"""Los avisos de vencimiento: cuando, a quien, y una sola vez (epica #22).

Reemplaza a `obligations.create_deadline_notifications()`, que tenia tres
defectos medidos con sondas antes de escribir esto.

## 1. Duplicaba (#119)

Tres corridas seguidas sobre la misma obligacion y la misma ventana dejaban
**tres avisos**. El generador esta pensado para un cron diario: un reinicio, un
reintento o dos trabajadores, y la persona recibe el mismo correo repetido.

**El dano no es el ruido, es lo que el ruido provoca.** Un sistema que avisa de
mas se deja de leer, y entonces el aviso que si importaba pasa de largo. En este
dominio eso termina en una declaracion no presentada.

Ahora cada aviso lleva una `dedupe_key` con una restriccion de unicidad detras
(`db/17`). No es un `if` en Python: hay dos lugares que escriben en
`notifications`, y una restriccion protege tambien contra dos procesos a la vez,
que es justo el caso del cron con reintentos.

## 2. Las obligaciones sin responsable no avisaban a nadie (#123)

    if not obl.owner_user_id:
        continue

Medido en el seed: **3 de 8 obligaciones no tienen responsable**. Las que estan
mas expuestas —nadie se hizo cargo— eran exactamente las que no generaban
ningun aviso, en silencio.

Ahora escalan: sin responsable, el aviso va a los administradores de la empresa,
y **dice que va escalado y por que**. Un aviso que llega sin explicar por que le
llego a esa persona se archiva.

## 3. Las ventanas estaban escritas a mano (#120)

`days_before = [30, 15, 7, 1]` en el codigo, mientras `notification_rules`
—con `lead_minutes` por empresa— existe en el esquema desde el principio y
**tiene cero filas**: nada la leia.

El criterio ahora es: **la regla de la empresa si existe, el defecto si no**. Un
tenant nuevo funciona sin configurar nada, y uno que quiera otras ventanas las
declara sin tocar codigo.

Ojo: el codigo decia 30/15/7/1 y el requisito (#120) pide **15/7/3/1**. Se sigue
el requisito. Los 30 dias no estaban en ningun lado salvo en esa linea.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models.catalog import RetcSystem
from ..models.notifications import Notification, NotificationRule
from ..models.obligations import DeclarationTemplate, Obligation
from ..models.organization import User
from .declaracion import urgencia

#: Las ventanas por defecto, en dias antes del vencimiento (#120, RF-42).
#:
#: **Se usan cuando la empresa no declaro las suyas**, no como unica opcion. Un
#: tenant recien creado tiene que recibir avisos sin que nadie configure nada;
#: uno con otro ritmo de trabajo declara sus reglas y estas dejan de aplicar.
VENTANAS_POR_DEFECTO = (15, 7, 3, 1)

#: El evento al que corresponden estas reglas en `notification_rules`.
EVENTO = "obligacion_por_vencer"

#: Margen a cada lado del dia exacto.
#:
#: Doce horas y no cero: el cron corre a una hora fija y el vencimiento cae a
#: cualquier hora. Sin margen, un vencimiento a las 09:00 nunca cae exactamente
#: a N dias del momento en que corre el cron y **no se avisaria jamas**.
MARGEN = timedelta(hours=12)


@dataclass
class Resultado:
    """Que hizo la corrida. Lo que no se hizo tambien se cuenta."""

    creados: int = 0
    #: Ya existian: el cron corrio de nuevo y no repitio. **Es lo esperado**,
    #: no un error, y por eso se informa aparte de los creados.
    omitidos_por_repetidos: int = 0
    #: Obligaciones sin responsable cuyo aviso se escalo a los administradores.
    escalados: int = 0
    #: **Obligaciones que no avisaron a nadie porque no habia a quien.** Es el
    #: numero que hay que mirar: significa que la empresa no tiene ni
    #: responsable ni administrador activo.
    sin_destinatario: list[str] = field(default_factory=list)
    ventanas: tuple[int, ...] = ()


def ventanas_de(db: Session, tenant_id: UUID) -> tuple[int, ...]:
    """Los dias de anticipacion que usa esta empresa.

    Sale de `notification_rules.lead_minutes` si hay reglas activas para el
    evento; si no, del defecto. Se ordenan de mayor a menor —el aviso mas
    lejano primero— y se quitan repetidos: dos reglas con el mismo plazo son un
    error de configuracion, no una razon para avisar dos veces.
    """
    minutos = db.scalars(
        select(NotificationRule.lead_minutes).where(
            NotificationRule.tenant_id == tenant_id,
            NotificationRule.event_type == EVENTO,
            NotificationRule.active.is_(True),
            NotificationRule.deleted_at.is_(None),
        )
    ).all()

    if not minutos:
        return VENTANAS_POR_DEFECTO

    # `lead_minutes` puede ser negativo — el esquema lo documenta como "aviso
    # posterior al vencimiento". Eso es otro caso de uso y no se mezcla aca.
    dias = {m // 1440 for m in minutos if m > 0}
    return tuple(sorted(dias, reverse=True)) if dias else VENTANAS_POR_DEFECTO


def _destinatarios(db: Session, obligacion: Obligation) -> tuple[list[UUID], bool]:
    """A quien le llega. Devuelve `(destinatarios, fue_escalado)`.

    Con responsable, va solo a el. Sin responsable **escala a los
    administradores de la empresa** en vez de callarse: una obligacion sin
    dueno es mas urgente que una con dueno, no menos.
    """
    if obligacion.owner_user_id is not None:
        return [obligacion.owner_user_id], False

    admins = db.scalars(
        select(User.id).where(
            User.tenant_id == obligacion.tenant_id,
            User.user_type.in_(["tenant_admin", "internal"]),
            User.status == "active",
            User.deleted_at.is_(None),
        )
    ).all()
    return list(admins), True


def _plantilla_de(db: Session, obl: Obligation) -> DeclarationTemplate | None:
    """La plantilla Excel vigente del sistema ante el que declara esta obligacion.

    Devuelve `None` sin ruido en tres casos legitimos: la obligacion no declara
    sistema, el sistema no tiene plantilla cargada, o la que hay no esta
    vigente. **Hoy los tres son el caso normal**: `declaration_templates` tiene
    cero filas — el repositorio de plantillas (#116) es contenido oficial que
    todavia no se cargo, no codigo que falte.

    La vigencia se filtra por fecha y no solo por `active`: una plantilla
    marcada activa cuyo `valid_to` ya paso corresponde a una estructura que el
    portal dejo de aceptar, y adjuntarla haria que la empresa preparara su
    declaracion en un formato que le van a rechazar.
    """
    if obl.retc_system_id is None:
        return None

    hoy = date.today()
    return db.scalar(
        select(DeclarationTemplate)
        .join(RetcSystem, RetcSystem.code == DeclarationTemplate.system_code)
        .where(
            RetcSystem.id == obl.retc_system_id,
            DeclarationTemplate.active.is_(True),
            DeclarationTemplate.deleted_at.is_(None),
            or_(DeclarationTemplate.valid_from.is_(None), DeclarationTemplate.valid_from <= hoy),
            or_(DeclarationTemplate.valid_to.is_(None), DeclarationTemplate.valid_to >= hoy),
        )
        .order_by(DeclarationTemplate.valid_from.desc().nulls_last())
    )


def _clave(obligacion_id: UUID, dias: int) -> str:
    """La clave que impide el duplicado. Ver `db/17`."""
    return f"vencimiento:{obligacion_id}:{dias}"


def _destinatarios_ya_avisados(db: Session, tenant_id: UUID, clave: str) -> set:
    """Quienes ya recibieron este aviso.

    Se pregunta **por destinatario y no por clave a secas**: si un
    escalamiento se corta a la mitad —la base se cae entre dos administradores—
    la siguiente corrida tiene que completar los que faltan, no darlo por hecho
    porque uno ya lo tiene.
    """
    return set(
        db.scalars(
            select(Notification.recipient_user_id).where(
                Notification.tenant_id == tenant_id,
                Notification.dedupe_key == clave,
                Notification.deleted_at.is_(None),
            )
        ).all()
    )


def _cuerpo(obligacion: Obligation, dias: int, escalado: bool) -> tuple[str, str]:
    fecha = obligacion.due_at.strftime("%d/%m/%Y") if obligacion.due_at else "sin fecha"
    asunto = f"Vence en {dias} {'dia' if dias == 1 else 'dias'}: {obligacion.title}"

    cuerpo = (
        f"La declaracion '{obligacion.title}' (codigo {obligacion.code}) "
        f"vence el {fecha}."
    )
    if escalado:
        # **Se dice por que le llego.** Un aviso sin explicacion sobre algo que
        # la persona no reconoce como suyo se archiva sin leer.
        cuerpo += (
            "\n\nRecibes este aviso porque la declaracion no tiene un responsable "
            "asignado. Asignale uno para que los proximos le lleguen directamente."
        )
    return asunto, cuerpo


def generar(
    db: Session,
    tenant_id: UUID,
    ahora: datetime | None = None,
    ventanas: tuple[int, ...] | None = None,
) -> Resultado:
    """Crea los avisos que correspondan hoy, **sin repetir los de ayer**."""
    ahora = ahora or datetime.now(timezone.utc)
    ventanas = ventanas if ventanas is not None else ventanas_de(db, tenant_id)
    r = Resultado(ventanas=ventanas)

    for dias in ventanas:
        objetivo = ahora + timedelta(days=dias)

        obligaciones = db.scalars(
            select(Obligation).where(
                Obligation.tenant_id == tenant_id,
                # No se avisa de lo ya resuelto. `submitted` si entra: se
                # presento pero todavia no la aceptan, y el plazo corre igual.
                Obligation.status.not_in(["accepted", "closed"]),
                Obligation.due_at >= objetivo - MARGEN,
                Obligation.due_at <= objetivo + MARGEN,
                Obligation.deleted_at.is_(None),
            )
        ).all()

        for obl in obligaciones:
            clave = _clave(obl.id, dias)
            ya = _destinatarios_ya_avisados(db, tenant_id, clave)

            todos, escalado = _destinatarios(db, obl)
            destinatarios = [u for u in todos if u not in ya]
            if todos and not destinatarios:
                r.omitidos_por_repetidos += 1
                continue
            if not todos:
                # Ni responsable ni administrador activo. **Se cuenta y se
                # informa** en vez de saltarlo en silencio, que es lo que hacia
                # el generador anterior con toda obligacion sin dueno.
                r.sin_destinatario.append(obl.code)
                continue

            asunto, cuerpo = _cuerpo(obl, dias, escalado)

            # La plantilla Excel del sistema ante el que se declara (#117). Va
            # en el contexto y **no pegada en el cuerpo**: quien envie el correo
            # necesita el id para adjuntar el archivo, no su nombre en una
            # frase. Sin sistema, sin plantilla, o con la plantilla caducada, el
            # aviso sale igual — uno sin adjunto sirve; uno que no se envia, no.
            plantilla = _plantilla_de(db, obl)
            contexto = {
                "obligation_id": str(obl.id),
                "days_before": dias,
                "escalado": escalado,
                "urgencia": urgencia(obl, ahora).nivel,
            }
            if plantilla is not None:
                contexto["template_id"] = str(plantilla.id)
                contexto["template_name"] = plantilla.name
                contexto["template_version"] = plantilla.version

            for uid in destinatarios:
                db.add(
                    Notification(
                        tenant_id=tenant_id,
                        recipient_user_id=uid,
                        channel="in_app",
                        subject=asunto,
                        body=cuerpo,
                        status="queued",
                        # La misma clave para los N destinatarios de un
                        # escalamiento: el indice unico es
                        # `(tenant, clave, destinatario)`, asi que cada persona
                        # recibe el aviso una vez y solo una.
                        #
                        # La primera version indexaba sin el destinatario y **la
                        # base la rechazo en la primera prueba**: escalar
                        # inserta una fila por administrador.
                        dedupe_key=clave,
                        context=contexto,
                    )
                )
                r.creados += 1
            if escalado:
                r.escalados += 1

            # El `flush` va por obligacion y no al final: sin el, `_ya_existe`
            # no ve lo insertado en esta misma corrida y una obligacion que cae
            # en dos ventanas a la vez se duplicaria.
            db.flush()

    return r
