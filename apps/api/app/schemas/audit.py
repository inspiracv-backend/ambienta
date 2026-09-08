from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .base import OrmBase


# ── Audit ─────────────────────────────────────────────────────────────────

class AuditCreate(BaseModel):
    facility_id: UUID | None = None
    code: str
    title: str
    audit_type: str
    scope: str
    lead_auditor_user_id: UUID | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    criteria: dict = Field(default_factory=dict)


class AuditRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    code: str
    title: str
    audit_type: str
    scope: str
    lead_auditor_user_id: UUID | None
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    status: str
    criteria: dict
    created_at: datetime
    updated_at: datetime


class AuditUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    criteria: dict | None = None


# ── AuditItem ─────────────────────────────────────────────────────────────

class AuditItemCreate(BaseModel):
    audit_id: UUID
    article_compliance_id: UUID | None = None
    #: El proceso auditado. Opcional: un requisito general del sistema
    #: de gestion no pertenece a ninguno.
    process_id: UUID | None = None
    sequence: int
    question: str
    #: **Faltaba, y por eso `notes` se perdia en silencio.** Arreglar solo el
    #: esquema anidado dejaba el mismo agujero un nivel mas abajo: el cuerpo lo
    #: aceptaba, `AuditItemCreate` lo descartaba, y la respuesta salia 201.
    notes: str | None = None
    auditor_user_id: UUID | None = None


class AuditItemRead(OrmBase):
    id: UUID
    tenant_id: UUID
    audit_id: UUID
    article_compliance_id: UUID | None
    process_id: UUID | None
    sequence: int
    question: str
    result: str
    notes: str | None
    auditor_user_id: UUID | None
    assessed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuditItemUpdate(BaseModel):
    question: str | None = None
    #: `conform | nonconform | observation | not_applicable | pending`. Los
    #: valores son los del CHECK de la tabla, no traducciones.
    result: str | None = None
    notes: str | None = None
    auditor_user_id: UUID | None = None
    article_compliance_id: UUID | None = None
    #: El proceso auditado. Opcional: un requisito general del sistema
    #: de gestion no pertenece a ninguno.
    process_id: UUID | None = None
    #: `assessed_at` **se quito del cuerpo a proposito.** La marca de cuando se
    #: respondio la pone el servidor: aceptarla permitiria fechar una respuesta
    #: cuando conviniera, y esa fecha es justo lo que revisa un certificador
    #: para saber si la auditoria se contesto durante su ejecucion o despues de
    #: cerrarla.


# ── AuditParticipant ──────────────────────────────────────────────────────

class AuditParticipantCreate(BaseModel):
    audit_id: UUID
    user_id: UUID
    external_name: str | None = None
    external_email: str | None = None
    participant_role: str
    attendance_status: str = "invited"
    notes: str | None = None


class AuditParticipantRead(OrmBase):
    audit_id: UUID
    user_id: UUID
    tenant_id: UUID
    external_name: str | None
    external_email: str | None
    participant_role: str
    attendance_status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ── Nonconformity ─────────────────────────────────────────────────────────

#: Los origenes que obligan a decir de que hallazgo salio el registro.
ORIGENES_DE_AUDITORIA = ("auditoria_interna", "auditoria_externa")

#: Lo que cada tipo de registro exige, con la clausula que lo pide.
#:
#: **Las mismas reglas viven en la base** (`db/24`), y esa es la barrera: un
#: `UPDATE` a mano tambien tiene que respetarlas, y el registro de mejora es de
#: las tablas que alguien corrige por SQL cuando algo sale mal. Aca se
#: comprueban antes para responder un 422 legible en vez de un error de
#: restriccion, que se lee como un fallo del sistema y no como un dato que falta.
DATOS_POR_TIPO = {
    "salida_no_conforme": ("product_data", ("sku", "lote"), "ISO 9001 8.7"),
    "reclamo": ("complaint_data", ("cliente_nombre", "canal"), "ISO 9001 9.1.2"),
}


