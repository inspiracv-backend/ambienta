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
from fastapi import HTTPException, status
from sqlalchemy import func, inspect as sa_inspect, literal, or_, select
from sqlalchemy.orm import Session

from .. import alcance
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

    def _visibles(self, db: Session | None = None):
        """`SELECT` que excluye lo borrado **y lo que esta fuera del alcance**.

        Punto unico para no olvidarlo, por el mismo motivo que el borrado
        logico: los recursos de la API son instancias directas de `CRUDBase`,
        asi que repartir el filtro por veinte routers serian veinte lugares
        donde olvidarlo — y olvidarlo no falla, devuelve de mas.

        **`db` es opcional para no romper a quien llame sin el.** Sin sesion no
        hay alcance que aplicar, que es exactamente lo que pasa en el modo de
        desarrollo. Ver `app/alcance.py` para las tres reglas.
        """
        stmt = select(self.model)
        if self.usa_borrado_logico:
            stmt = stmt.where(self.model.deleted_at.is_(None))

        if db is not None and alcance.acota(self.model):
            permitidas = alcance.instalaciones_permitidas(db)
            if permitidas is not None:
                # **`IS NULL` entra.** Una fila sin instalacion es de la empresa
                # entera, no de otra planta: 36 de las 41 obligaciones del seed
                # son asi, y esconderlas le ocultaria a un encargado de planta
                # las obligaciones corporativas que tambien le aplican.
                stmt = stmt.where(
                    or_(
                        self.model.facility_id.is_(None),
                        self.model.facility_id.in_(permitidas),
                    )
                )
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
        return db.scalar(self._visibles(db).where(self._columna_id() == id))

    def _orden(self) -> list:
        """Un orden **total y estable**: la creacion y despues la clave primaria.

        Sin `ORDER BY`, Postgres no promete que dos consultas con `OFFSET`
        devuelvan las filas en el mismo orden, asi que leer un listado por
        paginas podia **repetir filas y saltarse otras** sin que nada fallara.
        Pasaba inadvertido mientras la web leia solo la primera pagina; dejo de
        ser teorico el 21-sep, cuando la Matriz Legal empezo a leer todas
        (`api.getTodas`) porque la primera traia 100 de 264 evaluaciones.

        La clave primaria va al final porque `created_at` empata: vale `now()`,
        que es el inicio de la transaccion, y todo lo que se crea junto comparte
        el mismo instante.
        """
        columnas = []
        creado = getattr(self.model, "created_at", None)
        if creado is not None:
            columnas.append(creado)
        columnas.extend(sa_inspect(self.model).primary_key)
        return columnas

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        return list(
            db.scalars(
                self._visibles(db).order_by(*self._orden()).offset(skip).limit(limit)
            ).all()
        )

    def create(
        self, db: Session, *, obj_in: CreateSchemaType, tenant_id: UUID | None = None
    ) -> ModelType:
        data = obj_in.model_dump(exclude_unset=True)
        if tenant_id is not None:
            data["tenant_id"] = tenant_id
        self._exigir_alcance(db, data.get("facility_id"))
        self._exigir_referencias(db, data)
        obj = self.model(**data)
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def update(
        self, db: Session, *, db_obj: ModelType, obj_in: UpdateSchemaType
    ) -> ModelType:
        update_data = obj_in.model_dump(exclude_unset=True)
        # **Mover una fila a otra planta tambien es escribir ahi.** Sin esto la
        # guarda del alta se saltaria con un PATCH — la puerta trasera que ya
        # aparecio en las etapas del CRM.
        if "facility_id" in update_data:
            self._exigir_alcance(db, update_data["facility_id"])
        self._exigir_referencias(db, update_data)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def _exigir_alcance(self, db: Session, facility_id: Any) -> None:
        """Rechaza escribir sobre una instalacion fuera del alcance del rol.

        **Filtrar solo la lectura seria peor que no filtrar.** Alguien acotado a
        Calama podria crear una evaluacion en Antofagasta y despues no verla:
        una fila que existe, cuenta en los totales de la planta ajena y es
        invisible para quien la escribio. Es la leccion de la guarda que solo
        miraba el `DELETE` de las etapas del CRM.

        **403 y no 404.** El recurso que se pide crear no existe todavia, asi
        que no hay nada cuya existencia revelar: lo que falta es permiso sobre
        esa planta, y decirlo permite entender el error. Distinto del `validar_
        visible` de las claves foraneas, donde el 422 evita el oraculo de
        identificadores ajenos — la planta ya la conoce, sale de su propio
        selector.
        """
        if not alcance.fuera_de_alcance(db, self.model, facility_id):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tu rol esta acotado a otras instalaciones: no puedes escribir "
                "sobre esta."
            ),
        )

    def _exigir_referencias(self, db: Session, data: dict) -> None:
        """Toda clave foranea hacia una tabla de empresa tiene que apuntar a algo
        que **esta empresa ve**.

        **Las FK de Postgres no pasan por RLS**: solo exigen que la fila exista,
        no que sea de la empresa (`_comun.validar_visible` lo explica). La regla
        de este repositorio era que cada endpoint que acepte un id en el cuerpo
        llame a `validar_visible`, y se cumplia a medias: el 21-sep
        `routers/compliance.py` no lo llamaba ni una vez. Una regla que depende
        de acordarse en cada endpoint es la que este archivo ya reemplazo dos
        veces —borrado logico y alcance— por un punto unico.

        Se lee el destino con **la misma sesion**, asi que RLS decide: si esta
        empresa no lo ve, para ella no existe. Lo retirado tampoco cuenta. Las
        tablas sin `tenant_id` —catalogo global, `tenants`— no se comprueban:
        la FK basta.

        Mismo codigo y mismo texto que `validar_visible`, exista o no el
        destino: distinguirlos seria un oraculo de identificadores ajenos.
        """
        tabla = self.model.__table__
        for nombre, valor in data.items():
            if valor is None or nombre == "tenant_id":
                continue
            columna = tabla.c.get(nombre)
            if columna is None:
                continue
            for fk in columna.foreign_keys:
                destino = fk.column.table
                if "tenant_id" not in destino.c:
                    continue
                consulta = select(literal(1)).select_from(destino).where(fk.column == valor)
                if "deleted_at" in destino.c:
                    consulta = consulta.where(destino.c.deleted_at.is_(None))
                if db.execute(consulta.limit(1)).first() is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"{nombre} no corresponde a un registro de esta empresa.",
                    )

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
