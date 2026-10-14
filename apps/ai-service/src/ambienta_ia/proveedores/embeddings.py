"""
Embeddings detrás de una interfaz.

- `EmbeddingsOpenAI`: el proveedor por defecto.
- `EmbeddingsLocales`: determinista y sin red. Es una bolsa de palabras con hashing, no un
  modelo semántico: sirve para pruebas, para la demo sin claves y para que la evaluación de
  recuperación en CI no gaste. **No es para producción**: no entiende sinónimos.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from typing import Protocol

LOTE = 64


class Embeddings(Protocol):
    modelo: str
    dimension: int

    async def generar(self, textos: list[str]) -> list[list[float]]: ...


class EmbeddingsOpenAI:
    def __init__(self, modelo: str, dimension: int, api_key: str | None = None):
        from openai import AsyncOpenAI

        self.modelo = modelo
        self.dimension = dimension
        self._cliente = AsyncOpenAI(api_key=api_key)

    async def generar(self, textos: list[str]) -> list[list[float]]:
        salida: list[list[float]] = []
        for i in range(0, len(textos), LOTE):
            r = await self._cliente.embeddings.create(
                model=self.modelo, input=textos[i : i + LOTE], dimensions=self.dimension
            )
            salida.extend(d.embedding for d in r.data)
        return salida


_VACIAS = set(
    """
    a al ante bajo con contra de del desde durante e el en entre hacia hasta la las le les lo los
    mediante o para por que qué se segun según sin so sobre tras un una unos unas y u es son ser
    su sus este esta estos estas ese esa eso cual cuál cuales cuáles cuando cuándo como cómo
    donde dónde quien quién me mi mis tengo tiene tienen hay debe deben puede pueden dice
    """.split()
)


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def _raiz(palabra: str) -> str:
    # recorte grosero de sufijos: "declaraciones" y "declaración" caen juntas
    for sufijo in ("aciones", "acion", "mente", "iones", "ion", "es", "s"):
        if palabra.endswith(sufijo) and len(palabra) - len(sufijo) >= 4:
            return palabra[: -len(sufijo)]
    return palabra


def terminos(texto: str) -> list[str]:
    palabras = re.findall(r"[a-z0-9ñ]+", _normalizar(texto))
    return [_raiz(p) for p in palabras if p not in _VACIAS and len(p) > 1]


class EmbeddingsOllama:
    """Embeddings con Ollama (por ejemplo `bge-m3`, multilingüe, 1024 dimensiones)."""

    def __init__(self, modelo: str, dimension: int, url: str | None = None):
        import os

        import httpx

        self.modelo = modelo
        self.dimension = dimension
        self._http = httpx.AsyncClient(base_url=url or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
                                       timeout=120)

    async def generar(self, textos: list[str]) -> list[list[float]]:
        salida: list[list[float]] = []
        for i in range(0, len(textos), LOTE):
            r = await self._http.post("/api/embed", json={"model": self.modelo, "input": textos[i : i + LOTE]})
            r.raise_for_status()
            vectores = r.json()["embeddings"]
            if vectores and len(vectores[0]) != self.dimension:
                raise ValueError(f"{self.modelo} devuelve {len(vectores[0])} dimensiones y la base espera "
                                 f"{self.dimension}: ajustar DIMENSION_EMBEDDINGS y reindexar.")
            salida.extend(vectores)
        return salida


class EmbeddingsLocales:
    def __init__(self, dimension: int = 256, modelo: str = "local-hash-v1"):
        self.modelo = modelo
        self.dimension = dimension

    def _vector(self, texto: str) -> list[float]:
        v = [0.0] * self.dimension
        for t in terminos(texto):
            h = int.from_bytes(hashlib.blake2b(t.encode(), digest_size=8).digest(), "big")
            v[h % self.dimension] += 1.0 if (h >> 32) & 1 else -1.0
        norma = math.sqrt(sum(x * x for x in v))
        if norma == 0:
            v[0] = 1.0  # un texto sin términos no puede ser un vector nulo para pgvector
            return v
        return [x / norma for x in v]

    async def generar(self, textos: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in textos]


def crear_embeddings(proveedor: str, modelo: str, dimension: int) -> Embeddings:
    if proveedor == "local":
        return EmbeddingsLocales(dimension=dimension)
    if proveedor == "openai":
        return EmbeddingsOpenAI(modelo=modelo, dimension=dimension)
    if proveedor == "ollama":
        return EmbeddingsOllama(modelo=modelo, dimension=dimension)
    raise ValueError(f"Proveedor de embeddings desconocido: {proveedor}")


def como_vector(v: list[float]) -> str:
    """Literal que pgvector acepta con ::vector. Evita depender de numpy."""
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def coseno(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=True))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0