class NonconformityCreate(BaseModel):
    """Alta de un registro de mejora (#37, RF-46 y RF-96).

    **El tipo es la primera decision y define que mas se exige.** No es un
    campo de clasificacion que se rellena al final: una salida no conforme sin
    producto ni lote no dice que salida se controlo, y un reclamo sin cliente ni
    canal no es un reclamo, es una nota.
    """

    facility_id: UUID | None = None
    audit_item_id: UUID | None = None
    article_compliance_id: UUID | None = None
    code: str
    title: str
    description: str
    severity: str
    record_type: str | None = None
    detection_origin: str | None = None
    owner_user_id: UUID | None = None
    due_date: date | None = None
    #: Solo para `salida_no_conforme`. Claves: sku, lote, nombre, cantidad, unidad.
    product_data: dict | None = None
    #: Solo para `reclamo`. Claves: cliente_nombre, canal, fecha_reclamo, cliente_id.
    complaint_data: dict | None = None
    risk_opportunity_id: UUID | None = None
    #: Del catalogo de la empresa. La clave foranea **no pasa por RLS**, asi que
    #: el router tiene que comprobarla con `validar_visible`.
    root_cause_methodology_id: UUID | None = None

    @model_validator(mode="after")
    def _los_datos_de_su_tipo(self):
        """Que esten los del tipo, y que no esten los de otro.

        Las dos mitades importan. La primera es la que pide la norma; la segunda
        evita un registro mal clasificado —un reclamo con datos de producto—
        que **se veria exactamente igual que uno bien hecho** en cualquier
        listado.
        """
        for tipo, (campo, claves, clausula) in DATOS_POR_TIPO.items():
            valor = getattr(self, campo)
            if self.record_type == tipo:
                faltan = [
                    k for k in claves
                    if not str((valor or {}).get(k, "")).strip()
                ]
                if faltan:
                    raise ValueError(
                        f"Un registro de tipo «{tipo}» exige {campo} con "
                        f"{', '.join(faltan)} ({clausula})."
                    )
            elif valor is not None:
                raise ValueError(
                    f"«{campo}» solo corresponde a un registro de tipo "
                    f"«{tipo}», y este es «{self.record_type or 'sin tipo'}»."
                )

        if self.detection_origin in ORIGENES_DE_AUDITORIA and self.audit_item_id is None:
            raise ValueError(
                "Un registro con origen en una auditoria tiene que decir de que "
                "hallazgo salio: sin eso no hay trazabilidad hacia la auditoria "
                "que lo origino, que es lo primero que se pide al revisar su "
                "seguimiento."
            )
        return self


class NonconformityRead(OrmBase):
    id: UUID
    tenant_id: UUID
    facility_id: UUID | None
    audit_item_id: UUID | None
    article_compliance_id: UUID | None
    code: str
    title: str
    description: str
    severity: str
    status: str
    record_type: str | None
    detection_origin: str | None
    root_cause_answers: list
    improvement_stages: dict
    product_data: dict | None
    complaint_data: dict | None
    risk_opportunity_id: UUID | None
    detected_at: datetime
    detected_by: UUID | None
    owner_user_id: UUID | None
    due_date: date | None
    closed_at: datetime | None
    closure_notes: str | None
    created_at: datetime
    updated_at: datetime


class NonconformityUpdate(BaseModel):
    title: str | None = None
    severity: str | None = None
    status: str | None = None
    root_cause_answers: list | None = None
    improvement_stages: dict | None = None
    owner_user_id: UUID | None = None
    due_date: date | None = None
    closure_notes: str | None = None


# ── ActionPlan ────────────────────────────────────────────────────────────

class ActionPlanCreate(BaseModel):
    article_compliance_id: UUID | None = None
    nonconformity_id: UUID | None = None
    title: str
    root_cause: str | None = None
    objective: str
    priority: str = "medium"
    owner_user_id: UUID | None = None
    target_date: date | None = None
    success_criteria: dict = Field(default_factory=dict)


class ActionPlanRead(OrmBase):
    id: UUID
    tenant_id: UUID
    article_compliance_id: UUID | None
    nonconformity_id: UUID | None
    title: str
    root_cause: str | None
    objective: str
    status: str
    priority: str
    owner_user_id: UUID | None
    target_date: date | None
    verified_at: datetime | None
    verified_by: UUID | None
    success_criteria: dict
    created_at: datetime
    updated_at: datetime


class ActionPlanUpdate(BaseModel):
    title: str | None = None
    root_cause: str | None = None
    objective: str | None = None
    status: str | None = None
    priority: str | None = None
    owner_user_id: UUID | None = None
    target_date: date | None = None
    success_criteria: dict | None = None


# ── EntityStatusHistory ───────────────────────────────────────────────────

