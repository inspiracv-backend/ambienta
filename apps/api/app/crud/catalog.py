from pydantic import BaseModel

from ..models.organization import Country
from ..models.catalog import (
    FacilityNormAssignment,
    LegalArticle,
    LegalNorm,
    LegalNormVersion,
    LegalSource,
    Sector,
    RetcSystem,
)
from ..schemas.catalog import (
    FacilityNormAssignmentCreate,
    LegalArticleCreate,
    LegalNormCreate,
    LegalNormUpdate,
    LegalNormVersionCreate,
)
from .base import CRUDBase

# Sin esquemas de escritura a proposito: el catalogo de paises se consulta, no
# se administra. Ver el docstring de `CountryRead`.
crud_country = CRUDBase[Country, BaseModel, BaseModel](Country)
crud_legal_source = CRUDBase[LegalSource, BaseModel, BaseModel](LegalSource)
crud_sector = CRUDBase[Sector, BaseModel, BaseModel](Sector)
crud_legal_norm = CRUDBase[LegalNorm, LegalNormCreate, LegalNormUpdate](LegalNorm)
crud_legal_norm_version = CRUDBase[LegalNormVersion, LegalNormVersionCreate, BaseModel](LegalNormVersion)
crud_legal_article = CRUDBase[LegalArticle, LegalArticleCreate, BaseModel](LegalArticle)
crud_facility_norm_assignment = CRUDBase[FacilityNormAssignment, FacilityNormAssignmentCreate, BaseModel](FacilityNormAssignment)
crud_retc_system = CRUDBase[RetcSystem, BaseModel, BaseModel](RetcSystem)
