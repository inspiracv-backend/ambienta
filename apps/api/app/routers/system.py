from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..crud.system import crud_audit_log
from ..deps import get_tenant_db
from ..schemas.system import AuditLogRead

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/audit-log", response_model=list[AuditLogRead])
def list_audit_log(skip: int = 0, limit: int = 100, db: Session = Depends(get_tenant_db)):
    return crud_audit_log.get_multi(db, skip=skip, limit=limit)