class EntityStatusHistoryRead(OrmBase):
    id: int
    tenant_id: UUID
    entity_type: str
    entity_id: UUID
    from_status: str | None
    to_status: str
    changed_at: datetime
    changed_by: UUID | None
    reason: str | None


class AuditParticipantUpdate(BaseModel):
    """Lo editable de un participante.

    `audit_id` y `user_id` no estan: son la clave compuesta, o sea la
    identidad de la fila. Cambiarlos no es editar, es otro participante.
    """

    participant_role: str | None = None
    attendance_status: str | None = None
    external_name: str | None = None
    external_email: str | None = None
    notes: str | None = None


class AuditParticipantCreateAnidado(BaseModel):
    """Cuerpo de `POST /audits/{audit_id}/participants/{user_id}`.

    La auditoria y la persona vienen del path: son la clave compuesta.
    """

    participant_role: str
    attendance_status: str = "invited"
    external_name: str | None = None
    external_email: str | None = None
    notes: str | None = None


class AuditItemCreateAnidado(BaseModel):
    """Cuerpo de `POST /audits/{audit_id}/items`. La auditoria viene del path.

    **Nombraba cuatro campos que la tabla no tiene** —`clause_reference`,
    `article_id`, `result`, `evidence_note`— y `create_audit_item` los pasaba a
    `AuditItemCreate`, que los descarta. Medido: la API respondia **201** y
    guardaba `result = 'pending'` aunque se mandara `conform`, y la nota de
    evidencia desaparecia sin dejar rastro.

    Y faltaba `article_compliance_id`, que es **el vinculo por clausula que
    RF-92 pide**: sin el no habia forma de decir que requisito legal revisa cada
    pregunta, ni de calcular cobertura.

    `sequence` pasa a ser opcional: sin el se toma el siguiente. La base lo
    exige unico por auditoria (`uq_audit_items_seq`), asi que dejarlo siempre en
    manos de quien llama convierte un olvido en un error de restriccion.

    `result` **no esta a proposito**: una pregunta nace sin responder. Aceptarlo
    al crear permitiria levantar un checklist ya contestado sin que nadie lo
    haya recorrido, y la marca de cuando se respondio quedaria vacia.
    """

    question: str
    sequence: int | None = None
    article_compliance_id: UUID | None = None
    #: A que proceso pertenece la pregunta. **Opcional a proposito**: un
    #: requisito general del sistema de gestion no es de ningun proceso, y
    #: forzarlo a uno inventaria una pertenencia. El informe los cuenta aparte.
    process_id: UUID | None = None
    notes: str | None = None
    auditor_user_id: UUID | None = None


class CoberturaDeAuditoria(BaseModel):
    """Cuanto de lo aplicable miro la auditoria de verdad (RF-93).

    Es el numero que falta para leer un resumen sin equivocarse: sin el, una
    auditoria que reviso 3 de 50 requisitos y no encontro nada se lee
    **identica** a una que los reviso los 50 — las dos dicen "0 no conformes".
    """

    aplicables: int
    cubiertos: int
    #: `null` cuando no hay nada aplicable — **no cero**. Un 0 % ahi seria una
    #: acusacion por algo que no existe, el mismo error del tablero con las
    #: plantas sin evaluar.
    porcentaje: float | None
    #: Preguntas de proceso, sin requisito legal asociado. Van aparte para que
    #: nadie las confunda con cobertura.
    items_sin_articulo: int


# ── Catalogos configurables por empresa (RF-100, #41) ───────────────────────


#: Las formas que el sistema sabe pedir y mostrar.
#:
#: Es una lista cerrada mientras el nombre no lo es: una empresa llama a su
#: metodologia como quiera, pero no puede inventar una forma para la que no hay
#: ni formulario ni manera de leer las respuestas.
FORMAS_DE_ANALISIS = ("cinco_porques", "espina_pescado", "texto_libre")


class SeveridadBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=80)
    rank: int = 0
    #: Dias para cerrar un hallazgo de este nivel. **`None` no es cero**: es
    #: "la empresa no declaro plazo", y entonces nadie calcula la fecha limite.
    #: Sembrar un numero seria inventarle el compromiso, y un plazo falso en un
    #: sistema de cumplimiento hace creer que se va a tiempo.
    days_to_close: int | None = Field(default=None, gt=0)
    active: bool = True


class SeveridadCreate(SeveridadBase):
    pass


class SeveridadUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    rank: int | None = None
    days_to_close: int | None = Field(default=None, gt=0)
    active: bool | None = None


