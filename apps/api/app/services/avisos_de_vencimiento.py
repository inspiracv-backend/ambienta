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

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from ..models.catalog import RetcSystem
from ..models.notifications import Notification, NotificationRule
from ..models.obligations import DeclarationTemplate, Obligation
from ..models.organization import Country, Facility, Tenant, User
from . import plantillas_correo
from .declaracion import urgencia

logger = logging.getLogger("ambienta.avisos")

#: Las ventanas por defecto, en dias antes del vencimiento (#120, RF-42).
#:
#: **Se usan cuando la empresa no declaro las suyas**, no como unica opcion. Un
#: tenant recien creado tiene que recibir avisos sin que nadie configure nada;
#: uno con otro ritmo de trabajo declara sus reglas y estas dejan de aplicar.
VENTANAS_POR_DEFECTO = (15, 7, 3, 1)

#: El evento al que corresponden estas reglas en `notification_rules`.
#: **`obligation_due` y no `obligacion_por_vencer`.** Esta constante decia lo
#: segundo y no coincidia con nada: las plantillas sembradas en
#: `notification_templates` usan `obligation_due`, igual que el resto de los
#: `event_type` del seed (`audit_scheduled`, `nc_created`). El desajuste no
#: rompia nada **porque nadie buscaba la plantilla todavia** — al enchufarla
#: (#121) la busqueda no habria encontrado ninguna y el aviso habria salido con
#: el texto de respaldo para siempre, sin ningun error.
EVENTO = "obligation_due"

#: Huso al que se cae si la empresa no tiene pais con huso declarado.
#:
#: Chile porque es el mercado del producto, pero **no da igual**: es el huso el
#: que decide en que dia del calendario cae un vencimiento, y con el equivocado
#: el aviso sale un dia antes o un dia despues.
HUSO_POR_DEFECTO = "America/Santiago"


def huso_de(db: Session, tenant_id: UUID) -> str:
    """El huso horario de la empresa, via el pais al que pertenece.

    `countries.default_timezone` tiene cinco paises distintos, asi que esto no
    es una constante disfrazada: la misma obligacion a las 23:59 cae en dias
    distintos para una empresa chilena y una mexicana.
    """
    nombre = db.scalar(
        select(Country.default_timezone)
        .join(Tenant, Tenant.country_id == Country.id)
        .where(Tenant.id == tenant_id)
    )
    return nombre or HUSO_POR_DEFECTO


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


def _clave(obligacion_id: UUID, dias: int, canal: str) -> str:
    """La clave que impide el duplicado. Ver `db/17`.

    **Lleva el canal.** El indice unico es `(tenant, clave, destinatario)`, asi
    que sin el, el aviso in-app y el correo de la misma obligacion y la misma
    ventana chocarian entre si: la segunda insercion la rechaza la base y la
    persona recibe uno de los dos, no los dos.

    Cambiar el formato deja de reconocer los avisos ya creados con el formato
    viejo, o sea que la primera corrida despues del cambio los recrea. Es
    inocuo **hoy**: no hay produccion todavia, solo datos de ejemplo. El dia que
    la haya, un cambio de formato aca necesita reescribir las claves existentes
    en una migracion.
    """
    return f"vencimiento:{obligacion_id}:{dias}:{canal}"


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


def _nombre_de_planta(db: Session, facility_id: UUID | None) -> str:
    """El nombre de la planta, o algo legible si la obligacion no tiene una.

    No todas la tienen: un compromiso de RCA puede ser de la empresa entera. La
    plantilla la pide igual, y dejar el marcador `{{facility_name}}` a la vista
    en un correo al cliente es peor que decir "toda la empresa".
    """
    if facility_id is None:
        return "toda la empresa"
    nombre = db.execute(
        select(Facility.name).where(Facility.id == facility_id)
    ).scalar()
    return nombre or "toda la empresa"


