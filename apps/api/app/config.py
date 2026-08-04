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
    database_url: str = (
        "postgresql+psycopg://ambienta:ambienta_dev@postgres:5432/ambienta"
    )

    # Origenes permitidos por CORS, separados por coma.
    cors_origins: str = "http://localhost:3000"

    environment: str = "development"
    port: int = 8000

    # Loguea cada consulta SQL. Util para depurar, ruidoso para el resto.
    sql_echo: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
