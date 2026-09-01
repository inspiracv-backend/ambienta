"""Control de informacion documentada (RF-102 a RF-106, epica #31).

ISO 9001 §7.5. El cliente lo nombro directo: *"la informacion se maneja por
correo y se pierde"*.

## Lo que ya existia y lo que no

La capa de evidencias esta desde `01_schema.sql` —`documents`,
`document_versions`, `entity_documents`, con almacenamiento abstraido— pero
**sin control**: sin codigo no se puede citar un documento en una auditoria, y
sin aprobacion registrada **nada impedia usar un borrador como evidencia**.

Ese ultimo es el agujero que importa. Una evidencia sin aprobar no sostiene
nada ante un fiscalizador, y el sistema la aceptaba sin decir palabra.

## El ciclo de vida vive en la revision, no en el documento

    borrador -> en_revision -> aprobado -> vigente -> obsoleto

El "Procedimiento de Manejo de Residuos PR-07" es el mismo documento en su
revision 1 y en su revision 4. Lo que se aprueba, lo que entra en vigencia y lo
que queda obsoleto son **las revisiones**.

Poner el estado en `documents` obligaria a que aprobar la revision 4
"desaprobara" la 3, y se perderia el rastro de que la 3 estuvo vigente entre
tales fechas — que es exactamente lo que una auditoria pregunta.

## Aprobar y poner en vigencia son dos actos distintos

Se aprueba una revision hoy y entra en vigencia el primero del mes que viene.
Juntarlos obligaria a aprobar el mismo dia que rige, o a aprobar tarde. Por eso
`aprobado` y `vigente` son dos estados y no uno.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.documents import Document, DocumentVersion, EntityDocument

#: Los tipos que son documentacion controlada del sistema de gestion (RF-102).
#:
#: Los otros que admite `documents.document_type` —comprobantes, plantillas,
#: adjuntos de correo— son archivos de la operacion: **no se aprueban ni se
#: revisan**, solo se guardan. Exigirles ciclo de vida obligaria a "aprobar" el
#: comprobante que devolvio un portal del Estado, que no tiene sentido.
TIPOS_CONTROLADOS = frozenset(
    {"politica", "procedimiento", "instructivo", "formato", "registro", "externo"}
)

#: Que estado puede seguir a cual. Lo que no esta, no se puede.
TRANSICIONES: dict[str, set[str]] = {
    "borrador": {"en_revision", "obsoleto"},
    # Vuelve a borrador si la revision encuentra algo que corregir.
    "en_revision": {"aprobado", "borrador", "obsoleto"},
    "aprobado": {"vigente", "obsoleto"},
    "vigente": {"obsoleto"},
    # **Sin salida.** Un documento obsoleto que "revive" deja a quien lo cito
    # sin saber si en ese momento regia. Se emite una revision nueva.
    "obsoleto": set(),
}

#: Los estados en los que una revision sirve como evidencia.
#:
#: `aprobado` **no** entra: aprobada pero sin entrar en vigencia significa que
#: todavia rige la anterior.
SIRVE_COMO_EVIDENCIA = frozenset({"vigente"})


class ErrorDocumental(Exception):
    """La operacion pedida no corresponde."""


class TransicionInvalida(ErrorDocumental):
    """Ese salto de estado no existe."""


class NoEsControlado(ErrorDocumental):
    """El tipo de documento no lleva ciclo de vida."""


class EvidenciaSinAprobar(ErrorDocumental):
    """**RF-105.** Se intento usar como evidencia algo que no rige."""


def _revision(db: Session, version_id: UUID) -> DocumentVersion:
    v = db.get(DocumentVersion, version_id)
    if v is None:
        # Lo mismo para "no existe" y "es de otra empresa": las claves foraneas
        # no pasan por RLS, y distinguirlas seria un oraculo de existencia.
        raise ErrorDocumental("La revision no corresponde a un documento de esta empresa.")
    return v


def _exigir_controlado(doc: Document) -> None:
    if doc.document_type not in TIPOS_CONTROLADOS:
        raise NoEsControlado(
            f"'{doc.document_type}' es un archivo de la operacion, no documentacion "
            f"controlada. Los tipos con ciclo de vida son: "
            f"{', '.join(sorted(TIPOS_CONTROLADOS))}."
        )


def _mover(db: Session, revision: DocumentVersion, destino: str) -> None:
    permitidos = TRANSICIONES.get(revision.lifecycle_status, set())
    if destino not in permitidos:
        raise TransicionInvalida(
            f"Una revision en '{revision.lifecycle_status}' no puede pasar a "
            f"'{destino}'. Desde aca solo se puede: "
            f"{', '.join(sorted(permitidos)) or 'nada'}."
        )
    revision.lifecycle_status = destino


def enviar_a_revision(db: Session, *, version_id: UUID) -> DocumentVersion:
    """El borrador queda listo para que alguien lo revise."""
    revision = _revision(db, version_id)
    _exigir_controlado(revision.document)
    _mover(db, revision, "en_revision")
    db.flush()
    return revision


def devolver_a_borrador(db: Session, *, version_id: UUID) -> DocumentVersion:
    """La revision encontro algo que corregir (RF-104).

    `TRANSICIONES` declaraba `en_revision -> borrador` desde el principio y
    **no habia funcion para hacerlo**: la maquina de estados estaba escrita a
    medias y el unico camino desde `en_revision` era aprobar o mandar a
    obsoleto. Eso deja a quien revisa con dos salidas malas — aprobar algo que
    no corresponde, o retirar un documento que solo necesitaba una correccion.
    """
    revision = _revision(db, version_id)
    _exigir_controlado(revision.document)
    _mover(db, revision, "borrador")
    db.flush()
    return revision


def aprobar(
    db: Session, *, version_id: UUID, aprobador_id: UUID, ahora: datetime | None = None
) -> DocumentVersion:
    """Registra la aprobacion (RF-105).

    **Quien aprueba queda escrito, no es opcional.** La base tiene un CHECK que
    lo exige, asi que ni siquiera un `UPDATE` a mano puede dejar una revision
    aprobada sin firma. Una aprobacion anonima no sirve de nada ante una
    auditoria: la pregunta no es si se aprobo, es quien.
    """
    revision = _revision(db, version_id)
    _exigir_controlado(revision.document)
    _mover(db, revision, "aprobado")
    revision.approved_at = ahora or datetime.now(timezone.utc)
    revision.approved_by = aprobador_id
    db.flush()
    return revision


def poner_en_vigencia(
    db: Session, *, version_id: UUID, desde: date | None = None, motivo: str | None = None
) -> DocumentVersion:
    """La revision empieza a regir, y **la anterior queda obsoleta**.

    Es un solo acto porque son un solo hecho: dos revisiones vigentes a la vez
    dejan a la empresa sin saber cual manda. La base lo respalda con un indice
    unico, asi que si esto se escribiera mal reventaria en vez de dejar el dato
    incoherente.

    La anterior **no se borra**: se marca obsoleta con su motivo (RF-106). Las
    evaluaciones que la citan siguen necesitando saber contra que se evaluaron.
    """
    revision = _revision(db, version_id)
    doc = revision.document
    _exigir_controlado(doc)

    anterior = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.lifecycle_status == "vigente",
        )
    )
    if anterior is not None and anterior.id != revision.id:
        anterior.lifecycle_status = "obsoleto"
        anterior.obsoleted_at = datetime.now(timezone.utc)
        anterior.obsoleted_reason = (
            motivo or f"Reemplazada por la revision {revision.version_no}."
        )
        anterior.valid_to = desde or date.today()
        # **Antes de mover la nueva.** El indice unico solo admite una vigente:
        # al reves, el `flush` chocaria contra la que todavia lo es.
        db.flush()

    _mover(db, revision, "vigente")
    revision.valid_from = desde or date.today()
    doc.status = "vigente"
    doc.current_version_id = revision.id
    db.flush()
    return revision


def marcar_obsoleta(
    db: Session, *, version_id: UUID, motivo: str
) -> DocumentVersion:
    """Retira una revision **conservandola** (RF-106).

    El motivo es obligatorio. Un obsoleto sin explicacion obliga a quien lo
    encuentre a adivinar si todavia sirve para algo, y en la duda se usa.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErrorDocumental(
            "Un documento obsoleto sin motivo obliga a adivinar si todavia sirve. "
            "Indica por que dejo de regir."
        )

    revision = _revision(db, version_id)
    doc = revision.document
    _exigir_controlado(doc)
    _mover(db, revision, "obsoleto")
    revision.obsoleted_at = datetime.now(timezone.utc)
    revision.obsoleted_reason = motivo
    revision.valid_to = date.today()

    # Si era la vigente, el documento entero queda sin nada que rija.
    if doc.current_version_id == revision.id:
        doc.status = "obsoleto"
        doc.current_version_id = None

    db.flush()
    return revision


