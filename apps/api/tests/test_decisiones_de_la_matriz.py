"""Las dos decisiones del 13-oct-2026 sobre la Matriz Legal (D y E).

## D · Una evaluacion es evidencia: no se borra

`DELETE /compliance/article-compliance/{id}` responde **403** y no borra. Una
evaluacion dice que se reviso un articulo, con que resultado y cuando: es la
respuesta de la empresa ante una fiscalizacion del periodo en que se hizo.

Y el indice unico pasa a ser **parcial** (`db/37`): era un CONSTRAINT, que en
Postgres no admite `WHERE`, asi que cubria tambien las filas retiradas y una
evaluacion borrada dejaba su articulo con **409 para siempre**. Medido antes de
arreglarlo: 9 filas asi en la base de desarrollo.

## E · Una norma que dejo de aplicar sale del porcentaje

La sincronizacion marca `not_applicable` lo que ya no le corresponde a la
empresa y conserva sus evaluaciones. Hasta esta decision seguian pesando en el
numero que la empresa muestra, mientras un **articulo** marcado "no aplica" ya
salia del calculo: el sistema era incoherente consigo mismo.

**Las dos pruebas de E miden antes y despues sobre la misma matriz** y
restauran el estado. Comparar contra una constante seria frágil: el seed cambia.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services.resumen_cumplimiento import resumir  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
BASE = "/api/v1/compliance"


@pytest.fixture(scope="module")
def cliente():
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
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
        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": empresa}
        )
        valor = db.execute(text(sql), params).scalar()
    if valor is None:
        pytest.skip(f"Falta el dato para la prueba: {sql}")
    return str(valor)


def _ejecutar(sql: str, empresa: str, **params) -> None:
    with SessionLocal() as db:
        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": empresa}
        )
        db.execute(text(sql), params)
        db.commit()


class TestLaEvaluacionNoSeBorra:
    def test_el_delete_responde_403_y_la_evaluacion_sigue_ahi(self, cliente) -> None:
        evaluacion = _uno(
            "SELECT id FROM article_compliance WHERE deleted_at IS NULL "
            "ORDER BY created_at LIMIT 1",
            EMPRESA_A,
        )

        r = cliente.delete(
            f"{BASE}/article-compliance/{evaluacion}",
            headers={"X-Tenant-Id": EMPRESA_A},
        )

        assert r.status_code == 403, r.text
        assert r.json()["detail"]["codigo"] == "evaluacion_es_evidencia"
        # **Y no se borro.** Un 403 que igual borra seria peor que no tener la
        # guarda: diria que no y haria que si.
        sigue = _uno(
            "SELECT count(*) FROM article_compliance WHERE id = :i AND deleted_at IS NULL",
            EMPRESA_A,
            i=evaluacion,
        )
        assert sigue == "1"

    def test_un_id_que_no_se_ve_sigue_dando_404(self, cliente) -> None:
        """El 403 no convierte el endpoint en un oraculo.

        Si respondiera 403 a cualquier id, la respuesta distinguiria "existe
        pero no es tuya" de "no existe", que es como se enumeran identificadores
        ajenos. Se comprueba la existencia **antes** de negar, con la sesion de
        la empresa: lo que RLS no ve no existe para ella, venga de otra empresa
        o de ninguna.

        Va con un id inventado y no con uno de la empresa B **a proposito**: la
        primera version pedia una evaluacion de B, B no tiene ninguna en el seed
        y la prueba se **saltaba**. Las dos entradas recorren el mismo
        `obtener_o_404`, y el caso entre empresas lo cubre
        `test_referencias_de_la_matriz.py`.
        """
        inventado = "00000000-0000-0000-0000-00000000dead"

        r = cliente.delete(
            f"{BASE}/article-compliance/{inventado}",
            headers={"X-Tenant-Id": EMPRESA_A},
        )

        assert r.status_code == 404, r.text


class TestUnaEvaluacionRetiradaNoBloqueaSuArticulo:
    def test_se_puede_volver_a_evaluar_el_articulo(self, cliente) -> None:
        """La trampa que `db/37` cierra: 409 para siempre.

        Se retira una evaluacion **por SQL** —la API ya no lo permite, y es lo
        que seguira pasando con una limpieza o una reparacion a mano— y se
        vuelve a crear por la API. Con el constraint no-parcial esto respondia
        409 y el articulo quedaba inevaluable.
        """
        # **El articulo tiene que ser de la norma de su fila.** El seed tiene
        # evaluaciones que no cumplen eso —dos de una RCA cuelgan de articulos
        # de la Ley 19.300— y desde el 21-sep la API las rechaza con 422. La
        # primera version de esta prueba tomaba "la primera evaluacion" y
        # fallaba con 422 acusando al indice, que no tenia nada que ver.
        fila = _uno(
            "SELECT ac.id || ' ' || ac.matrix_norm_id || ' ' || ac.article_id "
            "       || ' ' || ac.facility_id "
            "FROM article_compliance ac "
            "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id AND mn.deleted_at IS NULL "
            "JOIN legal_articles la ON la.id = ac.article_id "
            "JOIN legal_norm_versions v ON v.id = la.norm_version_id "
            "  AND v.norm_id = mn.norm_id "
            "WHERE ac.deleted_at IS NULL AND ac.facility_id IS NOT NULL "
            "ORDER BY ac.created_at LIMIT 1",
            EMPRESA_A,
        )
        evaluacion, matrix_norm, articulo, planta = fila.split()

        _ejecutar(
            "UPDATE article_compliance SET deleted_at = now() WHERE id = :i",
            EMPRESA_A,
            i=evaluacion,
        )
        nueva = None
        try:
            r = cliente.post(
                f"{BASE}/article-compliance",
                headers={"X-Tenant-Id": EMPRESA_A},
                json={
                    "matrix_norm_id": matrix_norm,
                    "article_id": articulo,
                    "facility_id": planta,
                },
            )
            assert r.status_code == 201, r.text
            nueva = r.json()["id"]
        finally:
            if nueva:
                _ejecutar(
                    "DELETE FROM article_compliance WHERE id = :i", EMPRESA_A, i=nueva
                )
            _ejecutar(
                "UPDATE article_compliance SET deleted_at = NULL WHERE id = :i",
                EMPRESA_A,
                i=evaluacion,
            )


class TestLaNormaQueDejoDeAplicarSaleDelPorcentaje:
    @pytest.fixture
    def norma_evaluada(self):
        """Una norma de la matriz de A con evaluaciones y que hoy aplica."""
        fila = _uno(
            "SELECT mn.id || ' ' || mn.matrix_id FROM matrix_norms mn "
            "JOIN article_compliance ac ON ac.matrix_norm_id = mn.id "
            "  AND ac.deleted_at IS NULL "
            "WHERE mn.deleted_at IS NULL AND mn.applicability <> 'not_applicable' "
            "GROUP BY mn.id, mn.matrix_id HAVING count(*) > 0 "
            "ORDER BY count(*) DESC LIMIT 1",
            EMPRESA_A,
        )
        matrix_norm, matriz = fila.split()
        anterior = _uno(
            "SELECT applicability FROM matrix_norms WHERE id = :i",
            EMPRESA_A,
            i=matrix_norm,
        )
        yield matrix_norm, matriz
        _ejecutar(
            "UPDATE matrix_norms SET applicability = :a WHERE id = :i",
            EMPRESA_A,
            a=anterior,
            i=matrix_norm,
        )

    def _resumen(self, matriz: str):
        with SessionLocal() as db:
            db.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": EMPRESA_A},
            )
            return resumir(db, matriz)

    def test_el_total_baja_y_la_norma_conserva_su_conteo(self, norma_evaluada) -> None:
        matrix_norm, matriz = norma_evaluada
        antes = self._resumen(matriz)
        suyos_antes = next(
            n.conteo.evaluables
            for n in antes.por_norma
            if str(n.matrix_norm_id) == matrix_norm
        )
        assert suyos_antes > 0, "la norma elegida no tiene articulos que contar"

        _ejecutar(
            "UPDATE matrix_norms SET applicability = 'not_applicable' WHERE id = :i",
            EMPRESA_A,
            i=matrix_norm,
        )
        despues = self._resumen(matriz)

        # El total de la empresa pierde exactamente los articulos de esa norma.
        assert despues.total.evaluables == antes.total.evaluables - suyos_antes

        # Y la ficha de la norma los conserva: son la evidencia del periodo en
        # que si le aplicaba. De ahi que `total` no sea la suma de `por_norma`.
        fila = next(
            n for n in despues.por_norma if str(n.matrix_norm_id) == matrix_norm
        )
        assert fila.applicability == "not_applicable"
        assert fila.conteo.evaluables == suyos_antes

    def test_el_tablero_usa_la_misma_regla(self, cliente, norma_evaluada) -> None:
        """Con el filtro en un solo lado, la matriz y el tablero se separan.

        Ya paso en este producto: la matriz decia 100 % y el tablero 6 % para la
        misma norma. De ahi que la constante viva en un solo modulo.
        """
        matrix_norm, _ = norma_evaluada
        antes = cliente.get(
            "/api/v1/dashboard/metrics", headers={"X-Tenant-Id": EMPRESA_A}
        ).json()

        _ejecutar(
            "UPDATE matrix_norms SET applicability = 'not_applicable' WHERE id = :i",
            EMPRESA_A,
            i=matrix_norm,
        )
        despues = cliente.get(
            "/api/v1/dashboard/metrics", headers={"X-Tenant-Id": EMPRESA_A}
        ).json()

        # Las metricas van anidadas bajo `global`.
        assert despues["global"]["articles_evaluated"] < antes["global"]["articles_evaluated"]
