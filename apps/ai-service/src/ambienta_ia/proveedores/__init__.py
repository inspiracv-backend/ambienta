"""
Los únicos lugares del servicio que saben qué proveedor de modelos se usa.

Cambiar de proveedor toca este paquete y la configuración, nada más. La excepción que no se
puede esconder: el modelo de embeddings define la dimensión del vector, que es parte del
esquema. Cambiarlo es reindexar (SPEC-03).
"""

from .embeddings import Embeddings, EmbeddingsLocales, EmbeddingsOpenAI, crear_embeddings
from .llm import crear_modelo

__all__ = ["Embeddings", "EmbeddingsLocales", "EmbeddingsOpenAI", "crear_embeddings", "crear_modelo"]
