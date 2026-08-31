from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..crud.notifications import crud_notification, crud_notification_rule, crud_notification_template
from ..deps import get_tenant_db, get_tenant_id
from ._paginacion import Pagina, paginacion, recortar
from ._comun import borrar_o_404, obtener_o_404
from ..schemas.notifications import (
    NotificationCreate,
    NotificationRead,
    NotificationUpdate,
    NotificationRuleCreate,
    NotificationRuleRead,
    NotificationRuleUpdate,
    NotificationTemplateCreate,
    NotificationTemplateRead,
    NotificationTemplateUpdate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=list[NotificationRead])
def list_notifications(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_notification.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)


@router.post("/", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
def create_notification(
    data: NotificationCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_notification.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.get("/templates", response_model=list[NotificationTemplateRead])
def list_templates(db: Session = Depends(get_tenant_db)):
    return crud_notification_template.get_multi(db)


@router.post("/templates", response_model=NotificationTemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    data: NotificationTemplateCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_notification_template.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.get("/rules", response_model=list[NotificationRuleRead])
def list_rules(db: Session = Depends(get_tenant_db)):
    return crud_notification_rule.get_multi(db)


@router.post("/rules", response_model=NotificationRuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    data: NotificationRuleCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_tenant_db),
):
    obj = crud_notification_rule.create(db, obj_in=data, tenant_id=tenant_id)
    db.commit()
    return obj


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(notification_id: UUID, db: Session = Depends(get_tenant_db)):
    """Descarta un aviso de la bandeja de quien lo recibio."""
    borrar_o_404(crud_notification, db, notification_id, recurso="Notification")


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: UUID, db: Session = Depends(get_tenant_db)):
    """Retira una plantilla. Los avisos ya enviados no cambian: guardan su
    texto, no una referencia viva a la plantilla."""
    borrar_o_404(crud_notification_template, db, template_id, recurso="NotificationTemplate")


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: UUID, db: Session = Depends(get_tenant_db)):
    """Deja de disparar avisos para ese evento."""
    borrar_o_404(crud_notification_rule, db, rule_id, recurso="NotificationRule")


@router.get("/{notification_id}", response_model=NotificationRead)
def get_notification(notification_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_notification, db, notification_id, recurso="Notification")


@router.get("/templates/{template_id}", response_model=NotificationTemplateRead)
def get_template(template_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_notification_template, db, template_id, recurso="NotificationTemplate")


@router.get("/rules/{rule_id}", response_model=NotificationRuleRead)
def get_rule(rule_id: UUID, db: Session = Depends(get_tenant_db)):
    return obtener_o_404(crud_notification_rule, db, rule_id, recurso="NotificationRule")


@router.patch("/{notification_id}", response_model=NotificationRead)
def update_notification(notification_id: UUID, data: NotificationUpdate, db: Session = Depends(get_tenant_db)):
    """Marcar leido o cambiar el estado de un aviso."""
    obj = obtener_o_404(crud_notification, db, notification_id, recurso="Notification")
    obj = crud_notification.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.patch("/templates/{template_id}", response_model=NotificationTemplateRead)
def update_template(template_id: UUID, data: NotificationTemplateUpdate, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_notification_template, db, template_id, recurso="NotificationTemplate")
    obj = crud_notification_template.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj


@router.patch("/rules/{rule_id}", response_model=NotificationRuleRead)
def update_rule(rule_id: UUID, data: NotificationRuleUpdate, db: Session = Depends(get_tenant_db)):
    obj = obtener_o_404(crud_notification_rule, db, rule_id, recurso="NotificationRule")
    obj = crud_notification_rule.update(db, db_obj=obj, obj_in=data)
    db.commit()
    return obj
