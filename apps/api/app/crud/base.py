"""CRUD generico reutilizable para cualquier modelo con tenant_id.

Los 26 recursos de la API son instancias directas de `CRUDBase`, sin
sobreescribir nada, asi que lo que se decida aca vale para todos. Es la razon
por la que este archivo merece leerse entero antes de tocarlo.

**El borrado es logico, no fisico.** El esquema lo tenia previsto —`deleted_at`
en 38 tablas, con indices parciales `WHERE deleted_at IS NULL`— pero el CRUD lo
ignoraba: `remove()` hacia `db.delete()` y las lecturas no filtraban nada. Las
dos mitades estaban mal y se tapaban entre si, porque ningun router exponia el
borrado. Al exponerlo, una fila borrada habria seguido apareciendo en los
listados.

Borrar en firme ademas dejaria huerfano el registro de auditoria, que
referencia esas filas y que RNF-25 exige conservar.
"""
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]):
        self.model = model

    @property
    def usa_borrado_logico(self) -> bool:
        """Si el modelo lleva `deleted_at`.

        No lo llevan las tablas de union —permisos de un rol, sectores de una
        norma— donde quitar la fila **es** la operacion: no se conserva el
        rastro de un permiso revocado, se revoca.
        """
        return hasattr(self.model, "deleted_at")

    def _visibles(self):
        """`SELECT` que excluye lo borrado. Punto unico para no olvidarlo."""
        stmt = select(self.model)
        if self.usa_borrado_logico:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    def _columna_id(self):
        """La clave primaria simple. Falla claro si el modelo no tiene una.

        `CRUDBase` asume `id` unico porque los 26 recursos de la API se
        direccionan asi: `/recurso/{id}`. Hay una excepcion en el repositorio
        —`EquipmentOperator`, con clave compuesta (equipment_id, user_id)— que
        hoy no la usa ningun router. Si alguien la conecta, mejor un mensaje
        que diga que hacer que un AttributeError a mitad de una consulta.
        """
        columna = getattr(self.model, "id", None)
        if columna is None:
            raise NotImplementedError(
                f"{self.model.__name__} no tiene columna `id`: su clave es "
                "compuesta. CRUDBase direcciona por id simple; este modelo "
                "necesita su propio CRUD."
            )
        return columna

    def get(self, db: Session, id: Any) -> ModelType | None:
        """Una fila por id, salvo que este borrada.

        Va por `select` y no por `db.get()` porque este ultimo resuelve por
        clave primaria y por el mapa de identidad, sin pasar por un `WHERE`
        donde filtrar `deleted_at`.
        """
        return db.scalar(self._visibles().where(self._columna_id() == id))

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        return list(db.scalars(self._visibles().offset(skip).limit(limit)).all())

    def create(
        self, db: Session, *, obj_in: CreateSchemaType, tenant_id: UUID | None = None
    ) -> ModelType:
        data = obj_in.model_dump(exclude_unset=True)
        if tenant_id is not None:
            data["tenant_id"] = tenant_id
        obj = self.model(**data)
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def update(
        self, db: Session, *, db_obj: ModelType, obj_in: UpdateSchemaType
    ) -> ModelType:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> ModelType | None:
        """Marca la fila como borrada. `None` si no habia nada que borrar.

        Borrar dos veces no es un error ni mueve la fecha original: `get()` ya
        no la encuentra, asi que el segundo intento devuelve `None` y el router
        responde 404. Borrar algo ya borrado y "no existe" son lo mismo visto
        desde afuera.

        La marca la pone la base con `now()`, no Python: asi la hora es la del
        servidor de datos y es comparable con `created_at` y `updated_at`, que
        ya se generan ahi.
        """
        obj = self.get(db, id)
        if obj is None:
            return None

        if self.usa_borrado_logico:
            obj.deleted_at = func.now()
        else:
            db.delete(obj)

        db.flush()
        return obj
