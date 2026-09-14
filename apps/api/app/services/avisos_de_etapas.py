"""Avisos al responsable de cada etapa del registro de mejora (RF-99, #40).

## Por que existe

Las etapas nacen con el registro, cada una con su responsable y su fecha limite
(`etapas_de_mejora.sembrar_ciclo`). Sin aviso, **el ciclo se detiene sin que
nada falle**: la etapa queda asignada a alguien que no sabe que la tiene, vence,
y el registro no se puede cerrar. Eso es exactamente lo que un auditor lee como
"el sistema de gestion no gestiona sus hallazgos".

## Tres avisos, y los tres se escriben una sola vez

| Aviso | Cuando | A quien |
|---|---|---|
| **Asignacion** | la etapa tiene responsable y no esta completada | al responsable |
| **Por vencer** | faltan N dias (ventanas de la empresa) | al responsable, o escalado |
| **Vencida** | la fecha limite ya paso | al responsable, o escalado |

Mismo mecanismo que `avisos_de_vencimiento.py`, y a proposito: la unicidad la
garantiza el indice `(tenant, dedupe_key, destinatario)` de `db/17`, no un `if`,
y las fechas se comparan **por calendario en el huso de la empresa**, nunca
sumando horas — la leccion del cron que a las 07:00 no avisaba nunca.

## Lo que NO avisa

- **Etapas completadas.** `completada_en` no nulo.
- **Registros cerrados o rechazados.** Una etapa pendiente de un registro que
  ya se cerro por la regla anterior no es trabajo de nadie.
- **Etapas sin fecha limite**, salvo la asignacion. Hoy son todas: los plazos de
  `improvement_severities.days_to_close` estan en NULL a proposito hasta que la
  empresa los declare. Inventar una fecha para poder avisar produciria un
  vencimiento que nadie acordo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.audit import ImprovementStageEntry, Nonconformity
from ..models.notifications import Notification, NotificationRule
from ..models.organization import User
from .husos import huso_de

#: El evento de las reglas y plantillas de la empresa. Distinto del de las
#: obligaciones: los plazos de una no conformidad son de semanas, no de meses,
#: y una empresa puede querer ventanas distintas para cada cosa.
EVENTO = "improvement_stage_due"

#: Mas cortas que las de las obligaciones (15/7/3/1): una etapa de tratamiento
#: dura dias o semanas. Avisar a 15 dias de una etapa de 10 no tiene sentido.
VENTANAS_POR_DEFECTO = (7, 3, 1)

NOMBRE_DE_ETAPA = {
    "registro": "Registro",
    "correccion": "Correccion",
    "analisis_causa": "Analisis de causa",
    "accion_correctiva": "Accion correctiva",
    "seguimiento": "Seguimiento",
}

ESTADOS_SIN_TRABAJO = ("closed", "rejected")


@dataclass
class Resultado:
    creados: int = 0
    omitidos_por_repetidos: int = 0
    escalados: int = 0
    #: `CODIGO:etapa` de lo que no le aviso a nadie. Es el numero a mirar.
    sin_destinatario: list[str] = field(default_factory=list)


def ventanas_de(db: Session, tenant_id: UUID) -> tuple[int, ...]:
    """Los dias de anticipacion de esta empresa para las etapas."""
    minutos = db.scalars(
        select(NotificationRule.lead_minutes).where(
            NotificationRule.tenant_id == tenant_id,
            NotificationRule.event_type == EVENTO,
            NotificationRule.active.is_(True),
            NotificationRule.deleted_at.is_(None),
        )
    ).all()
    dias = {m // 1440 for m in minutos if m and m > 0}
    return tuple(sorted(dias, reverse=True)) if dias else VENTANAS_POR_DEFECTO


def _administradores(db: Session, tenant_id: UUID) -> list[UUID]:
    return list(
        db.scalars(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.user_type == "tenant_admin",
                User.status == "active",
                User.deleted_at.is_(None),
            )
        ).all()
    )


def _ya_avisados(db: Session, tenant_id: UUID, clave: str) -> set:
    return set(
        db.scalars(
            select(Notification.recipient_user_id).where(
                Notification.tenant_id == tenant_id,
                Notification.dedupe_key == clave,
                Notification.deleted_at.is_(None),
            )
        ).all()
    )


def _fecha(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "sin fecha limite"


def _encolar(
    db: Session,
    r: Resultado,
    *,
    tenant_id: UUID,
    destinatarios: list[UUID],
    clave_base: str,
    asunto: str,
    cuerpo: str,
    contexto: dict,
) -> None:
    # Los dos canales, igual que las obligaciones: sin la fila de correo, la
    # tuberia de Resend no tiene nada que mandar y nada falla.
    for canal in ("in_app", "email"):
        clave = f"{clave_base}:{canal}"
        ya = _ya_avisados(db, tenant_id, clave)
        faltan = [u for u in destinatarios if u not in ya]
        if not faltan:
            r.omitidos_por_repetidos += 1
            continue
        for uid in faltan:
            db.add(
                Notification(
                    tenant_id=tenant_id,
                    recipient_user_id=uid,
                    channel=canal,
                    subject=asunto,
                    body=cuerpo,
                    status="queued",
                    dedupe_key=clave,
                    context=contexto,
                )
            )
            r.creados += 1
    db.flush()


def generar(
    db: Session,
    tenant_id: UUID,
    ahora: datetime | None = None,
    ventanas: tuple[int, ...] | None = None,
) -> Resultado:
    """Crea los avisos de etapas que correspondan hoy, sin repetir."""
    ahora = ahora or datetime.now(timezone.utc)
    ventanas = ventanas if ventanas is not None else ventanas_de(db, tenant_id)
    hoy = ahora.astimezone(ZoneInfo(huso_de(db, tenant_id))).date()
    r = Resultado()

    filas = db.execute(
        select(ImprovementStageEntry, Nonconformity)
        .join(Nonconformity, Nonconformity.id == ImprovementStageEntry.nonconformity_id)
        .where(
            ImprovementStageEntry.tenant_id == tenant_id,
            ImprovementStageEntry.deleted_at.is_(None),
            ImprovementStageEntry.completada_en.is_(None),
            Nonconformity.deleted_at.is_(None),
            Nonconformity.status.not_in(ESTADOS_SIN_TRABAJO),
        )
    ).all()

    admins: list[UUID] | None = None

    for etapa, registro in filas:
        nombre = NOMBRE_DE_ETAPA.get(etapa.kind, etapa.kind)
        contexto = {
            "nonconformity_id": str(registro.id),
            "nonconformity_code": registro.code,
            "nonconformity_title": registro.title,
            "stage_id": str(etapa.id),
            "stage_kind": etapa.kind,
            "stage_name": nombre,
            "due_date": _fecha(etapa.due_date),
        }

        # 1. Asignacion. Si la etapa cambia de manos, la persona nueva recibe el
        # suyo y la anterior no recibe otro: la unicidad es **por destinatario**
        # (`_ya_avisados` y el indice de `db/17`), asi que la clave no necesita
        # llevar al responsable. Una primera version lo agregaba "por las dudas"
        # y la prueba de mutacion mostro que no protegia nada.
        if etapa.responsable_user_id is not None:
            _encolar(
                db, r,
                tenant_id=tenant_id,
                destinatarios=[etapa.responsable_user_id],
                clave_base=f"etapa-asignada:{etapa.id}",
                asunto=f"Te asignaron una etapa: {nombre} de {registro.code}",
                cuerpo=(
                    f"Quedaste como responsable de la etapa '{nombre}' del registro "
                    f"{registro.code} ({registro.title}). Fecha limite: "
                    f"{_fecha(etapa.due_date)}."
                ),
                contexto={**contexto, "motivo": "asignacion"},
            )

        if etapa.due_date is None:
            continue

        dias = (etapa.due_date - hoy).days
        if dias < 0:
            motivo, clave_base = "vencida", f"etapa-vencida:{etapa.id}"
            asunto = f"Etapa vencida: {nombre} de {registro.code}"
            texto = f"La etapa '{nombre}' del registro {registro.code} vencio el {_fecha(etapa.due_date)}."
        elif dias in ventanas:
            motivo, clave_base = "por_vencer", f"etapa-vence:{etapa.id}:{dias}"
            asunto = f"Vence en {dias} {'dia' if dias == 1 else 'dias'}: {nombre} de {registro.code}"
            texto = f"La etapa '{nombre}' del registro {registro.code} vence el {_fecha(etapa.due_date)}."
        else:
            continue

        if etapa.responsable_user_id is not None:
            destinatarios, escalado = [etapa.responsable_user_id], False
        else:
            # Sin responsable **se escala en vez de callarse**: una etapa sin
            # dueño que vence es mas urgente que una con dueño, no menos.
            if admins is None:
                admins = _administradores(db, tenant_id)
            destinatarios, escalado = admins, True
            texto += (
                "\n\nRecibes este aviso porque la etapa no tiene responsable. "
                "Asignale uno para que los proximos le lleguen directamente."
            )

        if not destinatarios:
            r.sin_destinatario.append(f"{registro.code}:{etapa.kind}")
            continue

        _encolar(
            db, r,
            tenant_id=tenant_id,
            destinatarios=destinatarios,
            clave_base=clave_base,
            asunto=asunto,
            cuerpo=texto,
            contexto={**contexto, "motivo": motivo, "days_remaining": dias, "escalado": escalado},
        )
        if escalado:
            r.escalados += 1

    return r
