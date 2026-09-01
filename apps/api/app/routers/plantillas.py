"""Plantillas del catalogo global: obligaciones y declaraciones.

**No llevan `tenant_id`.** Lo que se crea o edita aca lo ven TODAS las
empresas del sistema — igual que el catalogo normativo. Es la diferencia con
el resto de la API, donde Row Level Security acota cada fila a su empresa, y
por eso estos endpoints se comportan distinto:

- **Leer**: cualquier usuario autenticado. Una plantilla es informacion que la
  empresa necesita para entender que tiene que declarar.
- **Escribir**: solo Admin Global. Una empresa no puede cambiarle el catalogo
  a las demas.

Ese es el motivo por el que estas dos tablas quedaron fuera de las primeras
tandas de CRUD: no bastaba con escribir el router, habia que decidir quien
puede escribir. Aca esta decidido.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..crud.obligations import crud_declaration_template, crud_obligation_template
from ..deps import exigir_admin_global, get_current_user, get_db
from ..schemas.obligations import (
    DeclarationTemplateCreate,
    DeclarationTemplateRead,
    DeclarationTemplateUpdate,
    ObligationTemplateCreate,
    ObligationTemplateRead,
    ObligationTemplateUpdate,
)
from ._paginacion import Pagina, paginacion, recortar
from ._comun import borrar_o_404, obtener_o_404

router = APIRouter(prefix="/templates", tags=["templates"])


# ── Plantillas de obligacion ──────────────────────────────────────────────

@router.get("/obligations", response_model=list[ObligationTemplateRead])
def list_obligation_templates(
    respuesta: Response,
    pagina: Pagina = Depends(paginacion),
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return recortar(respuesta, crud_obligation_template.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.get("/obligations/{template_id}", response_model=ObligationTemplateRead)
def get_obligation_template(
    template_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return obtener_o_404(crud_obligation_template, db, template_id, recurso="ObligationTemplate")


@router.post("/obligations", response_model=ObligationTemplateRead, status_code=status.HTTP_201_CREATED)
def create_obligation_template(
    data: ObligationTemplateCreate,
    _: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    """Alta de plantilla. Solo Admin Global: afecta a todas las empresas."""
    obj = crud_obligation_template.create(db, obj_in=data)
    db.commit()
    return obj


@router.patch("/obligations/{template_id}", response_model=ObligationTemplateRead)
def update_obligation_template(
    template_id: UUID,
    data: ObligationTemplateUpdate,
    _: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    obj = obtener_o_404(crud_obligation_template, db, template_id, recurso="ObligationTemplate")
    obj = crud_obligation_template.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/obligations/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_obligation_template(
    template_id: UUID,
    _: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    """Retira una plantilla del catalogo.

    Las obligaciones ya creadas a partir de ella no se tocan: copiaron sus
    datos al crearse, no mantienen una referencia viva.
    """
    borrar_o_404(crud_obligation_template, db, template_id, recurso="ObligationTemplate")


# ── Plantillas de declaracion ─────────────────────────────────────────────

@router.get("/declarations", response_model=list[DeclarationTemplateRead])
def list_declaration_templates(
    respuesta: Response,
    pagina: Pagina = Depends(paginacion),
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return recortar(respuesta, crud_declaration_template.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.get("/declarations/{template_id}", response_model=DeclarationTemplateRead)
def get_declaration_template(
    template_id: UUID,
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return obtener_o_404(crud_declaration_template, db, template_id, recurso="DeclarationTemplate")


@router.post("/declarations", response_model=DeclarationTemplateRead, status_code=status.HTTP_201_CREATED)
def create_declaration_template(
    data: DeclarationTemplateCreate,
    _: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    obj = crud_declaration_template.create(db, obj_in=data)
    db.commit()
    return obj


@router.patch("/declarations/{template_id}", response_model=DeclarationTemplateRead)
def update_declaration_template(
    template_id: UUID,
    data: DeclarationTemplateUpdate,
    _: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    obj = obtener_o_404(crud_declaration_template, db, template_id, recurso="DeclarationTemplate")
    obj = crud_declaration_template.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.delete("/declarations/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_declaration_template(
    template_id: UUID,
    _: CurrentUser = Depends(exigir_admin_global),
    db: Session = Depends(get_db),
):
    borrar_o_404(crud_declaration_template, db, template_id, recurso="DeclarationTemplate")
