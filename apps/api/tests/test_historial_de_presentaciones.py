"""Cada intento de presentar una declaracion, con su propio folio.

## El problema, y por que no era cosmetico

`obligations.external_receipt` guarda **un solo folio**. Una declaracion que se
rechaza y se vuelve a presentar produce dos, y con una sola columna el primero
se pierde al escribir el segundo — sin ningun error y sin que nada diga que
existio.

Eso importa porque el folio **es el comprobante**: lo unico que la empresa puede
mostrarle a un fiscalizador para sostener que declaro. Perder el de un intento
rechazado borra la prueba de que ese intento ocurrio, y con ella la fecha de la
primera presentacion — que es exactamente lo que se discute cuando hay un plazo
de por medio.

`declaration_submissions` existia desde el principio, con `version_no`,
`prepared_by`, `reviewed_by`, `submitted_by` y `external_folio`, y **nadie
escribia una sola fila**: tenia CRUD completo y cero llamadores. Mismo patron
que `bcn.sincronizar()` y `control_documental.py`.

## Donde se escribe, y por que ahi

En `services/declaracion.py`, no en el router. Hay cuatro caminos que mueven una
declaracion y cada uno vive en un endpoint distinto; con el rastro escrito
arriba, un endpoint nuevo se olvidaria y **no fallaria nada** — simplemente esa
presentacion no existiria. Es el mismo criterio que el registro de actividades,
enganchado al `flush` de la sesion.
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

from app.main import app  # noqa: E402

EMPRESA = "a0000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def cliente():
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible ({exc}). Hace falta docker compose.")

    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as c:
        c.headers["X-Tenant-Id"] = EMPRESA
        yield c


def _declaracion(cliente) -> str:
    r = cliente.post(
        "/api/v1/obligations/",
        json={
            "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
            "title": "Declaracion de prueba",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _historial(cliente, oid: str) -> list[dict]:
    r = cliente.get(f"/api/v1/obligations/{oid}/presentaciones")
    assert r.status_code == 200, r.text
    return r.json()


class TestElCicloCompleto:
    def test_dos_intentos_dejan_dos_folios(self, cliente) -> None:
        """El caso que motiva todo esto.

        Se presenta, la rechazan, se corrige, se vuelve a presentar y la
        aceptan. Son **dos presentaciones** y la obligacion solo puede guardar
        un folio.
        """
        oid = _declaracion(cliente)
        try:
            assert cliente.post(f"/api/v1/obligations/{oid}/submit").status_code == 200
            assert (
                cliente.post(
                    f"/api/v1/obligations/{oid}/reject",
                    json={"motivo": "Falta el anexo de emisiones"},
                ).status_code
                == 200
            )
            assert cliente.post(f"/api/v1/obligations/{oid}/submit").status_code == 200
            aceptar = cliente.post(
                f"/api/v1/obligations/{oid}/approve", json={"folio": "FOLIO-V2"}
            )
            assert aceptar.status_code == 200, aceptar.text

            historial = _historial(cliente, oid)
            assert len(historial) == 2, (
                f"Se presento dos veces y el historial tiene {len(historial)} "
                "filas. Cada intento es una presentacion."
            )

            por_version = {p["version_no"]: p for p in historial}
            assert por_version[1]["status"] == "rejected"
            assert por_version[2]["status"] == "accepted"
            assert por_version[2]["external_folio"] == "FOLIO-V2"

            # **El motivo del rechazo queda en SU intento.** En la obligacion se
            # sobrescribe con el del proximo; aca cada version conserva el suyo,
            # que es lo que deja ver por que hicieron falta dos vueltas.
            assert "anexo" in por_version[1]["submission_data"].get(
                "motivo_rechazo", ""
            )
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")

    def test_la_obligacion_conserva_el_ultimo_folio(self, cliente) -> None:
        """Los dos, no uno.

        Quitar `external_receipt` rompe la pantalla, que lo lee; dejar **solo**
        esa columna es el problema que este historial resuelve.
        """
        oid = _declaracion(cliente)
        try:
            cliente.post(f"/api/v1/obligations/{oid}/submit")
            cliente.post(
                f"/api/v1/obligations/{oid}/approve", json={"folio": "FOLIO-UNICO"}
            )

            obligacion = cliente.get(f"/api/v1/obligations/{oid}").json()
            assert obligacion["external_receipt"] == "FOLIO-UNICO"
            assert _historial(cliente, oid)[0]["external_folio"] == "FOLIO-UNICO"
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")

    def test_la_primera_presentacion_es_la_version_uno(self, cliente) -> None:
        oid = _declaracion(cliente)
        try:
            cliente.post(f"/api/v1/obligations/{oid}/submit")

            historial = _historial(cliente, oid)
            assert len(historial) == 1
            assert historial[0]["version_no"] == 1
            assert historial[0]["status"] == "submitted"
            assert historial[0]["submitted_at"] is not None
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")

    def test_guarda_el_periodo_de_entonces(self, cliente) -> None:
        """El periodo se copia al presentar, no se lee de la obligacion.

        Una declaracion puede cambiar de periodo despues; el historial tiene que
        decir contra que se presento **entonces**.

        Y hay una trampa: `Obligation` no tiene `period_label`, tiene
        `period_start` y `period_end`. La primera version escribia
        `obligacion.period_label` con un `hasattr` delante, o sea que **habria
        guardado `None` siempre y en silencio** — el defecto de campo descartado
        que este repositorio ya sufrio con `planned_start_date` y `process_id`.
        """
        r = cliente.post(
            "/api/v1/obligations/",
            json={
                "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
                "title": "Con periodo",
                "period_start": "2026-01-01",
                "period_end": "2026-06-30",
            },
        )
        assert r.status_code == 201, r.text
        oid = r.json()["id"]
        try:
            cliente.post(f"/api/v1/obligations/{oid}/submit")

            etiqueta = _historial(cliente, oid)[0]["period_label"]
            assert etiqueta and "2026-01-01" in etiqueta, (
                f"El periodo no llego al historial: {etiqueta!r}. Si es `None`, "
                "se esta escribiendo un campo que la obligacion no tiene."
            )
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")


class TestLoQueNoSeInventa:
    def test_una_declaracion_sin_presentar_no_tiene_historial(self, cliente) -> None:
        """Vacio, y eso es una respuesta — no un fallo."""
        oid = _declaracion(cliente)
        try:
            assert _historial(cliente, oid) == []
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")

    def test_aceptar_sin_presentacion_previa_no_fabrica_una(self, cliente) -> None:
        """Las declaraciones que ya estaban presentadas antes de que existiera
        este historial no tienen fila.

        Fabricarles una al aceptarlas seria inventar una presentacion que nadie
        registro, **con su fecha, su version y su autor, los tres falsos**. Y en
        un sistema de cumplimiento una fecha de presentacion inventada es
        exactamente el dato que se discute ante un fiscalizador.
        """
        from sqlalchemy import text

        from app.db import SessionLocal
        from app.deps import declarar

        oid = _declaracion(cliente)
        try:
            # Se la deja en `submitted` **por SQL**, saltandose el servicio: es
            # el estado en que quedaron las declaraciones anteriores al cambio.
            with SessionLocal() as db:
                declarar(db, EMPRESA)
                db.execute(
                    text("UPDATE obligations SET status = 'submitted' WHERE id = :o"),
                    {"o": oid},
                )
                db.commit()

            assert _historial(cliente, oid) == [], "el montaje no dejo el historial vacio"

            aceptar = cliente.post(
                f"/api/v1/obligations/{oid}/approve", json={"folio": "FOLIO-VIEJO"}
            )
            assert aceptar.status_code == 200, aceptar.text

            assert _historial(cliente, oid) == [], (
                "Aceptar fabrico una presentacion que nunca ocurrio. El "
                "historial vacio dice la verdad; una fila inventada no."
            )
            # El folio si queda en la obligacion: eso no se inventa, se acaba
            # de registrar.
            assert (
                cliente.get(f"/api/v1/obligations/{oid}").json()["external_receipt"]
                == "FOLIO-VIEJO"
            )
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")
