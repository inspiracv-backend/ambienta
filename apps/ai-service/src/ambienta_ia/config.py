"""
Configuración del servicio. Todo sale de variables de entorno y se valida al arrancar.

Si falta algo obligatorio, el servicio no arranca: es mejor que arrancar a medias
(SPEC-09).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # backend de Ambienta
    backend_url: str = Field(description="Base de la API, por ejemplo http://api:8000/api/v1")
    backend_timeout_s: float = 20.0

    # identidad (SPEC-02). Sin JWKS = modo desarrollo, igual que el backend.
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None

    # base de conocimiento (SPEC-03): dos roles
    database_url_consulta: str
    database_url_sincronizador: str | None = None

    # cuenta servicio_lectura, solo para sincronizar el catálogo (SPEC-04)
    servicio_token: str | None = None
    servicio_tenant_id: str | None = None  # modo desarrollo del backend

    # proveedores (decisiones A y B del plan)
    proveedor_llm: Literal["openai", "anthropic", "ollama", "falso"] = "openai"
    modelo_llm: str = "gpt-4o-mini"
    proveedor_embeddings: Literal["openai", "ollama", "local"] = "openai"
    modelo_embeddings: str = "text-embedding-3-small"
    dimension_embeddings: int = 1536

    # recuperación y agente, calibrados con SPEC-08
    # 0,40 medido con text-embedding-3-small el 21/09/2026 (evaluacion/README.md). Con los
    # embeddings locales de la demo se usa 0,25. Cambiar de modelo es volver a medir.
    umbral_evidencia: float = 0.40
    k_recuperacion: int = 5
    max_herramientas: int = 6
    max_revisiones: int = 2
    max_tokens_consulta: int = 20_000
    turnos_de_contexto: int = 10
    revisor_con_modelo: bool = True
    # Reordenar los candidatos con el modelo. Con el catálogo real es lo que decide la evidencia:
    # el coseno solo no separa lo pertinente de lo ajeno (medido el 21/09/2026).
    reordenar_con_modelo: bool = True

    @property
    def modo_desarrollo(self) -> bool:
        return not self.clerk_jwks_url


@lru_cache(maxsize=1)
def config() -> Config:
    return Config()  # type: ignore[call-arg]
