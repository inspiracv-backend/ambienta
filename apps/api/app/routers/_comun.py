"""Piezas compartidas por los routers.

Existe para que el borrado se comporte igual en los 16 endpoints que lo
exponen. Repetir seis lineas dieciseis veces garantiza que alguna termine
distinta —un 404 que no se lanza, un commit que falta— y esas diferencias no
se ven leyendo un router aislado.
"""
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session


def borrar_o_404(crud: Any, db: Session, id: Any, *, recurso: str) -> None:
    """Borra por id. 404 si no habia nada que borrar.

    El borrado es **logico**: la fila queda con `deleted_at` y deja de
    aparecer en lecturas y listados (ver `crud/base.py`). No se elimina porque
    el registro de auditoria la referencia y RNF-25 exige conservarlo.

    Borrar algo ya borrado responde 404, igual que borrar algo que nunca
    existio: desde afuera son el mismo hecho, y distinguirlos solo serviria
    para confirmar que ese identificador fue real alguna vez.

    No devuelve nada. Los endpoints responden 204, que es lo que corresponde
    cuando no queda representacion del recurso que mostrar.
    """
    if crud.remove(db, id=id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{recurso} not found"
        )
    db.commit()
