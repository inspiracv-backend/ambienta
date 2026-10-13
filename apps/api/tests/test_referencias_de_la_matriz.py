"""Las escrituras de la Matriz Legal no aceptan identificadores ajenos.

**Las claves foraneas no pasan por RLS** (`_comun.validar_visible`): una FK solo
exige que la fila exista, no que sea de la empresa. `routers/compliance.py` no
comprobaba ninguno de los identificadores que recibe en el cuerpo hasta el
21-sep —la evaluacion se podia colgar de la matriz, la planta o la persona de
otra empresa—, y ademas aceptaba evaluar un articulo **de otra norma**, que el
resumen cuenta despues en el porcentaje de la norma de la fila.

Cada rechazo se compara con el de un identificador inventado: si fueran
distintos, la respuesta diria que el ajeno existe.

La prueba positiva escribe de verdad en la base de desarrollo y despues retira
la fila con el `DELETE` de la API (borrado logico).
"""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"
BASE = "/api/v1/compliance"


@pytest.fixture(scope="module")
def cliente():
    import psycopg

    try:
        psycopg.connect(os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")).close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible ({exc}).")
    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c


def _uno(sql: str, empresa: str, **params):
    """Un valor leido **con la empresa declarada**, como lo veria ella."""
    with SessionLocal() as db:
        db.execute(text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": empresa})
        valor = db.execute(text(sql), params).scalar()
    if valor is None:
        pytest.skip(f"Falta el dato para la prueba: {sql}")
    return str(valor)


@pytest.fixture(scope="module")
def datos():
    """Una norma de la matriz de A con articulado vigente, y lo necesario de B."""
    # Una norma de la matriz con un articulo vigente que A todavia no evaluo:
    # el alta positiva no choca con una evaluacion que ya exista.
    par = (
        "SELECT mn.id::text || ' ' || a.id::text FROM matrix_norms mn "
        "JOIN legal_norm_versions v ON v.norm_id = mn.norm_id AND v.is_current AND v.deleted_at IS NULL "
        "JOIN legal_articles a ON a.norm_version_id = v.id AND a.deleted_at IS NULL "
        "WHERE mn.deleted_at IS NULL AND NOT EXISTS (SELECT 1 FROM article_compliance ac "
        "  WHERE ac.article_id = a.id AND ac.matrix_norm_id = mn.id) "
        "ORDER BY mn.id, a.id LIMIT 1"
    )
    fila_a, articulo_propio = _uno(par, EMPRESA_A).split()
    norma = _uno("SELECT norm_id FROM matrix_norms WHERE id = :m", EMPRESA_A, m=fila_a)
    articulo_de_otra_norma = _uno(
        "SELECT a.id FROM legal_articles a "
        "JOIN legal_norm_versions v ON v.id = a.norm_version_id "
        "JOIN legal_norms n ON n.id = v.norm_id AND n.tenant_id IS NULL AND n.deleted_at IS NULL "
        "WHERE v.norm_id <> :n AND a.deleted_at IS NULL ORDER BY a.id LIMIT 1",
        EMPRESA_A,
        n=norma,
    )
    version_de_otra_norma = _uno(
        "SELECT v.id FROM legal_norm_versions v JOIN legal_norms n ON n.id = v.norm_id "
        "WHERE n.tenant_id IS NULL AND n.deleted_at IS NULL AND v.norm_id <> :n "
        "ORDER BY v.id LIMIT 1",
        EMPRESA_A,
        n=norma,
    )
    return {
        "fila_a": fila_a,
        "norma": norma,
        "matriz_a": _uno("SELECT matrix_id FROM matrix_norms WHERE id = :m", EMPRESA_A, m=fila_a),
        "articulo_propio": articulo_propio,
        "articulo_de_otra_norma": articulo_de_otra_norma,
        "version_vigente": _uno(
            "SELECT id FROM legal_norm_versions WHERE norm_id = :n AND is_current", EMPRESA_A, n=norma
        ),
        "version_de_otra_norma": version_de_otra_norma,
        "planta_a": _uno("SELECT id FROM facilities WHERE deleted_at IS NULL ORDER BY id LIMIT 1", EMPRESA_A),
        "planta_b": _uno("SELECT id FROM facilities WHERE deleted_at IS NULL ORDER BY id LIMIT 1", EMPRESA_B),
        "persona_b": _uno("SELECT id FROM users WHERE deleted_at IS NULL ORDER BY id LIMIT 1", EMPRESA_B),
    }


def _post(c, empresa: str, ruta: str, cuerpo: dict):
    return c.post(f"{BASE}{ruta}", json=cuerpo, headers={"X-Tenant-Id": empresa})


def _igual_que_inventado(ajena, inventada) -> None:
    assert ajena.status_code == inventada.status_code == 422, (ajena.text, inventada.text)
    assert ajena.json() == inventada.json()


class TestUnaEvaluacion:
    def test_de_la_propia_empresa_y_de_esa_norma_se_acepta(self, cliente, datos) -> None:
        """Control: si esto fallara, los rechazos de abajo no probarian nada."""
        r = _post(
            cliente,
            EMPRESA_A,
            "/article-compliance",
            {
                "matrix_norm_id": datos["fila_a"],
                "article_id": datos["articulo_propio"],
                "facility_id": datos["planta_a"],
                # Lo que manda la pantalla al excluir del calculo un articulo
                # sin evaluar. Hasta el 21-sep se descartaba con 201.
                "attributes": {"incluidoEnCalculo": False},
            },
        )
        try:
            assert r.status_code == 201, r.text
            assert r.json()["attributes"] == {"incluidoEnCalculo": False}
        finally:
            if r.status_code == 201:
                cliente.delete(f"{BASE}/article-compliance/{r.json()['id']}", headers={"X-Tenant-Id": EMPRESA_A})

    def test_contra_la_matriz_de_otra_empresa_se_rechaza(self, cliente, datos) -> None:
        cuerpo = {"article_id": datos["articulo_propio"]}
        ajena = _post(cliente, EMPRESA_B, "/article-compliance", {**cuerpo, "matrix_norm_id": datos["fila_a"]})
        inventada = _post(cliente, EMPRESA_B, "/article-compliance", {**cuerpo, "matrix_norm_id": str(uuid.uuid4())})
        _igual_que_inventado(ajena, inventada)

    def test_sobre_un_articulo_de_otra_norma_se_rechaza(self, cliente, datos) -> None:
        r = _post(
            cliente,
            EMPRESA_A,
            "/article-compliance",
            {"matrix_norm_id": datos["fila_a"], "article_id": datos["articulo_de_otra_norma"]},
        )
        assert r.status_code == 422, r.text
        assert "article_id" in r.text

    @pytest.mark.parametrize("campo,clave", [("facility_id", "planta_b"), ("responsible_user_id", "persona_b")])
    def test_con_la_planta_o_la_persona_de_otra_empresa_se_rechaza(self, cliente, datos, campo, clave) -> None:
        cuerpo = {"matrix_norm_id": datos["fila_a"], "article_id": datos["articulo_propio"]}
        ajena = _post(cliente, EMPRESA_A, "/article-compliance", {**cuerpo, campo: datos[clave]})
        inventada = _post(cliente, EMPRESA_A, "/article-compliance", {**cuerpo, campo: str(uuid.uuid4())})
        _igual_que_inventado(ajena, inventada)

    def test_cambiar_el_responsable_por_alguien_de_otra_empresa_se_rechaza(self, cliente, datos) -> None:
        evaluacion = _uno(
            "SELECT id FROM article_compliance WHERE deleted_at IS NULL ORDER BY id LIMIT 1", EMPRESA_A
        )
        r = cliente.patch(
            f"{BASE}/article-compliance/{evaluacion}",
            json={"responsible_user_id": datos["persona_b"]},
            headers={"X-Tenant-Id": EMPRESA_A},
        )
        assert r.status_code == 422, r.text


class TestUnaNormaDeLaMatriz:
    def test_en_la_matriz_de_otra_empresa_se_rechaza(self, cliente, datos) -> None:
        cuerpo = {"norm_id": datos["norma"], "selected_version_id": datos["version_vigente"]}
        ajena = _post(cliente, EMPRESA_B, "/matrix-norms", {**cuerpo, "matrix_id": datos["matriz_a"]})
        inventada = _post(cliente, EMPRESA_B, "/matrix-norms", {**cuerpo, "matrix_id": str(uuid.uuid4())})
        _igual_que_inventado(ajena, inventada)

    def test_con_la_version_de_otra_norma_se_rechaza(self, cliente, datos) -> None:
        r = _post(
            cliente,
            EMPRESA_A,
            "/matrix-norms",
            {
                "matrix_id": datos["matriz_a"],
                "norm_id": datos["norma"],
                "selected_version_id": datos["version_de_otra_norma"],
            },
        )
        assert r.status_code == 422, r.text
        assert "selected_version_id" in r.text


def test_una_matriz_de_la_planta_de_otra_empresa_se_rechaza(cliente, datos) -> None:
    cuerpo = {"name": "[QA] matriz", "period_year": 2098}
    ajena = _post(cliente, EMPRESA_B, "/matrices", {**cuerpo, "facility_id": datos["planta_a"]})
    inventada = _post(cliente, EMPRESA_B, "/matrices", {**cuerpo, "facility_id": str(uuid.uuid4())})
    _igual_que_inventado(ajena, inventada)
