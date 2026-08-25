"""Configuracion de la API, leida del entorno.

Un solo lugar donde se resuelven las variables de entorno, para que el resto
del codigo no llame a os.environ disperso.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Conexion a Postgres. En Compose el host es el nombre del servicio
    # (`postgres`), no localhost.
    #
    # El driver va explicito (`postgresql+psycopg`) para que SQLAlchemy use
    # psycopg 3 y no intente cargar psycopg2, que no esta instalado.
    # Rol de la aplicacion. NO es superusuario y NO puede saltarse RLS: es lo
    # que hace que el aislamiento entre empresas viva en la conexion y no en
    # que alguien se acuerde de cambiar de rol en cada transaccion.
    database_url: str = (
        "postgresql+psycopg://ambienta_app:ambienta_app_dev@postgres:5432/ambienta"
    )

    # Conexion con el dueno de la base, que SI salta RLS. Solo para lo que
    # cruza empresas por diseno: el webhook de Clerk y el health del esquema.
    # Vacia por defecto para que usarla sea una decision, no un descuido.
    database_admin_url: str = ""

    #: Donde caen los JSON de la rotacion mensual del registro de actividades.
    #:
    #: Hoy es disco del servidor. **Cuando exista la cuenta de Backblaze esto se
    #: cambia por su bucket** y no hay que tocar la tarea: la ruta es lo unico
    #: que sabe donde escribe.
    ruta_archivo_auditoria: str = "/var/lib/ambienta/auditoria"

    # Origenes permitidos por CORS, separados por coma.
    cors_origins: str = "http://localhost:3000"

    environment: str = "development"
    port: int = 8000

    # Loguea cada consulta SQL. Util para depurar, ruidoso para el resto.
    sql_echo: bool = False

    # --- Clerk (ADR-006) -----------------------------------------------------
    # Vacias en desarrollo: sin ellas la API cae al fallback del header
    # X-Tenant-Id y el frontend muestra el DevRoleSwitcher. Ver
    # openspec/changes/integracion-clerk-auth/design.md §2.3.
    #
    # `clerk_jwks_url` es lo que decide si Clerk esta activo. Es la llave
    # publica: no es un secreto, pero sin ella no se puede verificar ninguna
    # firma.
    clerk_jwks_url: str = ""
    # Emisor esperado del token (claim `iss`). Se valida para que un JWT de
    # otra instancia de Clerk no sirva contra esta API.
    clerk_issuer: str = ""
    # Secreto del webhook (protocolo svix). Solo lo usa el router de webhooks
    # de la Fase 2; se declara aca para tener toda la config de Clerk junta.
    clerk_webhook_secret: str = ""

    # --- Token del Cliente Invitado (RF-01, RF-02, RF-07) --------------------
    # El invitado no es cuenta de Clerk, asi que su sesion no la puede firmar
    # Clerk: la firma esta API con su propio secreto (decision del equipo,
    # 22-ago-2026). Es simetrico —HS256— porque el mismo servicio firma y
    # verifica; no hay un tercero que necesite validar sin poder emitir.
    #
    # **Vacio a proposito y sin valor por defecto.** Un secreto por defecto en
    # el codigo es un secreto publicado: cualquiera que lea el repo puede
    # firmarse un token de invitado de cualquier empresa. Sin esta variable la
    # emision de sesiones **se niega** (503) en vez de funcionar con una llave
    # que no protege nada. Es la diferencia entre fallar cerrado y fallar
    # abierto, y aca el default tiene que ser cerrado.
    token_invitado_secreto: str = ""

    @property
    def token_invitado_configurado(self) -> bool:
        """Si se pueden emitir y verificar sesiones de invitado."""
        return bool(self.token_invitado_secreto)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def clerk_configured(self) -> bool:
        """Si Clerk esta activo, el fallback de desarrollo queda deshabilitado.

        Una sola propiedad decide el modo de toda la API: con Clerk configurado
        no hay camino que acepte un tenant sin firmar. Es deliberado que sea
        un solo interruptor y no una flag por endpoint — 93 endpoints con
        criterios distintos serian 93 formas de dejar un hueco.
        """
        return bool(self.clerk_jwks_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
