from ..models.compliance import ArticleCompliance, MatrixNorm, TenantLegalMatrix
from ..schemas.compliance import (
    ArticleComplianceCreate,
    ArticleComplianceUpdate,
    MatrixNormCreate,
    MatrixNormUpdate,
    TenantLegalMatrixCreate,
    TenantLegalMatrixUpdate,
)
from .base import CRUDBase

crud_matrix = CRUDBase[TenantLegalMatrix, TenantLegalMatrixCreate, TenantLegalMatrixUpdate](TenantLegalMatrix)
crud_matrix_norm = CRUDBase[MatrixNorm, MatrixNormCreate, MatrixNormUpdate](MatrixNorm)
crud_article_compliance = CRUDBase[ArticleCompliance, ArticleComplianceCreate, ArticleComplianceUpdate](ArticleCompliance)
