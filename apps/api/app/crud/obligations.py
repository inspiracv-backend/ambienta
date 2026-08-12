from pydantic import BaseModel

from ..models.obligations import (
    DeclarationSubmission,
    DeclarationTemplate,
    Obligation,
    ObligationTemplate,
    Task,
)
from ..schemas.obligations import (
    DeclarationSubmissionCreate,
    DeclarationSubmissionUpdate,
    ObligationCreate,
    ObligationUpdate,
    TaskCreate,
    TaskUpdate,
)
from .base import CRUDBase

crud_obligation_template = CRUDBase[ObligationTemplate, BaseModel, BaseModel](ObligationTemplate)
crud_obligation = CRUDBase[Obligation, ObligationCreate, ObligationUpdate](Obligation)
crud_task = CRUDBase[Task, TaskCreate, TaskUpdate](Task)
crud_declaration_template = CRUDBase[DeclarationTemplate, BaseModel, BaseModel](DeclarationTemplate)
crud_declaration_submission = CRUDBase[DeclarationSubmission, DeclarationSubmissionCreate, DeclarationSubmissionUpdate](DeclarationSubmission)
