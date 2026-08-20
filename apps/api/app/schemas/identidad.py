"""Lo que devuelve `GET /me`: quien llama, de que empresa y que puede hacer."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class UsuarioDeLaSesion(BaseModel):
    """La fila propia de quien llama.

    `id` es **el UUID interno**, que es el que esperan el resto de los
    endpoints. `clerk_id` es el del proveedor de identidad y viaja en el JWT.
    Son distintos, y confundirlos da 404 en cualquier consulta por usuario.
    """

    id: UUID = Field(description="UUID interno. Es el que usan los demas endpoints")
    clerk_id: str | None = Field(
        default=None, description="Id del proveedor de identidad (`sub` del JWT). No es `id`"
    )
    email: str
    nombre: str
    tipo: str = Field(description="`platform_admin` | `tenant_user` | ...")
    estado: str
    department_id: UUID | None = None


class EmpresaDeLaSesion(BaseModel):
    """La empresa contra la que se esta consultando.

    `sector_id` y `tramo` son **los que determinan que normativa le aplica**.
    Si vienen en `null`, la empresa todavia no declaro su perfil normativo y su
    matriz legal no puede proponer nada.
    """

    id: UUID
    nombre: str
    nombre_comercial: str | None = None
    rut: str | None = None
    sector_id: int | None = Field(
        default=None, description="Sector CIIU. `null` = perfil normativo sin declarar"
    )
    tramo: str | None = Field(
        default=None, description="`micro` | `pequena` | `mediana` | `grande`"
    )
    giro: str | None = None


class IdentidadRead(BaseModel):
    """Quien llama, de que empresa, y que puede hacer.

    Es la primera llamada de cualquier integracion: el token dice contra que
    empresa consultar, pero no dice quien es quien llama ni cual es su UUID
    interno.
    """

    modo_desarrollo: bool = Field(
        description="`true` cuando la API corre sin proveedor de identidad y "
        "acepta el header `X-Tenant-Id`. Entonces `usuario` viene en `null`: no "
        "hay identidad que resolver y **no se inventa una**"
    )
    usuario: UsuarioDeLaSesion | None
    empresa: EmpresaDeLaSesion
    permisos: list[str] = Field(
        description="Lo que esta persona puede hacer, ya resuelto: roles mas "
        "concesiones individuales, menos las denegaciones. **La denegacion gana.** "
        "Son los mismos que la API aplica en cada request"
    )
    acotado: bool = Field(
        description="Si el alcance esta limitado a instalaciones o departamentos "
        "concretos. Se dice explicito porque **una lista vacia significa 'sin "
        "acotar', no 'ninguno'** — es la diferencia entre un encargado de toda la "
        "empresa y uno sin acceso a nada"
    )
    instalaciones: list[UUID]
    departamentos: list[UUID]
