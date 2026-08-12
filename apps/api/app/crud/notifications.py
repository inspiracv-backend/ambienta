from pydantic import BaseModel

from ..models.notifications import Notification, NotificationRule, NotificationTemplate
from ..schemas.notifications import (
    NotificationCreate,
    NotificationRuleCreate,
    NotificationTemplateCreate,
)
from .base import CRUDBase

crud_notification = CRUDBase[Notification, NotificationCreate, BaseModel](Notification)
crud_notification_rule = CRUDBase[NotificationRule, NotificationRuleCreate, BaseModel](NotificationRule)
crud_notification_template = CRUDBase[NotificationTemplate, NotificationTemplateCreate, BaseModel](NotificationTemplate)
