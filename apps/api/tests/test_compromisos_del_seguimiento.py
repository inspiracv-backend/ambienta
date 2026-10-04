"""Las salidas que la verificacion deja abiertas quedan comprometidas (ISO 9001 10.2.1 e y f).

Hasta el 4-oct eran dos casillas tri-estado y nada mas: alguien marcaba "Si",
cerraba el registro y **el sistema no volvia a mencionarlo**. El spec de
`gestion-mejoras` lo pedia desde su primera version.

Contra la base real, por el camino HTTP: lo que se mide es el endpoint, no el
servicio. Cada registro `[QA]` se borra al terminar.
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
from app.deps import declarar  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"
BASE = "/api/v1/audits/nonconformities"
COMPROMISOS = "/api/v1/audits/compromisos"


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
        c.headers["X-Tenant-Id"] = EMPRESA_A
        yield c


def _borrar(nc_id: str) -> None:
    with SessionLocal() as db:
        declarar(db, uuid.UUID(EMPRESA_A))
        for tabla in ("improvement_commitments", "improvement_stage_entries", "action_plans"):
            db.execute(text(f"DELETE FROM {tabla} WHERE nonconformity_id = :n"), {"n": nc_id})
        db.execute(text("DELETE FROM nonconformities WHERE id = :n"), {"n": nc_id})
        db.commit()


@pytest.fixture
def registro(cliente):
    """Un registro `[QA]` con su ciclo sembrado y todas sus etapas hechas."""
    cliente.headers["X-Tenant-Id"] = EMPRESA_A
    r = cliente.post(
        BASE + "/",
        json={
            "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
            "title": "[QA] Registro para medir las salidas comprometidas",
            "description": "Creado por las pruebas de compromisos.",
            "severity": "major",
        },
    )
    assert r.status_code == 201, r.text
    nc = r.json()["id"]
    cliente.post(f"{BASE}/{nc}/etapas")
    for etapa in cliente.get(f"{BASE}/{nc}/etapas").json():
        cliente.patch(f"{BASE}/{nc}/etapas/{etapa['id']}", json={"fecha_ejecucion": "2026-09-12"})
    yield nc
    _borrar(nc)


def _seguimiento(cliente, nc: str) -> dict:
    return next(e for e in cliente.get(f"{BASE}/{nc}/etapas").json() if e["kind"] == "seguimiento")


def _verificar(cliente, nc: str, **campos) -> None:
    seguimiento = _seguimiento(cliente, nc)
    r = cliente.patch(f"{BASE}/{nc}/etapas/{seguimiento['id']}", json=campos)
    assert r.status_code == 200, r.text


def _una_persona(cliente) -> str:
    return cliente.get("/api/v1/users/").json()[0]["id"]


class TestLaVerificacionCompromete:
    def test_marcar_que_si_deja_una_salida_pendiente(self, cliente, registro) -> None:
        _verificar(cliente, registro, eficaz=True, requiere_actualizar_riesgos=True)

        compromisos = cliente.get(f"{BASE}/{registro}/compromisos").json()
        assert [(c["kind"], c["status"]) for c in compromisos] == [
            ("matriz_riesgos", "pendiente")
        ]

    def test_las_dos_salidas_son_dos_compromisos(self, cliente, registro) -> None:
        _verificar(
            cliente,
            registro,
            eficaz=True,
            requiere_actualizar_riesgos=True,
            requiere_cambios_sgc=True,
        )

        assert {c["kind"] for c in cliente.get(f"{BASE}/{registro}/compromisos").json()} == {
            "matriz_riesgos",
            "documento_sgc",
        }

    def test_guardar_dos_veces_no_duplica(self, cliente, registro) -> None:
        _verificar(cliente, registro, eficaz=True, requiere_actualizar_riesgos=True)
        _verificar(cliente, registro, requiere_actualizar_riesgos=True, observaciones="otra vez")

        assert len(cliente.get(f"{BASE}/{registro}/compromisos").json()) == 1

    def test_decir_despues_que_no_no_retira_lo_prometido(self, cliente, registro) -> None:
        """Lo comprometido se cumple o se descarta con justificacion. Que se
        borre cambiando una casilla seria la puerta trasera de siempre."""
        _verificar(cliente, registro, eficaz=True, requiere_actualizar_riesgos=True)
        _verificar(cliente, registro, requiere_actualizar_riesgos=False)

        assert len(cliente.get(f"{BASE}/{registro}/compromisos").json()) == 1

    def test_sin_marcar_nada_no_hay_compromisos(self, cliente, registro) -> None:
        _verificar(cliente, registro, eficaz=True)

        assert cliente.get(f"{BASE}/{registro}/compromisos").json() == []


class TestComprometerAMano:
    """La matriz FODA no sale de una casilla del seguimiento: la agrega quien
    verifica, mirando si el hallazgo cambia una fortaleza o una amenaza."""

    def test_se_puede_comprometer_la_matriz_foda(self, cliente, registro) -> None:
        r = cliente.post(
            f"{BASE}/{registro}/compromisos",
            json={"kind": "matriz_foda", "descripcion": "Revisar la amenaza de proveedor unico"},
        )

        assert r.status_code == 201, r.text
        assert r.json()["status"] == "pendiente"
        assert r.json()["descripcion"] == "Revisar la amenaza de proveedor unico"

    def test_la_misma_salida_dos_veces_se_rechaza(self, cliente, registro) -> None:
        cliente.post(f"{BASE}/{registro}/compromisos", json={"kind": "matriz_foda"})

        r = cliente.post(f"{BASE}/{registro}/compromisos", json={"kind": "matriz_foda"})

        assert r.status_code == 409, r.text
        assert len(cliente.get(f"{BASE}/{registro}/compromisos").json()) == 1

    def test_un_tipo_inventado_se_rechaza(self, cliente, registro) -> None:
        r = cliente.post(f"{BASE}/{registro}/compromisos", json={"kind": "lo_que_sea"})

        assert r.status_code == 422, r.text


class TestCerrarUnaSalida:
    def test_descartarla_sin_decir_por_que_se_rechaza(self, cliente, registro) -> None:
        _verificar(cliente, registro, eficaz=True, requiere_cambios_sgc=True)
        compromiso = cliente.get(f"{BASE}/{registro}/compromisos").json()[0]

        r = cliente.patch(f"{COMPROMISOS}/{compromiso['id']}", json={"status": "descartada"})

        assert r.status_code == 422, r.text
        assert "por que" in r.text
        assert cliente.get(f"{BASE}/{registro}/compromisos").json()[0]["status"] == "pendiente"

    def test_descartarla_con_justificacion_la_conserva(self, cliente, registro) -> None:
        _verificar(cliente, registro, eficaz=True, requiere_cambios_sgc=True)
        compromiso = cliente.get(f"{BASE}/{registro}/compromisos").json()[0]

        r = cliente.patch(
            f"{COMPROMISOS}/{compromiso['id']}",
            json={"status": "descartada", "justificacion": "El procedimiento ya lo cubria"},
        )

        assert r.status_code == 200, r.text
        assert r.json()["status"] == "descartada"
        assert r.json()["justificacion"] == "El procedimiento ya lo cubria"
        assert r.json()["completada_en"] is not None

    def test_ejecutarla_la_cierra_con_fecha(self, cliente, registro) -> None:
        _verificar(cliente, registro, eficaz=True, requiere_actualizar_riesgos=True)
        compromiso = cliente.get(f"{BASE}/{registro}/compromisos").json()[0]

        r = cliente.patch(f"{COMPROMISOS}/{compromiso['id']}", json={"status": "ejecutada"})

        assert r.status_code == 200, r.text
        assert r.json()["completada_en"] is not None


class TestElCierreDelRegistro:
    def test_una_salida_sin_responsable_ni_fecha_no_deja_cerrar(self, cliente, registro) -> None:
        """No bloquea por existir —la salida tiene su propio plazo— sino por no
        tener a quien avisarle: el defecto original con otro nombre."""
        _verificar(cliente, registro, eficaz=True, requiere_actualizar_riesgos=True)

        r = cliente.get(f"{BASE}/{registro}/puede-cerrarse").json()

        assert r["puede"] is False
        assert "matriz_riesgos" in r["motivo"]

    def test_con_responsable_y_fecha_el_registro_se_cierra(self, cliente, registro) -> None:
        _verificar(cliente, registro, eficaz=True, requiere_actualizar_riesgos=True)
        compromiso = cliente.get(f"{BASE}/{registro}/compromisos").json()[0]
        cliente.patch(
            f"{COMPROMISOS}/{compromiso['id']}",
            json={"responsable_user_id": _una_persona(cliente), "due_date": "2026-12-01"},
        )

        assert cliente.get(f"{BASE}/{registro}/puede-cerrarse").json()["puede"] is True

    def test_la_salida_sobrevive_al_cierre_del_registro(self, cliente, registro) -> None:
        """Es el punto entero: antes se cerraba el registro y la promesa
        desaparecia de la vista."""
        _verificar(cliente, registro, eficaz=True, requiere_actualizar_riesgos=True)
        compromiso = cliente.get(f"{BASE}/{registro}/compromisos").json()[0]
        cliente.patch(
            f"{COMPROMISOS}/{compromiso['id']}",
            json={"responsable_user_id": _una_persona(cliente), "due_date": "2026-12-01"},
        )
        cierre = cliente.post(f"{BASE}/{registro}/close")
        assert cierre.status_code in (200, 201), cierre.text

        pendientes = cliente.get(COMPROMISOS, params={"estado": "pendiente", "limit": 500}).json()
        mio = [c for c in pendientes if c["nonconformity_id"] == registro]
        assert mio, "la salida comprometida desaparecio al cerrar el registro"
        assert mio[0]["nonconformity_code"].startswith("PRB-")


def test_las_salidas_de_una_empresa_no_se_ven_desde_otra(cliente, registro) -> None:
    _verificar(cliente, registro, eficaz=True, requiere_actualizar_riesgos=True)
    try:
        cliente.headers["X-Tenant-Id"] = EMPRESA_B
        ajenas = cliente.get(COMPROMISOS, params={"estado": "todos", "limit": 500}).json()
    finally:
        cliente.headers["X-Tenant-Id"] = EMPRESA_A

    assert all(c["nonconformity_id"] != registro for c in ajenas)
