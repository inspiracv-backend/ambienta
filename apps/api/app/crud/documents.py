from pydantic import BaseModel

from ..models.documents import Document, DocumentVersion, EntityDocument
from ..schemas.documents import (
    DocumentCreate,
    DocumentUpdate,
    DocumentVersionCreate,
    EntityDocumentCreate,
)
from .base import CRUDBase

crud_document = CRUDBase[Document, DocumentCreate, DocumentUpdate](Document)
crud_document_version = CRUDBase[DocumentVersion, DocumentVersionCreate, BaseModel](DocumentVersion)
crud_entity_document = CRUDBase[EntityDocument, EntityDocumentCreate, BaseModel](EntityDocument)
