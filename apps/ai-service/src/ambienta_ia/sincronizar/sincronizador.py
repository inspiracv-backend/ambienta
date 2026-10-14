"""
Sincronización del catálogo público (SPEC-04).

Tres garantías:

1. **Solo lo que cambió.** Se pide `updated_since` con el `updated_at` máximo visto, no con la
   hora de la corrida. Y si la versión vigente tiene el mismo `content_hash`, no se pagan
   embeddings de nuevo.
2. **Sin hueco al cambiar de versión.** La versión vieja se borra y la nueva se inserta en la
   misma transacción: una consulta concurrente ve una o la otra, nunca ninguna.
3. **Una norma que falla no se pierde.** El máximo solo avanza hasta antes de la primera norma
   fallida, así la próxima corrida la vuelve a pedir.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

from ..backend import ClienteBackend
from ..backend.modelos import Norma
from ..citas import etiqueta_norma, normalizar_norma
from ..conocimiento import BaseConocimiento
from ..observabilidad import aviso, evento
from ..proveedores import Embeddings
from ..proveedores.embeddings import como_vector
from .arbol import elegir_vigente, fragmentar_norma, hash_de_articulos, texto_para_embedding

FUENTE = "catalogo"


@dataclass
class ErrorNorma:
    norm_id: str
    titulo: str
    error: str


@dataclass
class CambioDeNorma:
    """Una norma que cambió de versión vigente. Es lo que consume el agente de monitoreo (#137)."""

    norm_id: str
    etiqueta: str
    titulo: str
    version_anterior: str
    version_nueva: str
    vigente_desde: str | None
    modificados: list[str] = field(default_factory=list)
    nuevos: list[str] = field(default_factory=list)
    derogados: list[str] = field(default_factory=list)


@dataclass
class ResultadoSincronizacion:
    normas_vistas: int = 0
    versiones_nuevas: int = 0
    versiones_sin_cambios: int = 0
    normas_sin_vigente: int = 0
    normas_omitidas: int = 0
    fragmentos_indexados: int = 0
    fragmentos_borrados: int = 0
    errores: list[ErrorNorma] = field(default_factory=list)
    updated_at_maximo: datetime | None = None
    duracion_s: float = 0.0
    cambios: list[CambioDeNorma] = field(default_factory=list)


async def _estado(base: BaseConocimiento) -> datetime | None:
    async with base.transaccion() as conn:
        cur = await conn.execute(
            "SELECT updated_at_maximo FROM sincronizacion WHERE fuente = %s", (FUENTE,)
        )
        fila = await cur.fetchone()
    return fila[0] if fila else None


async def _guardar_estado(base: BaseConocimiento, r: ResultadoSincronizacion) -> None:
    resumen = asdict(r)
    resumen["updated_at_maximo"] = r.updated_at_maximo.isoformat() if r.updated_at_maximo else None
    async with base.transaccion() as conn:
        await conn.execute(
            """
            INSERT INTO sincronizacion (fuente, updated_at_maximo, ultima_corrida, resultado)
            VALUES (%s, %s, now(), %s::jsonb)
            ON CONFLICT (fuente) DO UPDATE
               SET updated_at_maximo = EXCLUDED.updated_at_maximo,
                   ultima_corrida    = EXCLUDED.ultima_corrida,
                   resultado         = EXCLUDED.resultado
            """,
            (FUENTE, r.updated_at_maximo, json.dumps(resumen, default=str)),
        )


async def _borrar_norma(base: BaseConocimiento, norm_id) -> int:
    async with base.transaccion() as conn:
        cur = await conn.execute("SELECT count(*) FROM fragmento WHERE norm_id = %s", (norm_id,))
        (n,) = await cur.fetchone()
        await conn.execute("DELETE FROM version_norma WHERE norm_id = %s", (norm_id,))
    return n


async def _purgar(base: BaseConocimiento, norm_ids: set) -> int:
    """Borra del índice público cualquier norma que resultó ser propia de una empresa."""
    async with base.transaccion() as conn:
        cur = await conn.execute("SELECT count(*) FROM fragmento WHERE norm_id = ANY(%s)", (list(norm_ids),))
        (n,) = await cur.fetchone()
        await conn.execute("DELETE FROM version_norma WHERE norm_id = ANY(%s)", (list(norm_ids),))
    if n:
        aviso("normativa_propia_purgada_del_indice", normas=len(norm_ids), fragmentos=n)
    return n


async def _sincronizar_norma(
    norma: Norma,
    cliente: ClienteBackend,
    base: BaseConocimiento,
    embeddings: Embeddings,
    r: ResultadoSincronizacion,
) -> None:
    versiones = await cliente.versiones(norma.id)
    vigente = elegir_vigente(versiones)
    if vigente is None:
        # Derogada o sin texto: lo que estuviera indexado deja de servirse (D-06).
        r.fragmentos_borrados += await _borrar_norma(base, norma.id)
        r.normas_sin_vigente += 1
        return

    async with base.transaccion() as conn:
        cur = await conn.execute(
            "SELECT id, content_hash FROM version_norma WHERE norm_id = %s", (norma.id,)
        )
        actual = await cur.fetchone()

    clave = normalizar_norma(f"{norma.norm_type} {norma.norm_number or ''}")

    articulos = None
    hash_vigente = vigente.content_hash
    if hash_vigente is None:
        articulos = await cliente.articulos(norma.id)
        hash_vigente = hash_de_articulos(articulos)

    if actual and actual[0] == vigente.id and actual[1] == hash_vigente:
        # Mismo texto. Se actualizan los metadatos por si cambió el título o el enlace.
        async with base.transaccion() as conn:
            await conn.execute(
                """
                UPDATE version_norma
                   SET titulo = %s, official_url = %s, clave_norma = %s, norm_number = %s,
                       is_current = true, valid_from = %s, valid_to = %s, sincronizado_en = now()
                 WHERE id = %s
                """,
                (norma.title, norma.official_url, clave, norma.norm_number,
                 vigente.valid_from, vigente.valid_to, vigente.id),
            )
        r.versiones_sin_cambios += 1
        return

    if articulos is None:
        articulos = await cliente.articulos(norma.id)
    de_la_version = [a for a in articulos if a.norm_version_id == vigente.id]
    if de_la_version:
        articulos = de_la_version

    fragmentos = fragmentar_norma(norma, articulos)
    if not fragmentos:
        aviso("norma_sin_texto", norm_id=str(norma.id), titulo=norma.title)
    vectores = await embeddings.generar([texto_para_embedding(norma.title, f.ruta, f.texto) for f in fragmentos])

    async with base.transaccion() as conn:
        cur = await conn.execute("SELECT count(*) FROM fragmento WHERE norm_id = %s", (norma.id,))
        (borrados,) = await cur.fetchone()
        # Qué cambió, artículo por artículo, antes de borrar la versión anterior. Es lo que el
        # agente de monitoreo le cuenta a cada empresa: no "cambió la ley", sino qué artículos.
        cur = await conn.execute(
            "SELECT coalesce(numero_normal, article_id::text), string_agg(texto, ' ' ORDER BY parte) "
            "FROM fragmento WHERE norm_id = %s GROUP BY 1", (norma.id,))
        antes = {n: " ".join(t.split()) for n, t in await cur.fetchall()}
        await conn.execute("DELETE FROM version_norma WHERE norm_id = %s", (norma.id,))
        await conn.execute(
            """
            INSERT INTO version_norma (id, norm_id, tenant_id, norm_type, norm_number, clave_norma,
                                       titulo, valid_from, valid_to, is_current, content_hash,
                                       official_url)
            VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, true, %s, %s)
            """,
            (vigente.id, norma.id, norma.norm_type, norma.norm_number, clave, norma.title,
             vigente.valid_from, vigente.valid_to, hash_vigente, norma.official_url),
        )
        async with conn.cursor() as c:
            await c.executemany(
                """
                INSERT INTO fragmento (article_id, version_id, norm_id, tenant_id, article_type,
                                       article_number, numero_normal, parte, total_partes, ruta,
                                       texto, embedding, modelo_embedding)
                VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                """,
                [
                    (f.article_id, vigente.id, norma.id, f.article_type, f.article_number,
                     f.numero_normal, f.parte, f.total_partes, f.ruta, f.texto, como_vector(v), embeddings.modelo)
                    for f, v in zip(fragmentos, vectores, strict=True)
                ],
            )
    r.fragmentos_borrados += borrados
    r.fragmentos_indexados += len(fragmentos)
    r.versiones_nuevas += 1
    if actual:  # había una versión indexada: esto es un cambio, no la primera carga
        ahora: dict[str, str] = {}
        for f in fragmentos:
            clave_art = f.numero_normal or str(f.article_id)
            ahora[clave_art] = (ahora.get(clave_art, "") + " " + f.texto).strip()
        ahora = {k: " ".join(v.split()) for k, v in ahora.items()}
        r.cambios.append(CambioDeNorma(
            norm_id=str(norma.id), etiqueta=etiqueta_norma(norma.norm_type, norma.norm_number, norma.title),
            titulo=norma.title, version_anterior=str(actual[0]), version_nueva=str(vigente.id),
            vigente_desde=vigente.valid_from.isoformat() if vigente.valid_from else None,
            modificados=sorted(k for k in ahora if k in antes and antes[k] != ahora[k]),
            nuevos=sorted(k for k in ahora if k not in antes),
            derogados=sorted(k for k in antes if k not in ahora),
        ))


async def sincronizar(
    cliente: ClienteBackend,
    base: BaseConocimiento,
    embeddings: Embeddings,
    *,
    completa: bool = False,
) -> ResultadoSincronizacion:
    """
    `cliente` tiene que ser el de la cuenta `servicio_lectura` (SPEC-02). `base` el del rol
    `ia_sincronizador`, que solo puede escribir filas públicas.

    `completa=True` ignora `updated_since` y revisa todo el catálogo; igual no reindexa lo que
    no cambió.
    """
    inicio = time.monotonic()
    r = ResultadoSincronizacion()
    anterior = None if completa else await _estado(base)
    r.updated_at_maximo = anterior

    # /catalog/norms le devuelve a la cuenta de servicio el catálogo público MÁS la normativa
    # propia de su empresa, sin ningún campo que las distinga (LegalNormRead no trae
    # tenant_id). Sin este filtro, la RCA de una empresa queda indexada como catálogo público y
    # la ve cualquier otra. Falla cerrado: si no se puede saber qué es propio, no se indexa nada.
    propias = {n.id async for n in cliente.normativa_propia()}
    if propias:
        r.fragmentos_borrados += await _purgar(base, propias)

    normas = [n async for n in cliente.normas(updated_since=anterior)]
    normas.sort(key=lambda n: n.updated_at)
    r.normas_vistas = len(normas)

    exitosas: list[datetime] = []
    fallidas: list[datetime] = []
    for norma in normas:
        if norma.tenant_id is not None or norma.id in propias:
            # Normativa propia de una empresa colada en el listado: no es catálogo público.
            r.normas_omitidas += 1
            exitosas.append(norma.updated_at)
            continue
        try:
            await _sincronizar_norma(norma, cliente, base, embeddings, r)
            exitosas.append(norma.updated_at)
        except Exception as e:  # una norma no frena a las demás
            fallidas.append(norma.updated_at)
            r.errores.append(ErrorNorma(str(norma.id), norma.title, f"{type(e).__name__}: {e}"))
            aviso("sincronizar_norma_fallo", norm_id=str(norma.id), error=str(e))

    tope = min(fallidas) if fallidas else None
    validas = [t for t in exitosas if tope is None or t < tope]
    if validas:
        r.updated_at_maximo = max([*validas, *([anterior] if anterior else [])])

    r.duracion_s = round(time.monotonic() - inicio, 2)
    await _guardar_estado(base, r)
    evento("sincronizacion", **{k: v for k, v in asdict(r).items() if k not in ("errores", "cambios")},
           errores=len(r.errores), cambios=len(r.cambios))
    return r
