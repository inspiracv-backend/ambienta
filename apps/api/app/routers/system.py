from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..crud.system import crud_audit_log
from ..deps import get_tenant_db
from ._paginacion import Pagina, paginacion, recortar
from ..schemas.system import AuditLogRead

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/audit-log", response_model=list[AuditLogRead])
def list_audit_log(respuesta: Response, pagina: Pagina = Depends(paginacion), db: Session = Depends(get_tenant_db)):
    return recortar(respuesta, crud_audit_log.get_multi(db, skip=pagina.skip, limit=pagina.pedir), pagina)