class SeveridadRead(SeveridadBase, OrmBase):
    id: UUID
    tenant_id: UUID


class MetodologiaBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    shape: Literal["cinco_porques", "espina_pescado", "texto_libre"]
    active: bool = True


class MetodologiaCreate(MetodologiaBase):
    pass


class MetodologiaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    shape: Literal["cinco_porques", "espina_pescado", "texto_libre"] | None = None
    active: bool | None = None


class MetodologiaRead(MetodologiaBase, OrmBase):
    id: UUID
    tenant_id: UUID


# ── El informe de auditoria (RF-101, #42) ────────────────────────────────


CLASIFICACIONES_DE_PROCESO = (
    "conforme",
    "conforme_con_observaciones",
    "no_conforme",
    "no_auditado",
)


class VeredictoDeProcesoBase(BaseModel):
    """Lo que el auditor escribe sobre un proceso. Lo derivable no va aca."""

    process_id: UUID
    classification: Literal[
        "conforme", "conforme_con_observaciones", "no_conforme", "no_auditado"
    ]
    conclusion: str | None = None
    #: Que tuvo a la vista. Va escrito y no derivado porque "el registro de
    #: calibracion de marzo" no esta en ninguna tabla.
    evidence_reviewed: str | None = None


class VeredictoDeProcesoCreateAnidado(VeredictoDeProcesoBase):
    """Lo que viaja en el cuerpo. **Sin `audit_id`, que sale de la URL.**

    Aceptarlo del cuerpo dejaria crear un veredicto bajo `/audits/{A}/procesos`
    y guardarlo en la auditoria B: la jerarquia de la URL seria decorativa.
    Misma separacion que `AuditItemCreateAnidado`.
    """


class VeredictoDeProcesoCreate(VeredictoDeProcesoBase):
    """La forma completa, que es la que llega al CRUD."""

    audit_id: UUID


class VeredictoDeProcesoUpdate(BaseModel):
    classification: (
        Literal["conforme", "conforme_con_observaciones", "no_conforme", "no_auditado"]
        | None
    ) = None
    conclusion: str | None = None
    evidence_reviewed: str | None = None


class VeredictoDeProcesoRead(VeredictoDeProcesoBase, OrmBase):
    id: UUID
    audit_id: UUID
    tenant_id: UUID


class FilaDeLaMatriz(BaseModel):
    """Una fila del informe. **Mezcla derivado y escrito**, y conviene saber cual.

    `clausulas_auditadas`, `items*` y `hallazgos` se calculan al pedir el
    informe; `clasificacion`, `conclusion` y `evidencia_revisada` las escribio
    el auditor. Guardar los conteos seria la forma mas corta de que el informe y
    el sistema digan cosas distintas.
    """

    proceso_id: str
    proceso_nombre: str
    clausulas_auditadas: list[str]
    items: int
    items_conformes: int
    items_no_conformes: int
    hallazgos: list[str]
    #: `no_auditado` cuando el auditor no dejo veredicto. **Es un valor, no una
    #: ausencia**: "no lo miramos" es informacion para el dueno del proceso.
    clasificacion: str
    conclusion: str | None
    evidencia_revisada: str | None


class ResumenDelInforme(BaseModel):
    procesos_auditados: int
    #: Preguntas que no son de ningun proceso: requisitos generales del sistema
    #: de gestion. Van aparte y no repartidas.
    items_sin_proceso: int
    no_conformidades: int
    observaciones: int
    oportunidades_de_mejora: int
    #: `null` cuando no se evaluo ni una pregunta — **no 0 %**. Mismo criterio
    #: que `CoberturaDeAuditoria.porcentaje`.
    conformidad: float | None


class InformeDeAuditoria(BaseModel):
    audit_id: str
    codigo: str
    titulo: str
    estado: str
    resumen: ResumenDelInforme
    matriz: list[FilaDeLaMatriz]
    #: `null` en tres casos que **no son cero**: no hay auditoria anterior, la
    #: anterior no dejo hallazgos, o no esta cerrada. Un 0 % ahi se leeria como
    #: "no cerraron nada", que es una acusacion.
    tasa_de_cierre_del_ciclo_anterior: float | None
    #: Cual de los tres casos. Sin esto, el `null` obliga a adivinar.
    motivo_sin_tasa: str | None
    auditoria_anterior_id: str | None
