"""El alcance por instalacion de un rol, aplicado (RF-12, `sistema-actores-roles-rbac`).

## Que estaba pasando, medido el 10-sep-2026

`user_roles.facility_id` y `department_id` existen desde el principio,
`services/permisos.py::alcance_del_usuario()` los resuelve, y `GET /me` los
devuelve en `instalaciones`, `departamentos` y `acotado` — o sea que la pantalla
podia mostrar "acotado a Planta Calama" con toda confianza.

**Y `alcance_del_usuario()` tenia un solo llamador: `/me`, que lo informaba.**
Ninguna consulta filtraba por el. Con el rol acotado a una sola planta:

| `GET /compliance/article-compliance` | filas |
|---|---|
| de su planta | 92 |
| **de las otras dos** | **172** |

No era una fuga entre empresas —RLS es la unica barrera entre tenants y sigue
firme— pero el acotamiento *dentro* de la empresa era decorativo, y eso se
promete en una venta y se contesta en una auditoria de accesos.

## Donde se aplica, y por que ahi

**En `CRUDBase._visibles()`, junto al filtro de borrado logico.** Es el mismo
razonamiento que dejo escrito ese archivo para `deleted_at`: los recursos de la
API son instancias directas de `CRUDBase`, asi que lo que se decida ahi vale
para todos. Repartir el filtro por veinte routers seria veinte lugares donde
olvidarlo, y olvidarlo **no falla**: devuelve de mas.

## Las tres reglas que lo hacen correcto

1. **Sin acotamiento no se filtra nada.** Un alcance vacio significa "toda la
   empresa", no "ninguna planta". Es lo que ya declara el docstring de `/me`, y
   confundirlo dejaria a los administradores viendo una pantalla en blanco.

2. **Una fila sin instalacion se ve igual.** `facility_id IS NULL` no es "de
   otra planta": es un registro de la empresa entera —36 de las 41 obligaciones
   del seed son asi—. Excluirlas le esconderia a un encargado de planta las
   obligaciones corporativas que tambien le aplican.

3. **Escribir fuera del alcance se rechaza.** Sin esto la guarda seria de las
   que hacen creer que protegen: alguien acotado a Calama podria crear una
   evaluacion en Antofagasta y despues no verla. Es la leccion del `PATCH` que
   se saltaba la comprobacion de las etapas del CRM.

## El costo

Una consulta extra la primera vez que un request toca un modelo con
`facility_id`, y **solo si hay sesion identificada**. Se cachea en `db.info`,
que vive lo que vive la sesion: un request no puede heredar el alcance de otro.
Mismo canal que usa el registro de actividades para saber quien actua.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

#: Donde se cachea el alcance ya resuelto, dentro de `db.info`.
#:
#: Vale `None` cuando **no hay acotamiento** y un `frozenset` cuando lo hay. La
#: ausencia de la clave significa "todavia no se calculo", que es distinto de
#: las dos anteriores — por eso no se usa `db.info.get(...)` a secas.
ALCANCE = "alcance_de_instalaciones"


def instalaciones_permitidas(db: Session) -> frozenset[UUID] | None:
    """A que instalaciones esta acotada esta sesion. `None` = a ninguna, o sea
    a todas.

    Se resuelve **una vez por sesion** y con importaciones diferidas: este
    modulo lo usa `crud/base.py`, y `services/permisos` arrastra los modelos.

    Sin sesion identificada devuelve `None`. Es el modo `X-Tenant-Id` de
    desarrollo, donde no hay usuario del cual sacar roles — el mismo criterio
    que el resto de las guardas.
    """
    if ALCANCE in db.info:
        return db.info[ALCANCE]

    alcance = _resolver(db)
    db.info[ALCANCE] = alcance
    return alcance


def _resolver(db: Session) -> frozenset[UUID] | None:
    from sqlalchemy import select

    from .deps import CONTEXTO_DE_AUDITORIA
    from .models.organization import User
    from .services.permisos import alcance_del_usuario

    contexto = db.info.get(CONTEXTO_DE_AUDITORIA) or {}
    clerk_id = contexto.get("clerk_id")
    if not clerk_id:
        return None

    quien = db.scalars(
        select(User).where(User.clerk_id == clerk_id, User.deleted_at.is_(None))
    ).first()
    if quien is None:
        return None

    instalaciones, _departamentos = alcance_del_usuario(db, quien.id)
    # **Vacio es "sin acotar", no "ninguna".** Ver la regla 1 del modulo.
    return frozenset(instalaciones) or None


def acota(modelo: type) -> bool:
    """Si a este modelo le corresponde el filtro.

    `facilities` queda **fuera a proposito**: su clave es `id`, no
    `facility_id`, y acotar el listado de plantas es otra decision — hoy alguien
    acotado a una planta igual necesita ver el selector para entender donde
    esta.
    """
    return hasattr(modelo, "facility_id")


def fuera_de_alcance(db: Session, modelo: type, facility_id: UUID | None) -> bool:
    """Si esta sesion **no** puede escribir sobre esa instalacion.

    `None` nunca esta fuera: una fila sin planta es de la empresa entera, y
    quien puede escribir en la empresa puede escribir ahi. Es la regla 2
    aplicada a la escritura.
    """
    if facility_id is None or not acota(modelo):
        return False
    permitidas = instalaciones_permitidas(db)
    if permitidas is None:
        return False
    return facility_id not in permitidas
