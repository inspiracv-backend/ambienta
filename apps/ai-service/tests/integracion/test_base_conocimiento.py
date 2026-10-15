"""SPEC-03 · La base del AI Service aísla por empresa aunque el código se equivoque."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from ambienta_ia.conocimiento import abrir_base
from ambienta_ia.conocimiento.migrar import migrar

pytestmark = pytest.mark.integracion

A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
B = uuid.UUID("a0000000-0000-0000-0000-000000000002")


def _sembrar(admin: str) -> None:
    vec = "[" + ",".join(["1"] + ["0"] * 255) + "]"
    with psycopg.connect(admin, autocommit=True) as c:
        for tenant, nombre in ((None, "publica"), (A, "privada-a")):
            vid = uuid.uuid4()
            c.execute(
                "INSERT INTO version_norma (id, norm_id, tenant_id, norm_type, titulo, is_current, content_hash) "
                "VALUES (%s, %s, %s, 'ley', %s, true, 'h')",
                (vid, uuid.uuid4(), tenant, nombre),
            )
            c.execute(
                "INSERT INTO fragmento (article_id, version_id, norm_id, tenant_id, article_type, ruta, texto, "
                "embedding, modelo_embedding) SELECT %s, id, norm_id, tenant_id, 'articulo', %s, %s, %s::vector, 'm' "
                "FROM version_norma WHERE id = %s",
                (uuid.uuid4(), nombre, nombre, vec, vid),
            )


async def _textos(url: str, tenant) -> set[str]:
    base = await abrir_base(url, maximo=1)
    try:
        async with base.de_empresa(tenant) as conn:
            cur = await conn.execute("SELECT texto FROM fragmento")  # sin ningún WHERE
            return {f[0] for f in await cur.fetchall()}
    finally:
        await base.cerrar()


async def test_un_fragmento_privado_no_se_ve_desde_otra_empresa(base_limpia):
    _sembrar(base_limpia["admin"])
    assert await _textos(base_limpia["consulta"], B) == {"publica"}
    assert await _textos(base_limpia["consulta"], A) == {"publica", "privada-a"}


async def test_sin_empresa_fijada_no_se_ve_nada_privado(base_limpia):
    _sembrar(base_limpia["admin"])
    assert await _textos(base_limpia["consulta"], None) == {"publica"}


def test_el_rol_del_servicio_no_puede_saltarse_rls(base_limpia):
    with psycopg.connect(base_limpia["admin"]) as c:
        for rol in ("ia_consulta", "ia_sincronizador"):
            super_, bypass = c.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", (rol,)
            ).fetchone()
            assert not super_ and not bypass
        duenos = {r[0] for r in c.execute(
            "SELECT tableowner FROM pg_tables WHERE tablename IN ('fragmento', 'version_norma')"
        )}
        assert not duenos & {"ia_consulta", "ia_sincronizador"}


def test_el_rol_de_consulta_no_puede_escribir(base_limpia):
    with psycopg.connect(base_limpia["consulta"]) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        c.execute("DELETE FROM fragmento")


def test_el_sincronizador_no_puede_escribir_filas_privadas(base_limpia):
    with psycopg.connect(base_limpia["sincronizador"]) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        c.execute(
            "INSERT INTO version_norma (id, norm_id, tenant_id, norm_type, titulo, is_current, content_hash) "
            "VALUES (%s, %s, %s, 'ley', 'x', true, 'h')",
            (uuid.uuid4(), uuid.uuid4(), A),
        )


def test_migrar_dos_veces_no_hace_nada_la_segunda(base_de_prueba):
    hechas = migrar(base_de_prueba["admin"], dimension=256, clave_consulta="clave-de-prueba",
                    clave_sincronizador="clave-de-prueba")
    assert hechas == ["000_roles"]  # los roles se reaplican siempre (las claves pueden rotar)
