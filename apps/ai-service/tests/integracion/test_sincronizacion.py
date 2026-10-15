"""SPEC-04 · El AI Service tiene el mismo catálogo que el backend."""

from __future__ import annotations

import asyncio
from datetime import datetime

import psycopg
import pytest

from ambienta_ia.demo import datos as D
from ambienta_ia.sincronizar import sincronizar

pytestmark = pytest.mark.integracion


class EmbeddingsContados:
    def __init__(self, interno):
        self.interno = interno
        self.modelo = interno.modelo
        self.dimension = interno.dimension
        self.textos = 0

    async def generar(self, textos):
        self.textos += len(textos)
        return await self.interno.generar(textos)


def _normas_publicas():
    return [n for n in D.construir()["normas"] if n.get("tenant_id") is None]


async def test_primera_corrida(fabrica_cliente, base_sincronizador, embeddings, base_limpia):
    cliente = fabrica_cliente()
    r = await sincronizar(cliente, base_sincronizador, embeddings)
    publicas = _normas_publicas()
    assert r.errores == []
    assert r.versiones_nuevas == len(publicas)
    # el máximo de todo lo que devolvió el backend, incluida la normativa propia que se omite
    visibles = [n for n in D.construir()["normas"] if n.get("tenant_id") in (None, str(D.EMPRESA_A))]
    assert r.updated_at_maximo == max(datetime.fromisoformat(n["updated_at"]) for n in visibles)
    with psycopg.connect(base_limpia["admin"]) as c:
        normas = c.execute("SELECT count(DISTINCT norm_id) FROM fragmento").fetchone()[0]
        privadas = c.execute("SELECT count(*) FROM fragmento WHERE tenant_id IS NOT NULL").fetchone()[0]
    assert normas == len(publicas)
    assert privadas == 0  # la RCA de la empresa A no es catálogo público


async def test_segunda_corrida_sin_cambios(fabrica_cliente, base_sincronizador, embeddings, estado_backend):
    await sincronizar(fabrica_cliente(), base_sincronizador, embeddings)
    contados = EmbeddingsContados(embeddings)
    estado_backend.peticiones.clear()
    r = await sincronizar(fabrica_cliente(), base_sincronizador, contados)
    assert contados.textos == 0
    assert r.normas_vistas == 0
    pedido = [p for p in estado_backend.peticiones if p[1].endswith("/catalog/norms")]
    assert pedido, "tiene que haber pedido el listado"


async def test_completa_revisa_todo_pero_no_reindexa_lo_que_no_cambio(fabrica_cliente, base_sincronizador, embeddings):
    await sincronizar(fabrica_cliente(), base_sincronizador, embeddings)
    contados = EmbeddingsContados(embeddings)
    r = await sincronizar(fabrica_cliente(), base_sincronizador, contados, completa=True)
    assert r.versiones_sin_cambios == len(_normas_publicas())
    assert contados.textos == 0


async def test_se_indexa_la_version_vigente_de_la_ley_19300(catalogo_sincronizado, base_limpia):
    with psycopg.connect(base_limpia["admin"]) as c:
        texto = c.execute(
            "SELECT f.texto FROM fragmento f JOIN version_norma v ON v.id = f.version_id "
            "WHERE v.clave_norma = 'ley/19300' AND f.numero_normal = '11'"
        ).fetchone()[0]
    assert "reasentamiento" in texto  # la de 2010, no la de 1994


