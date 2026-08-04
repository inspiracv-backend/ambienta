from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud.catalog import crud_legal_norm, crud_legal_source, crud_sector
from ..deps import get_db
from ..schemas.catalog import LegalNormRead, LegalSourceRead, SectorRead

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/sources", response_model=list[LegalSourceRead])
def list_sources(db: Session = Depends(get_db)):
    return crud_legal_source.get_multi(db)


@router.get("/sectors", response_model=list[SectorRead])
def list_sectors(db: Session = Depends(get_db)):
    return crud_sector.get_multi(db)


@router.get("/norms", response_model=list[LegalNormRead])
def list_norms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_legal_norm.get_multi(db, skip=skip, limit=limit)


@router.get("/norms/{norm_id}", response_model=LegalNormRead)
def get_norm(norm_id: UUID, db: Session = Depends(get_db)):
    obj = crud_legal_norm.get(db, norm_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Norm not found")
    return obj
