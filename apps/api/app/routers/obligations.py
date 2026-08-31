from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..crud.obligations import crud_obligation, crud_task
from ..deps import get_tenant_db, get_tenant_id
from ..crud.compliance import crud_article_compliance, crud_matrix_norm
from ._paginacion import Pagina, paginacion, recortar
from ._comun import borrar_o_404, obtener_o_404, validar_visible
from ..schemas.obligations import (
    AprobarDeclaracion,
    ObligationConUrgencia,
    ObligationCreate,
    RechazarDeclaracion,
    RegistrarFolio,
    VincularAMatriz,
    ObligationRead,
    ObligationUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)

router = APIRouter(prefix="/obligations", tags=["obligations"])


def _con_urgencia(obligaciones: list) -> list[dict]:
    """Le pega el semaforo a cada obligacion, en una sola pasada.

    `datetime.now()` se toma **una vez para todo el listado**. Calcularlo por
    fila haria que dos obligaciones con el mismo vencimiento salieran en niveles
    distintos si el reloj cruza la medianoche a mitad de la consulta — raro,
    pero cuando pasa es imposible de reproducir.
    """
    from datetime import datetime, timezone

    from ..services.declaracion import urgencia

    ahora = datetime.now(timezone.utc)
    salida = []
    for o in obligaciones:
        u = urgencia(o, ahora)
        fila = ObligationRead.model_validate(o).model_dump()
        fila["urgencia"] = u.nivel
        fila["dias_restantes"] = u.dias_restantes
        salida.append(fila)
    return salida


