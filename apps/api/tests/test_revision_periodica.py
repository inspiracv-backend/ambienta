"""La revision periodica de cada norma de la matriz (ISO 14001 §9.1.2).

`review_frequency` estaba declarada en las siete normas del seed y
`next_review_date` vacia en las siete: nadie calculaba la fecha, asi que el
calendario no podia avisar que una evaluacion periodica vencio.
"""
from __future__ import annotations

import os
from datetime import date

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from app.services.revision_periodica import (  # noqa: E402
    EVALUADA_SIN_FECHA,
    MESES_POR_FRECUENCIA,
    NUNCA_EVALUADA,
    POR_EVENTO,
    proxima,
    sumar_meses,
)

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
RUTA = "/api/v1/compliance/matrix-norms/revisiones"


# ── Las fechas ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "dia,meses,esperado",
    [
        (date(2026, 9, 2), 12, date(2027, 9, 2)),
        (date(2026, 9, 2), 3, date(2026, 12, 2)),
        # Cruza el anio.
        (date(2026, 11, 15), 3, date(2027, 2, 15)),
        # El dia no existe en el mes de destino: el ultimo, no el siguiente mes.
        (date(2026, 8, 31), 6, date(2027, 2, 28)),
        (date(2027, 8, 31), 6, date(2028, 2, 29)),
        (date(2026, 11, 30), 3, date(2027, 2, 28)),
    ],
)
def test_sumar_meses_no_se_corre_de_mes(dia, meses, esperado) -> None:
    assert sumar_meses(dia, meses) == esperado


def test_la_fecha_declarada_manda() -> None:
    """La empresa puede tener motivos que el sistema no conoce."""
    fecha, origen, motivo = proxima("annual", date(2026, 10, 1), date(2026, 9, 2), True)

    assert (fecha, origen, motivo) == (date(2026, 10, 1), "declarada", None)


def test_sin_declarada_se_calcula_con_la_ultima_evaluacion() -> None:
    fecha, origen, motivo = proxima("semiannual", None, date(2026, 9, 2), True)

    assert (fecha, origen, motivo) == (date(2027, 3, 2), "calculada", None)


def test_por_evento_no_inventa_una_fecha() -> None:
    assert proxima("event_based", None, date(2026, 9, 2), True) == (None, None, POR_EVENTO)


def test_sin_evaluar_dice_por_que_no_hay_fecha() -> None:
    assert proxima("annual", None, None, False) == (None, None, NUNCA_EVALUADA)
    # Evaluada, pero en filas sin `assessed_at`: no es lo mismo que nunca.
    assert proxima("annual", None, None, True) == (None, None, EVALUADA_SIN_FECHA)


# ── Por la API ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def filas():
    import psycopg

    try:
        psycopg.connect(os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")).close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible ({exc}).")
    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    with TestClient(app) as c:
        r = c.get(RUTA, headers={"X-Tenant-Id": EMPRESA_A})
    # **200 y no 422**: declarada despues de `/matrix-norms/{mn_id}`, esa ruta
    # leeria "revisiones" como UUID.
    assert r.status_code == 200, r.text
    if not r.json():  # pragma: no cover
        pytest.skip("la matriz de la empresa no tiene normas")
    return r.json()


def test_cada_fila_tiene_fecha_o_dice_por_que_no(filas) -> None:
    for f in filas:
        assert (f["proxima_revision"] is None) == (f["motivo_sin_fecha"] is not None), f
        assert (f["proxima_revision"] is None) == (f["origen"] is None), f


def test_la_calculada_es_la_ultima_evaluacion_mas_la_frecuencia(filas) -> None:
    calculadas = [f for f in filas if f["origen"] == "calculada"]
    if not calculadas:  # pragma: no cover
        pytest.skip("ninguna norma evaluada con fecha")
    for f in calculadas:
        ultima = date.fromisoformat(f["ultima_evaluacion"])
        esperado = sumar_meses(ultima, MESES_POR_FRECUENCIA[f["frecuencia"]])
        assert date.fromisoformat(f["proxima_revision"]) == esperado, f


def test_lo_mas_proximo_primero_y_lo_sin_fecha_al_final(filas) -> None:
    fechas = [f["proxima_revision"] for f in filas]
    con_fecha = [d for d in fechas if d is not None]
    assert con_fecha == sorted(con_fecha)
    assert fechas[: len(con_fecha)] == con_fecha
