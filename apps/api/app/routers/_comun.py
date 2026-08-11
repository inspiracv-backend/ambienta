"""Piezas compartidas por los routers.

Existe para que el borrado se comporte igual en los 16 endpoints que lo
exponen. Repetir seis lineas dieciseis veces garantiza que alguna termine
distinta —un 404 que no se lanza, un commit que falta— y esas diferencias no
se ven leyendo un router aislado.
"""
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session


class CRUDAsociacion:
    """CRUD para tablas de union con clave compuesta.

    `CRUDBase` direcciona por columna `id` simple y lanza `NotImplementedError`
    sobre estas tablas — a proposito, para que nadie las conecte por accidente.
    Pero `audit_participants`, `equipment_operators` y `facility_processes` si
    necesitan API: son relaciones **con atributos propios** (el rol en la
    auditoria, la certificacion del operador, la vigencia del proceso en la
    planta), no simples enlaces.

    Se exponen anidadas bajo su padre, que es lo que corresponde: un
    participante no existe fuera de su auditoria. El padre sale del path y el
    hijo del path o del cuerpo, asi que la clave compuesta nunca hay que
    serializarla en una URL.

    El borrado es logico, igual que en `CRUDBase`: estas tablas tambien tienen
    `deleted_at` y su historial importa — quien participo en una auditoria es
    parte del registro de esa auditoria.
    """

    def __init__(self, model: Any, campo_padre: str, campo_hijo: str):
        self.model = model
        self.campo_padre = campo_padre
        self.campo_hijo = campo_hijo

    def _visibles(self, padre_id: UUID):
        return select(self.model).where(
            getattr(self.model, self.campo_padre) == padre_id,
            self.model.deleted_at.is_(None),
        )

    def listar(self, db: Session, padre_id: UUID) -> list[Any]:
        return list(db.scalars(self._visibles(padre_id)).all())

    def obtener(self, db: Session, padre_id: UUID, hijo_id: UUID) -> Any | None:
        return db.scalar(
            self._visibles(padre_id).where(
                getattr(self.model, self.campo_hijo) == hijo_id
            )
        )

    def _obtener_incluso_borrado(
        self, db: Session, padre_id: UUID, hijo_id: UUID
    ) -> Any | None:
        return db.scalar(
            select(self.model).where(
                getattr(self.model, self.campo_padre) == padre_id,
                getattr(self.model, self.campo_hijo) == hijo_id,
            )
        )

    def crear(
        self, db: Session, *, padre_id: UUID, hijo_id: UUID, datos: Any, tenant_id: UUID
    ) -> Any:
        """Agrega el vinculo, o **reinstala** uno que se habia quitado.

        La clave primaria de estas tablas es `(padre, hijo)` y **no es parcial
        sobre `deleted_at`**: una fila dada de baja sigue ocupando la clave.
        Insertar de nuevo la misma pareja choca contra una fila que el usuario
        no puede ver, y sale un 500 por violacion de unicidad.

        Y volver a agregar algo que se quito no es un caso raro aca: es lo
        normal. Una persona se reincorpora a una auditoria, un proceso vuelve a
        una planta, un operador recupera su certificacion. Por eso se reinstala
        la fila existente en vez de rechazar la operacion — y con los datos
        nuevos, no los viejos: quien la vuelve a agregar esta declarando las
        condiciones de ahora.
        """
        campos = datos.model_dump(exclude_unset=True)
        # El padre y el hijo salen del path, nunca del cuerpo: si vinieran del
        # cuerpo, la URL diria una cosa y la fila otra.
        campos.pop(self.campo_padre, None)
        campos.pop(self.campo_hijo, None)

        previa = self._obtener_incluso_borrado(db, padre_id, hijo_id)
        if previa is not None:
            for campo, valor in campos.items():
                setattr(previa, campo, valor)
            previa.deleted_at = None
            db.flush()
            db.refresh(previa)
            return previa

        obj = self.model(
            **campos,
            **{self.campo_padre: padre_id, self.campo_hijo: hijo_id},
            tenant_id=tenant_id,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def actualizar(self, db: Session, *, db_obj: Any, datos: Any) -> Any:
        for campo, valor in datos.model_dump(exclude_unset=True).items():
            setattr(db_obj, campo, valor)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def borrar(self, db: Session, *, padre_id: UUID, hijo_id: UUID) -> Any | None:
        obj = self.obtener(db, padre_id, hijo_id)
        if obj is None:
            return None
        obj.deleted_at = func.now()
        db.flush()
        return obj


def listar_por_padre(model: Any, db: Session, padre_id: UUID, *, campo: str) -> list[Any]:
    """Listado de hijos de un padre, excluyendo lo borrado.

    Existe porque `CRUDBase.get_multi` no filtra por ninguna columna, asi que
    cualquier listado acotado hay que escribirlo a mano — y ahi es facil
    olvidar `deleted_at` y devolver filas dadas de baja.
    """
    stmt = select(model).where(
        getattr(model, campo) == padre_id, model.deleted_at.is_(None)
    )
    return list(db.scalars(stmt).all())


def verificar_padre(obj: Any, padre_id: UUID, *, campo: str) -> Any:
    """Comprueba que el hijo pertenezca al padre de la URL.

    **Anidar la ruta no ata el hijo al padre.** `CRUDBase.get` resuelve por id
    a secas, asi que `/documents/{A}/entidades/{X}` devolveria X aunque X
    pertenezca al documento B. La jerarquia de la URL seria decorativa.

    404 y no 403: bajo ese padre, ese hijo no existe.
    """
    if getattr(obj, campo) != padre_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
    return obj


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