def validar_sirve_como_evidencia(db: Session, *, document_id: UUID) -> None:
    """**RF-105: un documento no aprobado no sirve como evidencia.**

    La comprobacion que no existia. Hasta ahora se podia colgar un borrador de
    una evaluacion de cumplimiento y el sistema lo aceptaba sin decir palabra —
    la empresa quedaba creyendo que tenia respaldo.

    Los archivos de la operacion **pasan sin comprobacion**: un comprobante del
    RETC o un adjunto de correo son evidencia por lo que son, no por haber sido
    aprobados por nadie. Exigirles aprobacion obligaria a inventar un flujo para
    algo que llega ya validado por un tercero.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise ErrorDocumental("El documento no corresponde a esta empresa.")

    if doc.document_type not in TIPOS_CONTROLADOS:
        return

    if doc.current_version_id is None:
        raise EvidenciaSinAprobar(
            f"'{doc.title}' no tiene ninguna revision vigente, asi que no puede "
            f"usarse como evidencia. Aprueba una revision y ponla en vigencia."
        )

    vigente = db.get(DocumentVersion, doc.current_version_id)
    if vigente is None or vigente.lifecycle_status not in SIRVE_COMO_EVIDENCIA:
        estado = vigente.lifecycle_status if vigente else "sin revision"
        raise EvidenciaSinAprobar(
            f"La revision actual de '{doc.title}' esta en '{estado}'. Solo una "
            f"revision vigente sirve como evidencia."
        )


def documentos_que_lo_citan(db: Session, *, version_id: UUID) -> list[EntityDocument]:
    """Que registros usan como evidencia el documento de esta revision.

    Sirve antes de marcar algo obsoleto: si diez evaluaciones lo citan, quien
    lo retira deberia saberlo. **No lo impide** — retirar un documento vencido
    es lo correcto aunque haya evaluaciones viejas apuntandole, porque esas
    evaluaciones se hicieron cuando si regia.
    """
    revision = _revision(db, version_id)
    return list(
        db.scalars(
            select(EntityDocument).where(
                EntityDocument.document_id == revision.document_id,
                EntityDocument.purpose == "evidence",
                EntityDocument.deleted_at.is_(None),
            )
        ).all()
    )
