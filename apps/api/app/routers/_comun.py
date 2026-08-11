"""Piezas compartidas por los routers.

Existe para que el borrado se comporte igual en los 16 endpoints que lo
exponen. Repetir seis lineas dieciseis veces garantiza que alguna termine
distinta —un 404 que no se lanza, un commit que falta— y esas diferencias no
se ven leyendo un router aislado.
"""
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session


def validar_visible(
    crud: Any, db: Session, id: Any, *, campo: str
) -> None:
    """Comprueba que una clave foranea apunte a algo de la propia empresa.

    **Las FK de Postgres no pasan por Row Level Security.** `fk_departments_
    facility` solo exige que exista una fila en `facilities` con ese id: no
    mira el tenant. Asi que un PATCH con el `facility_id` de otra empresa pasa
    la restriccion sin problema y deja la fila apuntando fuera.

    El dano no es solo una fila incoherente. Es un **oraculo de existencia**:
    quien prueba identificadores al azar distingue "no existe" (falla la FK)
    de "existe pero es de otro" (pasa), y con eso enumera identificadores
    ajenos sin verlos nunca.

    Se resuelve leyendo el destino con la sesion del tenant: si RLS no lo ve,
    para esta empresa no existe. Un `None` se acepta sin comprobar — significa
    "sin asignar", no "asignado a algo invisible".

    422 y no 404 porque el recurso que se pide si existe: lo que esta mal es
    un dato del cuerpo.
    """
    if id is None:
        return
    if crud.get(db, id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{campo} no corresponde a un registro de esta empresa.",
        )


def validar_sin_ciclo(
    crud: Any, db: Session, *, id_propio: Any, id_padre: Any, campo: str
) -> None:
    """Impide que un arbol se cierre sobre si mismo.

    Nada en el esquema lo evita: no hay CHECK contra `parent = id` propio ni
    contra A→B→A. Un ciclo no rompe el INSERT — rompe a quien recorra el arbol
    despues, y lo hace colgandose, que es la peor forma de enterarse.

    Se camina hacia arriba en vez de hacia abajo porque la cadena de padres
    es un solo camino, mientras que los hijos se ramifican.
    """
    if id_padre is None:
        return
    if id_propio is not None and id_padre == id_propio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{campo}: un registro no puede ser su propio padre.",
        )

    visitados = {id_propio}
    actual = id_padre
    while actual is not None:
        if actual in visitados:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{campo}: la jerarquia formaria un ciclo.",
            )
        visitados.add(actual)
        fila = crud.get(db, actual)
        if fila is None:
            return  # `validar_visible` ya se encarga de este caso
        actual = getattr(fila, campo, None)


def obtener_o_404(crud: Any, db: Session, id: Any, *, recurso: str) -> Any:
    """Una fila por id, o 404.

    `crud.get()` ya excluye lo borrado, asi que un recurso dado de baja
    responde 404 y no una fila fantasma. Un recurso de otra empresa tambien
    responde 404: Row Level Security hace que ni siquiera se vea, de modo que
    la API nunca confirma que ese identificador exista en otro lado.
    """
    obj = crud.get(db, id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{recurso} not found"
        )
    return obj


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
