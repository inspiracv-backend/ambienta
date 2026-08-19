from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.compliance import crud_article_compliance, crud_matrix, crud_matrix_norm
from ..deps import get_tenant_db, get_tenant_id
from ..services.normativa_aplicable import calcular as calcular_normativa_aplicable
from ..services.resumen_cumplimiento import resumir as resumir_cumplimiento
from ..services.sincronizar_matriz import (
    desactualizadas as normas_desactualizadas,
    sincronizar as sincronizar_matriz,
)
from ._comun import borrar_o_404, obtener_o_404
from ..schemas.compliance import (
    NormaAplicableRead,
    NormativaAplicableRead,
    ConteoRead,
    NormaDesactualizadaRead,
    ResumenDeMatrizRead,
    ResumenPorInstalacionRead,
    ResumenPorNormaRead,
    SincronizacionRead,
    ArticleComplianceCreate,
    ArticleComplianceRead,
    ArticleComplianceUpdate,
    MatrixNormCreate,
    MatrixNormRead,
    MatrixNormUpdate,
    TenantLegalMatrixCreate,
    TenantLegalMatrixRead,
    TenantLegalMatrixUpdate,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/matrices", response_model=list[TenantLegalMatrixRead])
def list_matrices(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_matrix.get_multi(db, skip=skip, limit=limit)


@router.get("/matrices/{matrix_id}", response_model=TenantLegalMatrixRead)
def get_matrix(matrix_id: UUID, db: Session = Depends(get_tenant_db)):
    obj = crud_matrix.get(db, matrix_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix not found")
    return obj


@router.post("/matrices", response_model=TenantLegalMatrixRead, status_code=status.HTTP_201_CREATED)
def create_matrix(
    data: TenantLegalMatrixCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_matrix.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/matrices/{matrix_id}", response_model=TenantLegalMatrixRead)
def update_matrix(matrix_id: UUID, data: TenantLegalMatrixUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_matrix.get(db, matrix_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix not found")
    obj = crud_matrix.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/matrix-norms", response_model=list[MatrixNormRead])
def list_matrix_norms(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_matrix_norm.get_multi(db, skip=skip, limit=limit)


@router.post("/matrix-norms", response_model=MatrixNormRead, status_code=status.HTTP_201_CREATED)
def create_matrix_norm(
    data: MatrixNormCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_matrix_norm.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/matrix-norms/{mn_id}", response_model=MatrixNormRead)
def update_matrix_norm(mn_id: UUID, data: MatrixNormUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_matrix_norm.get(db, mn_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix norm not found")
    obj = crud_matrix_norm.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.get("/article-compliance", response_model=list[ArticleComplianceRead])
def list_article_compliance(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_article_compliance.get_multi(db, skip=skip, limit=limit)


@router.post("/article-compliance", response_model=ArticleComplianceRead, status_code=status.HTTP_201_CREATED)
def create_article_compliance(
    data: ArticleComplianceCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_article_compliance.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.patch("/article-compliance/{ac_id}", response_model=ArticleComplianceRead)
def update_article_compliance(ac_id: UUID, data: ArticleComplianceUpdate, db: Session = Depends(get_tenant_db)):
    obj = crud_article_compliance.get(db, ac_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article compliance not found")
    obj = crud_article_compliance.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


# ── Business Logic ──────────────────────────────────────────────────────

@router.get("/matrices/{matrix_id}/stats", tags=["business-logic"])
def matrix_stats(matrix_id: UUID, db: Session = Depends(get_tenant_db)):
    from ..services.compliance import get_compliance_stats
    try:
        return get_compliance_stats(db, matrix_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/article-compliance/{ac_id}/evaluate", response_model=ArticleComplianceRead, tags=["business-logic"])
def evaluate(
    ac_id: UUID,
    answer: str,
    compliance_method: str | None = None,
    evidence_url: str | None = None,
    db: Session = Depends(get_tenant_db),
):
    from ..services.compliance import evaluate_article
    try:
        obj = evaluate_article(db, ac_id, answer, compliance_method, evidence_url)
        db.commit()
        return obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/matrices/{matrix_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_matrix(matrix_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una matriz legal de un periodo. Las evaluaciones por articulo
    quedan: son el historial de cumplimiento, no un detalle de la matriz."""
    borrar_o_404(crud_matrix, db, matrix_id, recurso="Matrix")


@router.delete("/matrix-norms/{mn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_matrix_norm(mn_id: UUID, db: Session = Depends(get_tenant_db)):
    """Saca una norma de la matriz: deja de aplicarle a la empresa."""
    borrar_o_404(crud_matrix_norm, db, mn_id, recurso="MatrixNorm")


@router.delete("/article-compliance/{ac_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article_compliance(ac_id: UUID, db: Session = Depends(get_tenant_db)):
    borrar_o_404(crud_article_compliance, db, ac_id, recurso="ArticleCompliance")


@router.get("/matrix-norms/{mn_id}", response_model=MatrixNormRead)
def get_matrix_norm(mn_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_matrix_norm, db, mn_id, recurso="MatrixNorm")


@router.get("/article-compliance/{ac_id}", response_model=ArticleComplianceRead)
def get_article_compliance(ac_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_article_compliance, db, ac_id, recurso="ArticleCompliance")


# ── Normativa aplicable a la empresa (RF-19) ──────────────────────────────


@router.get("/normativa-aplicable", response_model=NormativaAplicableRead)
def get_normativa_aplicable(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Que normas le corresponden a esta empresa segun su perfil.

    **No escribe nada.** Calcular y aplicar son operaciones distintas a
    proposito: el negocio pidio "un check de normativas recomendadas", y un
    check es una revision humana antes de comprometer. Generar la matriz de
    golpe le daria a la empresa cientos de articulos que evaluar sin que nadie
    mirara si tienen sentido.

    Las normas vienen separadas en **obligatorias** —aplicabilidad directa— y
    **recomendadas** —indirecta o referencial—, y cada una dice que sector y que
    nivel la hicieron entrar.

    ## Por que `estado` y no solo la lista

    Una lista vacia tiene dos causas opuestas: que la empresa no haya declarado
    su sector, o que nadie haya clasificado las normas de ese sector todavia.
    **Ninguna significa que la empresa no tenga obligaciones**, y devolver solo
    la lista dejaria que la pantalla mostrara "0 normas" en los tres casos.
    """
    r = calcular_normativa_aplicable(db, tenant_id)
    return NormativaAplicableRead(
        estado=r.estado,
        sector_id=r.sector_id,
        obligatorias=[NormaAplicableRead(**vars(n)) for n in r.obligatorias],
        recomendadas=[NormaAplicableRead(**vars(n)) for n in r.recomendadas],
        total=r.total,
    )


@router.post(
    "/matrices/{matrix_id}/sincronizar",
    response_model=SincronizacionRead,
    tags=["business-logic"],
)
def sincronizar_la_matriz(
    matrix_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    """Lleva a la matriz la normativa que hoy le corresponde a la empresa.

    **Se sincroniza, no se reemplaza.** Agrega lo que falta y nunca borra: lo
    que dejo de corresponder se marca como no aplicable con su motivo, porque
    borrarlo eliminaria la evidencia de que en su momento se evaluo — que es lo
    que pide un fiscalizador al revisar un periodo pasado.

    Lo agregado a mano se respeta siempre: que el calculo no encuentre una norma
    no significa que no aplique, puede venir de un contrato o de la RCA.

    Los articulos entran **sin evaluar**, no incumplidos. No haber evaluado no
    es incumplir, y contarlo asi hundiria el porcentaje de la empresa el dia que
    se le carga la matriz.

    Es idempotente: correrlo dos veces deja el mismo estado.
    """
    if not crud_matrix.get(db, matrix_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix not found")

    r = sincronizar_matriz(db, matrix_id, tenant_id)
    db.commit()
    return SincronizacionRead(**vars(r))


@router.get(
    "/matrices/{matrix_id}/desactualizadas",
    response_model=list[NormaDesactualizadaRead],
)
def listar_desactualizadas(matrix_id: UUID, db: Session = Depends(get_tenant_db)):
    """Normas de la matriz que se evaluaron contra una version que ya no rige.

    **Compara versiones, no fechas.** Una norma puede tener correcciones que no
    cambian el articulado; el esquema ya distingue versiones por contenido, asi
    que usar fechas reintroduciria falsos positivos que el versionado evita.

    **Las evaluaciones sobre la version anterior siguen visibles y validas.** Se
    hicieron sobre el texto que regia entonces, y esa es la respuesta correcta
    ante una auditoria de ese periodo. Esto avisa; no migra ni invalida nada.
    """
    if not crud_matrix.get(db, matrix_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix not found")

    return [NormaDesactualizadaRead(**vars(n)) for n in normas_desactualizadas(db, matrix_id)]


def _conteo(c) -> ConteoRead:
    return ConteoRead(
        cumplen=c.cumplen,
        no_cumplen=c.no_cumplen,
        sin_evaluar=c.sin_evaluar,
        no_aplican=c.no_aplican,
        excluidos=c.excluidos,
        evaluables=c.evaluables,
        porcentaje=c.porcentaje,
    )


@router.get("/matrices/{matrix_id}/resumen", response_model=ResumenDeMatrizRead)
def resumen_de_la_matriz(matrix_id: UUID, db: Session = Depends(get_tenant_db)):
    """Como va el cumplimiento, desglosado por norma y por instalacion.

    ## Que entra al porcentaje

    El denominador son los articulos que la empresa **debe cumplir**. Quedan
    fuera los **excluidos del calculo** (RF-24) —sin esto la exclusion seria
    decorativa— y los marcados **no aplicables**: un articulo que no le toca a
    la empresa no es una obligacion suya, y contarlo la penalizaria.

    `partial` cuenta como **no cumplido**: dar por cumplido lo que se cumple a
    medias sobreestima el porcentaje ante un auditor.

    `pending` **si** cuenta en el denominador. No haber evaluado no es
    incumplir, pero tampoco es cumplir — dejarlo fuera daria 100 % a una empresa
    que no evaluo nada.

    ## Cuando no hay nada que medir

    `porcentaje` es **`null`, no cero**. Cero significa "no cumple nada"; `null`
    significa "todavia no hay obligaciones que evaluar".
    """
    if not crud_matrix.get(db, matrix_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matrix not found")

    r = resumir_cumplimiento(db, matrix_id)
    return ResumenDeMatrizRead(
        total=_conteo(r.total),
        por_norma=[
            ResumenPorNormaRead(
                norm_id=n.norm_id,
                matrix_norm_id=n.matrix_norm_id,
                title=n.title,
                applicability=n.applicability,
                conteo=_conteo(n.conteo),
            )
            for n in r.por_norma
        ],
        por_instalacion=[
            ResumenPorInstalacionRead(
                facility_id=p.facility_id, nombre=p.nombre, conteo=_conteo(p.conteo)
            )
            for p in r.por_instalacion
        ],
    )
