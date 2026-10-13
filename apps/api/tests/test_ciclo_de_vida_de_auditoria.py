"""El ciclo de vida de una auditoria, y que su vocabulario sea el de la base.

## Que estaba roto

`AUDIT_STATUS_TRANSITIONS` nombraba `in_progress`, `fieldwork` y `review`. El
CHECK de `audits.status` admite `planned|active|reporting|closed|cancelled`, y
esos tres no estan. Consecuencia medida el 4-sep: de una auditoria recien
creada, **el unico avance posible era cancelarla**.

Lo que hace dificil de ver un defecto asi es que los dos errores se leen como
cosas distintas y ninguno nombra la causa:

| intento | respuesta | como se lee |
|---|---|---|
| `planned -> in_progress` | 422 `audits_status_check` | "mande un dato mal" |
| `planned -> active` | 400 "no permitida" | "ese paso no existe" |

Es la misma familia que `fulfill` escribiendo un estado fuera del CHECK, y que
`normSemaforo(0)`: dos mitades del sistema que hablan idiomas distintos y se
encuentran recien en tiempo de ejecucion.

## Por que la primera prueba lee la base

Comparar la tabla de Python contra una lista escrita a mano aca no protege de
nada: seria una tercera copia del mismo vocabulario, que se puede desincronizar
igual. La prueba **le pregunta al CHECK**, que es quien decide.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import date, timedelta

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from sqlalchemy import text  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.audits import AUDIT_STATUS_TRANSITIONS  # noqa: E402

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


@pytest.fixture(scope="module")
def planta(cliente) -> str:
    return cliente.get("/api/v1/facilities/").json()[0]["id"]


def _estados_que_admite_la_base() -> set[str]:
    from app.db import SessionLocal

    with SessionLocal() as db:
        definicion = db.scalar(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE contype = 'c' AND conrelid = 'audits'::regclass "
                "AND pg_get_constraintdef(oid) LIKE '%status%'"
            )
        )
    assert definicion, "no se encontro el CHECK de audits.status"
    return set(re.findall(r"'([a-z_]+)'::character varying", definicion))


def _crear_auditoria(cliente, planta: str) -> str:
    hoy = date.today()
    respuesta = cliente.post(
        "/api/v1/audits/",
        json={
            "facility_id": planta,
            "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
            "title": "Auditoria de prueba",
            "audit_type": "internal",
            "scope": "Alcance de prueba",
            "planned_start": str(hoy),
            "planned_end": str(hoy + timedelta(days=2)),
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


class TestElVocabularioEsElDeLaBase:
    def test_ningun_estado_de_la_maquina_esta_fuera_del_check(self) -> None:
        admitidos = _estados_que_admite_la_base()

        nombrados = set(AUDIT_STATUS_TRANSITIONS) | {
            destino
            for destinos in AUDIT_STATUS_TRANSITIONS.values()
            for destino in destinos
        }

        assert nombrados <= admitidos, (
            f"La maquina de estados nombra {sorted(nombrados - admitidos)}, que el "
            "CHECK de audits.status no admite. Avanzar a uno de esos responde 422 "
            "y el mensaje habla del dato enviado, no de la tabla de transiciones."
        )

    def test_todo_estado_de_la_base_tiene_salida_declarada(self) -> None:
        """Un estado que el CHECK admite y la maquina no nombra es una auditoria
        que puede quedar ahi sin ningun avance posible."""
        faltan = _estados_que_admite_la_base() - set(AUDIT_STATUS_TRANSITIONS)

        assert not faltan, (
            f"{sorted(faltan)} son estados que la base admite y la maquina no "
            "conoce: una auditoria que llegue ahi no tiene salida declarada."
        )


class TestElAvanceFunciona:
    """Lo que la tabla de arriba no puede comprobar: que el camino se recorra.

    Las dos pruebas anteriores pasarian con una maquina coherente y vacia. Esta
    ejecuta el ciclo entero contra la base, que es lo que fallaba.
    """

    def test_el_ciclo_completo_hasta_cerrada(self, cliente, planta) -> None:
        auditoria = _crear_auditoria(cliente, planta)
        try:
            for destino in ("active", "reporting", "closed"):
                respuesta = cliente.post(
                    f"/api/v1/audits/{auditoria}/advance?new_status={destino}"
                )
                assert respuesta.status_code == 200, (
                    f"Avanzar a '{destino}' respondio {respuesta.status_code}. "
                    f"Un avance del ciclo normal no puede fallar: {respuesta.text[:200]}"
                )
                assert respuesta.json()["status"] == destino
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")

    def test_empezar_anota_cuando_empezo(self, cliente, planta) -> None:
        """`actual_start` es lo que distingue la fecha planificada de la real, y
        se anotaba en un estado que nunca se alcanzaba."""
        auditoria = _crear_auditoria(cliente, planta)
        try:
            respuesta = cliente.post(
                f"/api/v1/audits/{auditoria}/advance?new_status=active"
            )
            assert respuesta.status_code == 200, respuesta.text
            assert respuesta.json()["actual_start"] is not None, (
                "Pasar a 'active' no anoto actual_start: la auditoria queda sin "
                "fecha de inicio real y solo con la planificada."
            )
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")

    def test_un_salto_fuera_del_orden_se_rechaza_como_transicion(
        self, cliente, planta
    ) -> None:
        """Y con 400, no con 422: el dato enviado es valido, lo que no vale es
        el paso. Distinguirlo es lo que le dice a quien llama que corrija el
        orden y no el campo."""
        auditoria = _crear_auditoria(cliente, planta)
        try:
            respuesta = cliente.post(
                f"/api/v1/audits/{auditoria}/advance?new_status=closed"
            )
            assert respuesta.status_code == 400, respuesta.text
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")