@router.get(
    "/",
    response_model=list[ObligationConUrgencia],
    summary="Las declaraciones de la empresa, con su semaforo",
    description=(
        "Cada obligacion viene con `urgencia` y `dias_restantes` calculados por "
        "el servidor (#113).\n\n"
        "Los cinco niveles: `resuelta`, `vencida`, `critica` (3 dias o menos), "
        "`proxima` (15 o menos), `vigente`, y `sin_plazo` para las que no tienen "
        "fecha — que no es lo mismo que ir bien, y por eso no se pinta de verde."
    ),
)
def list_obligations(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return _con_urgencia(recortar(respuesta, crud_obligation.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina))


@router.get("/{obligation_id}", response_model=ObligationRead)
def get_obligation(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_obligation.get(db, obligation_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")
    return obj


@router.post("/", response_model=ObligationRead, status_code=status.HTTP_201_CREATED)
def create_obligation(
    data: ObligationCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    # **Las claves foraneas no pasan por RLS.** Sin estas dos lineas, una
    # empresa podia colgar su obligacion de la evaluacion de otra: medido antes
    # de escribirlas, un id inventado daba 422 y uno real ajeno daba **201**.
    validar_visible(crud_article_compliance, db, data.article_compliance_id,
                    campo="article_compliance_id")
    validar_visible(crud_matrix_norm, db, data.matrix_norm_id, campo="matrix_norm_id")

    obj = crud_obligation.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/{obligation_id}", response_model=ObligationRead)
def update_obligation(obligation_id: UUID, data: ObligationUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_obligation.get(db, obligation_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found")
    # `ObligationUpdate` no declara las claves foraneas, asi que `getattr` con
    # `None` por defecto: pedirlas directo seria un AttributeError el dia que
    # alguien las agregue o las quite.
    validar_visible(crud_article_compliance, db, getattr(data, "article_compliance_id", None),
                    campo="article_compliance_id")
    validar_visible(crud_matrix_norm, db, getattr(data, "matrix_norm_id", None),
                    campo="matrix_norm_id")

    # **El estado no se edita por PATCH.** Con esto abierto, la maquina de
    # estados de `services/declaracion.py` era decorativa: un PATCH podia poner
    # `accepted` directo, sin folio y sin haber presentado nada. La declaracion
    # quedaba aceptada en pantalla y sin comprobante que mostrar.
    if data.status is not None and data.status != obj.status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El estado de una declaracion no se edita: se mueve con "
                "/submit, /approve y /reject, que comprueban que la transicion "
                "exista y que haya folio antes de aceptar."
            ),
        )

    obj = crud_obligation.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Vinculo con la Matriz Legal (RF-14) ──────────────────────────────────

@router.put(
    "/{obligation_id}/matrix-link",
    response_model=ObligationRead,
    tags=["business-logic"],
    summary="Vincular la obligacion a un articulo de la Matriz Legal",
    description=(
        "Ata una obligacion existente al articulo que la origina (RF-14): el "
        "sentido inverso a generarla desde la matriz.\n\n"
        "La norma y la planta se **reescriben** desde la evaluacion, para que "
        "las tres referencias no puedan contradecirse. Un articulo de otra "
        "empresa responde 422, igual que uno inexistente — distinguirlos "
        "permitiria enumerar identificadores ajenos."
    ),
)
def vincular_a_matriz(
    obligation_id: UUID,
    data: VincularAMatriz,
    db: Session = Depends(get_tenant_db),
):
    from ..services.vinculo_matriz_obligacion import EvaluacionInvisible, vincular

    obj = obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")
    try:
        obj = vincular(db, obligacion=obj, article_compliance_id=data.article_compliance_id)
    except EvaluacionInvisible as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    db.commit()
    return obj


@router.delete(
    "/{obligation_id}/matrix-link",
    response_model=ObligationRead,
    tags=["business-logic"],
    summary="Soltar la obligacion de la Matriz Legal",
    description=(
        "Quita el vinculo **sin borrar la obligacion**: sigue existiendo y "
        "venciendo. Lo que se pierde es la trazabilidad hacia el requisito que "
        "la origino, y por eso es una operacion propia y no un efecto colateral "
        "de editar un campo cualquiera.\n\n"
        "Responde 200 con la obligacion ya suelta, y no 204, porque el recurso "
        "sigue existiendo y quien llama necesita ver como quedo."
    ),
)
def desvincular_de_matriz(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    from ..services.vinculo_matriz_obligacion import desvincular

    obj = obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")
    obj = desvincular(db, obligacion=obj)
    db.commit()
    return obj


# ── Tasks ────────────────────────────────────────────────────────────────

@router.get("/{obligation_id}/tasks", response_model=list[TaskRead])
def list_tasks(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    from sqlalchemy import select
    from ..models.obligations import Task
    stmt = select(Task).where(Task.obligation_id == obligation_id)
    return list(db.scalars(stmt).all())


@router.post("/{obligation_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    obligation_id: UUID,
    data: TaskCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    # La obligacion sale del path y **se ignora la del cuerpo**: si vinieran las
    # dos, la URL diria una cosa y la fila otra.
    obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")

    task_data = data.model_dump(exclude_unset=True)
    task_data["obligation_id"] = obligation_id

    # Misma historia que `article_compliance_id`: las claves foraneas no pasan
    # por RLS, asi que `parent_task_id` entraba sin comprobarse y una subtarea
    # podia colgar de la tarea de otra empresa.
    padre_id = task_data.get("parent_task_id")
    validar_visible(crud_task, db, padre_id, campo="parent_task_id")
    if padre_id is not None:
        padre = crud_task.get(db, padre_id)
        if padre is not None and padre.obligation_id != obligation_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "parent_task_id pertenece a otra obligacion. Una subtarea no "
                    "puede colgar de la tarea de otra declaracion: el arbol "
                    "quedaria cruzado entre dos megaproyectos."
                ),
            )

    from ..models.obligations import Task
    obj = Task(**task_data, tenant_id=tenant_id)
    db.add(obj)
    db.flush()
    db.refresh(obj)
    db.commit()
    return obj


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: UUID, data: TaskUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_task.get(db, task_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    obj = crud_task.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Business Logic ──────────────────────────────────────────────────────

@router.get("/upcoming/", response_model=list[ObligationRead], tags=["business-logic"])
def list_upcoming(
    days: int = 30,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..services.obligations import get_upcoming_obligations
    return get_upcoming_obligations(db, tenant_id, days)


@router.get("/overdue/", response_model=list[ObligationRead], tags=["business-logic"])
def list_overdue(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..services.obligations import get_overdue_obligations
    return get_overdue_obligations(db, tenant_id)


@router.post(
    "/{obligation_id}/submit",
    response_model=ObligationRead,
    tags=["business-logic"],
    summary="Presentar la declaracion",
    description=(
        "Marca la declaracion como presentada y la deja esperando revision "
        "(RF-31).\n\n"
        "Las transiciones validas se declaran en un solo lugar "
        "(`services/declaracion.py::TRANSICIONES`). Un flujo repartido en un "
        "`if` por endpoint termina permitiendo, en alguno, un salto que los "
        "otros prohiben."
    ),
)
def submit(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    from ..services.declaracion import ErrorDeDeclaracion, enviar

    obj = obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")
    try:
        obj = enviar(db, obligacion=obj)
    except ErrorDeDeclaracion as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    return obj


@router.post(
    "/{obligation_id}/approve",
    response_model=ObligationRead,
    tags=["business-logic"],
    summary="Aceptar la declaracion presentada",
    description=(
        "Cierra el flujo de RF-31: la declaracion presentada se acepta.\n\n"
        "**Exige el folio** que devolvio el portal del Estado, aca o ya "
        "registrado. Es la unica prueba de que la declaracion se presento de "
        "verdad; aceptar sin el deja a la empresa con un 'listo' en pantalla y "
        "nada que mostrarle a un fiscalizador — y eso no se descubre hasta la "
        "fiscalizacion.\n\n"
        "409 si la declaracion no esta presentada: no se puede aceptar algo que "
        "nadie envio."
    ),
)
def approve(
    obligation_id: UUID,
    data: AprobarDeclaracion,
    db: Session = Depends(get_tenant_db),
):
    from ..services.declaracion import ErrorDeDeclaracion, aprobar

    obj = obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")
    try:
        obj = aprobar(db, obligacion=obj, folio=data.folio)
    except ErrorDeDeclaracion as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    return obj


@router.post(
    "/{obligation_id}/reject",
    response_model=ObligationRead,
    tags=["business-logic"],
    summary="Rechazar la declaracion presentada",
    description=(
        "Devuelve la declaracion a quien la preparo, **con el motivo**, que es "
        "obligatorio.\n\n"
        "Un rechazo sin explicacion obliga a adivinar que corregir, y mientras "
        "se adivina el plazo sigue corriendo. El motivo queda en "
        "`data.motivo_rechazo`."
    ),
)
def reject(
    obligation_id: UUID,
    data: RechazarDeclaracion,
    db: Session = Depends(get_tenant_db),
):
    from ..services.declaracion import ErrorDeDeclaracion, rechazar

    obj = obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")
    try:
        obj = rechazar(db, obligacion=obj, motivo=data.motivo)
    except ErrorDeDeclaracion as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    return obj


@router.post(
    "/{obligation_id}/fulfill",
    response_model=ObligationRead,
    tags=["business-logic"],
    summary="Registrar el folio del sistema oficial",
    description=(
        "Anota el comprobante que devolvio el portal **sin cambiar el estado** "
        "(#114).\n\n"
        "Va aparte de aceptar porque son dos momentos y a veces dos personas: "
        "quien declara copia el folio apenas lo recibe, y quien aprueba puede "
        "revisarlo otro dia.\n\n"
        "**Este endpoint respondia 422 en el 100 % de los casos.** Escribia "
        "`status = 'fulfilled'`, un valor que el CHECK de `obligations` no "
        "admite — la misma clase de error que tuvo `evaluate_article` con "
        "`'not_evaluated'`: una lista de estados escrita de memoria en vez de "
        "leida del esquema."
    ),
)
def fulfill(
    obligation_id: UUID,
    data: RegistrarFolio,
    db: Session = Depends(get_tenant_db),
):
    from ..services.declaracion import ErrorDeDeclaracion, registrar_folio

    obj = obtener_o_404(crud_obligation, db, obligation_id, recurso="Obligation")
    try:
        obj = registrar_folio(db, obligacion=obj, folio=data.folio)
    except ErrorDeDeclaracion as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    return obj


@router.post(
    "/generate-notifications/",
    tags=["business-logic"],
    summary="Generar los avisos de vencimiento que correspondan hoy",
    description=(
        "Lo que el cron diario llama (#119). **Se puede correr las veces que "
        "haga falta:** cada aviso lleva una clave con una restriccion de "
        "unicidad detras, asi que una segunda corrida no repite nada.\n\n"
        "Antes si repetia. Medido: tres corridas seguidas sobre la misma "
        "obligacion y la misma ventana dejaban **tres avisos**. El dano no es "
        "el ruido sino lo que provoca — un sistema que avisa de mas se deja de "
        "leer, y despues pasa de largo el aviso que importaba.\n\n"
        "**Las ventanas salen de `notification_rules` si la empresa las "
        "declaro**, y del defecto 15/7/3/1 si no. Una obligacion sin "
        "responsable **escala a los administradores** en vez de quedarse sin "
        "aviso, que es lo que pasaba antes: 3 de las 8 obligaciones del seed no "
        "tienen dueno y no generaban nada.\n\n"
        "Mira `sin_destinatario`: son las obligaciones que no avisaron a nadie "
        "porque la empresa no tiene ni responsable ni administrador activo."
    ),
)
def generate_notifications(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    from ..services.avisos_de_vencimiento import generar

    r = generar(db, tenant_id)
    db.commit()
    return {
        "created": r.creados,
        "skipped_duplicates": r.omitidos_por_repetidos,
        "escalated": r.escalados,
        "without_recipient": r.sin_destinatario,
        "windows_days": list(r.ventanas),
    }


@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_obligation(obligation_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una obligacion. Sus tareas quedan igual: no se cascadea el
    borrado logico, porque tratarlas juntas impediria recuperarlas por
    separado si la baja fue un error."""
    borrar_o_404(crud_obligation, db, obligation_id, recurso="Obligation")


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_task, db, task_id, recurso="Task")


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_task, db, task_id, recurso="Task")