#: Por que un aviso escalado le llego a quien le llego.
#:
#: Vive aparte porque **tiene que ir en los dos canales**, y el del correo se
#: arma con la plantilla de la empresa — que no sabe nada de escalamientos.
#: Estaba solo en el texto de respaldo, asi que en cuanto una empresa tenia
#: plantilla de correo el parrafo desaparecia justo del canal que si llega.
POR_QUE_TE_LLEGA = (
    "\n\nRecibes este aviso porque la declaracion no tiene un responsable "
    "asignado. Asignale uno para que los proximos le lleguen directamente."
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
        cuerpo += POR_QUE_TE_LLEGA
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
    huso = huso_de(db, tenant_id)
    hoy = ahora.astimezone(ZoneInfo(huso)).date()
    r = Resultado(ventanas=ventanas)

    for dias in ventanas:
        # **Se comparan fechas, no instantes**, y eso es el arreglo del 4-sep.
        #
        # Antes esto era una banda de +-12 h alrededor de `ahora + N dias`. Un
        # plazo legal vence a las 23:59 del dia, o sea a las 02:59 UTC del
        # siguiente, y el cron esta configurado a las 07:00: entre los dos hay
        # 17 h. Fuera de la banda. Medido el 4-sep, con el cron a las 07:00 y
        # una obligacion que vence a las 23:59:
        #
        # | hora del cron | avisos, en cualquier ventana |
        # |---|---|
        # | 07:00 (la configurada) | **0** |
        # | 12:00, 18:00, 23:00 | 2 |
        #
        # O sea que tal como esta desplegado el sistema **no habria avisado
        # nunca**, y la banda de 12 h se veia como una precaucion razonable.
        # Doce horas cubren medio dia; el que quedaba afuera era justo el de la
        # mañana.
        #
        # Un margen mas ancho no es el arreglo: correrlo a 24 h haria que un
        # mismo vencimiento cayera en dos ventanas contiguas. Lo que una persona
        # quiere decir con "avisar 15 dias antes" es **un dia del calendario**,
        # no un intervalo de horas, y por eso se compara asi.
        objetivo = hoy + timedelta(days=dias)

        obligaciones = db.scalars(
            select(Obligation).where(
                Obligation.tenant_id == tenant_id,
                # No se avisa de lo ya resuelto. `submitted` si entra: se
                # presento pero todavia no la aceptan, y el plazo corre igual.
                Obligation.status.not_in(["accepted", "closed"]),
                cast(func.timezone(huso, Obligation.due_at), Date) == objetivo,
                Obligation.deleted_at.is_(None),
            )
        ).all()

        for obl in obligaciones:
            todos, escalado = _destinatarios(db, obl)
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
                # Lo que piden las plantillas sembradas. Los nombres son los de
                # `notification_templates`, no los de aca: la plantilla es dato
                # de empresa y ya estaba escrita, asi que manda ella.
                "obligation_code": obl.code,
                "obligation_title": obl.title,
                "days_remaining": dias,
                "due_date": (
                    obl.due_at.strftime("%d/%m/%Y") if obl.due_at else "sin fecha"
                ),
                "facility_name": _nombre_de_planta(db, obl.facility_id),
            }
            if plantilla is not None:
                contexto["template_id"] = str(plantilla.id)
                contexto["template_name"] = plantilla.name
                contexto["template_version"] = plantilla.version

            # Los dos canales (RF-32). Antes solo se creaba el in-app, asi
            # que **la tuberia de correo no tenia nada que enviar**: se podia
            # configurar Resend entero y no salia un solo mensaje.
            #
            # El correo se arma desde la plantilla de la empresa si la hay. Si
            # no, sale con el mismo texto que el in-app: un aviso sin diseno
            # sirve, uno que no se envia no.
            for canal in ("in_app", "email"):
                asunto_canal, cuerpo_canal = asunto, cuerpo
                if canal == "email":
                    plantilla_correo = plantillas_correo.buscar(
                        db, tenant_id=tenant_id, event_type=EVENTO, channel="email"
                    )
                    if plantilla_correo is not None:
                        rellenada = plantillas_correo.aplicar(plantilla_correo, contexto)
                        if rellenada.faltantes:
                            # No se cae ni se manda a medias en silencio: sale
                            # el texto de respaldo, que esta completo, y queda
                            # anotado que la plantilla pide algo que el contexto
                            # no trae.
                            logger.warning(
                                "La plantilla %s pide variables que el aviso no trae (%s). "
                                "Se usa el texto por defecto.",
                                plantilla_correo.code,
                                ", ".join(rellenada.faltantes),
                            )
                        else:
                            asunto_canal = rellenada.asunto
                            cuerpo_canal = rellenada.cuerpo
                            if escalado:
                                # **La plantilla no sabe de escalamientos**, y
                                # no puede: son dato de empresa y solo admiten
                                # sustitucion de `{{variable}}`, sin
                                # condicionales — a proposito, porque un motor
                                # con expresiones convierte "editar una
                                # plantilla" en "ejecutar codigo en la API".
                                #
                                # Asi que el parrafo se pega despues. Medido: el
                                # aviso in-app lo explicaba y **el del correo
                                # no**, o sea que el canal que de verdad llega
                                # era justo el que no decia por que llegaba.
                                cuerpo_canal += POR_QUE_TE_LLEGA

                clave = _clave(obl.id, dias, canal)
                ya = _destinatarios_ya_avisados(db, tenant_id, clave)
                destinatarios = [u for u in todos if u not in ya]
                if not destinatarios:
                    r.omitidos_por_repetidos += 1
                    continue

                for uid in destinatarios:
                    db.add(
                        Notification(
                            tenant_id=tenant_id,
                            recipient_user_id=uid,
                            channel=canal,
                            subject=asunto_canal,
                            body=cuerpo_canal,
                            status="queued",
                            # La misma clave para los N destinatarios de un
                            # escalamiento: el indice unico es
                            # `(tenant, clave, destinatario)`, asi que cada
                            # persona recibe el aviso una vez y solo una.
                            #
                            # La primera version indexaba sin el destinatario y
                            # **la base la rechazo en la primera prueba**:
                            # escalar inserta una fila por administrador.
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
