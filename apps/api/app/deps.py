"""Dependencias compartidas de FastAPI."""
from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant_id(x_tenant_id: str = Header(...)) -> UUID:
    try:
        return UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header must be a valid UUID",
        )


def get_tenant_db(
    tenant_id: UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> Generator[Session, None, None]:
    db.execute(text("SET LOCAL ROLE ambienta_app"))
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    yield db
