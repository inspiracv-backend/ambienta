from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..crud.notifications import crud_notification, crud_notification_rule, crud_notification_template
from ..deps import get_tenant_db, get_tenant_id
from ._comun import borrar_o_404
from ..schemas.notifications import (
    NotificationCreate,
    NotificationRead,
    NotificationRuleCreate,
    NotificationRuleRead,
    NotificationTemplateCreate,
    NotificationTemplateRead,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=list[NotificationRead])
def list_notifications(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_notification.get_multi(db, skip=skip, limit=limit)


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