async def test_cambio_de_version_sin_hueco(fabrica_cliente, base_sincronizador, embeddings, estado_backend, base_limpia):
    await sincronizar(fabrica_cliente(), base_sincronizador, embeddings)

    # el backend publica una versión nueva del DS 1
    ds1 = next(n for n in estado_backend.datos["normas"] if n["norm_number"] == "1/2013")
    nueva = "b0000000-0000-0000-0000-000000000099"
    estado_backend.datos["versiones"][ds1["id"]].append(
        {"id": nueva, "norm_id": ds1["id"], "valid_from": "2026-09-15", "valid_to": None,
         "is_current": True, "content_hash": "ds1-2026"})
    viejos = estado_backend.datos["articulos"]
    viejo_id = next(v["id"] for v in estado_backend.datos["versiones"][ds1["id"]] if v["id"] != nueva)
    viejos[nueva] = [{**a, "norm_version_id": nueva, "id": a["id"][:-4] + "9999",
                      "parent_article_id": (a["parent_article_id"][:-4] + "9999") if a["parent_article_id"] else None,
                      "content": (a["content"] or "") and a["content"] + " (texto 2026)"} for a in viejos[viejo_id]]
    estado_backend.datos["vigencia"][ds1["id"]] = [(D.date(2026, 9, 15), None, nueva)]
    ds1["updated_at"] = "2026-09-15T00:00:00+00:00"

    vistos: list[int] = []
    corriendo = True

    async def observar():
        with psycopg.connect(base_limpia["admin"], autocommit=True) as c:
            while corriendo:
                vistos.append(c.execute(
                    "SELECT count(*) FROM fragmento WHERE norm_id = %s", (ds1["id"],)).fetchone()[0])
                await asyncio.sleep(0)

    tarea = asyncio.create_task(observar())
    r = await sincronizar(fabrica_cliente(), base_sincronizador, embeddings)
    corriendo = False
    await tarea

    assert r.versiones_nuevas == 1
    with psycopg.connect(base_limpia["admin"]) as c:
        versiones = [x[0] for x in c.execute(
            "SELECT DISTINCT version_id::text FROM fragmento WHERE norm_id = %s", (ds1["id"],))]
    assert versiones == [nueva]
    assert 0 not in vistos
    # el cambio queda registrado artículo por artículo, para el agente de monitoreo
    [cambio] = r.cambios
    assert cambio.version_nueva == nueva and cambio.etiqueta == "DS 1/2013"
    assert set(cambio.modificados) == {"18", "19"} and cambio.nuevos == [] and cambio.derogados == []


async def test_una_norma_que_falla_no_se_pierde(fabrica_cliente, base_sincronizador, embeddings, estado_backend):
    ds40 = next(n for n in estado_backend.datos["normas"] if n["norm_number"] == "40/2012")
    ruta = f"/api/v1/catalog/norms/{ds40['id']}/versions"
    estado_backend.fallas[ruta] = 99  # 500 siempre

    r = await sincronizar(fabrica_cliente(), base_sincronizador, embeddings)
    assert [e.norm_id for e in r.errores] == [ds40["id"]]
    assert r.updated_at_maximo < datetime.fromisoformat(ds40["updated_at"])

    estado_backend.fallas.clear()
    r2 = await sincronizar(fabrica_cliente(), base_sincronizador, embeddings)
    assert r2.errores == []
    assert r2.versiones_nuevas >= 1  # el DS 40 se volvió a pedir y se indexó


async def test_la_normativa_propia_de_la_cuenta_de_servicio_no_entra_al_indice_publico(
    fabrica_cliente, base_sincronizador, embeddings, base_limpia
):
    """
    Encontrado el 21/09/2026 contra el backend real: /catalog/norms le devuelve a la cuenta de
    servicio la RCA de su propia empresa mezclada con el catálogo, sin tenant_id.
    """
    r = await sincronizar(fabrica_cliente(tenant=D.EMPRESA_A), base_sincronizador, embeddings)
    assert r.normas_omitidas == 1
    with psycopg.connect(base_limpia["admin"]) as c:
        rca = c.execute("SELECT count(*) FROM version_norma WHERE norm_number = '123/2019'").fetchone()[0]
    assert rca == 0


async def test_si_no_se_puede_saber_que_es_propio_no_se_indexa_nada(
    fabrica_cliente, base_sincronizador, embeddings, estado_backend, base_limpia
):
    from ambienta_ia.backend import BackendCaido

    estado_backend.fallas["/api/v1/compliance/normativa-propia/"] = 99
    with pytest.raises(BackendCaido):
        await sincronizar(fabrica_cliente(), base_sincronizador, embeddings)
    with psycopg.connect(base_limpia["admin"]) as c:
        assert c.execute("SELECT count(*) FROM fragmento").fetchone()[0] == 0
