from pydantic import BaseModel

from ..models.catalog import (
    FacilityNormAssignment,
    LegalArticle,
    LegalNorm,
    LegalNormVersion,
    LegalSource,
    Sector,
)
from ..schemas.catalog import (
    FacilityNormAssignmentCreate,
    LegalArticleCreate,
    LegalNormCreate,
    LegalNormUpdate,
    LegalNormVersionCreate,
)
from .base import CRUDBase

crud_legal_source = CRUDBase[LegalSource, BaseModel, BaseModel](LegalSource)
crud_sector = CRUDBase[Sector, BaseModel, BaseModel](Sector)
crud_legal_norm = CRUDBase[LegalNorm, LegalNormCreate, LegalNormUpdate](LegalNorm)
crud_legal_norm_version = CRUDBase[LegalNormVersion, LegalNormVersionCreate, BaseModel](LegalNormVersion)
crud_legal_article = CRUDBase[LegalArticle, LegalArticleCreate, BaseModel](LegalArticle)
crud_facility_norm_assignment = CRUDBase[FacilityNormAssignment, FacilityNormAssignmentCreate, BaseModel](FacilityNormAssignment)
