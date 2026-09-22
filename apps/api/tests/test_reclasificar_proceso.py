"""Un proceso se puede reclasificar en el mapa (ISO 9001 §4.4).

## Que estaba roto, medido el 10-sep-2026

`processes.process_type` existe en la base, es `NOT NULL`, tiene su CHECK con
tres valores, y **`ProcessRead` lo devuelve**. Lo que faltaba era del otro lado:
`ProcessUpdate` no lo declaraba.

Pydantic descarta en silencio lo que no declara, asi que la pantalla del mapa de
procesos mandaba el cambio, la API respondia **200** y no guardaba nada.
Reclasificar se veia funcionar y se perdia al recargar — que es peor que no
tener la funcion, porque nadie la reporta.

Es la misma familia que `planned_start_date` en el alta de una auditoria, que
`process_id` en el alta anidada de un item, y que las citas del chatbot.

## Por que importa

El mapa de procesos es lo que ISO 9001 pide identificar, y `audit_items` cuelga
de el: el informe de auditoria arma su matriz **por proceso**. Un proceso
clasificado mal —o que no se puede corregir— sale mal en el informe que lee un
certificador.
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


@pytest.fixture
def proceso(cliente):
    """Un proceso propio, para no reclasificar los del seed."""
    r = cliente.post(
        "/api/v1/processes/",
        json={
            "code": f"PRC-{uuid.uuid4().hex[:6].upper()}",
            "name": "Proceso de prueba",
            "process_type": "operational",
        },
    )
    assert r.status_code == 201, r.text
    creado = r.json()
    yield creado

    with SessionLocal() as db:
        declarar(db, EMPRESA)
        db.execute(text("DELETE FROM processes WHERE id = :i"), {"i": creado["id"]})
        db.commit()


class TestReclasificar:
    def test_el_tipo_cambia_y_se_relee(self, cliente, proceso) -> None:
        """El caso que motiva todo: antes respondia 200 y no guardaba."""
        assert proceso["process_type"] == "operational"

        r = cliente.patch(
            f"/api/v1/processes/{proceso['id']}", json={"process_type": "strategic"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["process_type"] == "strategic"

        # **Se relee de la base.** La respuesta del PATCH puede venir del objeto
        # en memoria, que es justo lo que hacia creer que se habia guardado.
        vuelto = cliente.get(f"/api/v1/processes/{proceso['id']}").json()
        assert vuelto["process_type"] == "strategic", (
            "el PATCH respondio bien y la base quedo igual: el campo se esta "
            "descartando en silencio"
        )

    def test_los_tres_tipos_del_CHECK_se_aceptan(self, cliente, proceso) -> None:
        """La lista del esquema y la del schema tienen que coincidir.

        Si la base admite uno que el schema rechaza, hay filas que no se pueden
        corregir por la API.
        """
        for tipo in ("strategic", "operational", "support"):
            r = cliente.patch(
                f"/api/v1/processes/{proceso['id']}", json={"process_type": tipo}
            )
            assert r.status_code == 200, f"{tipo}: {r.text}"
            assert r.json()["process_type"] == tipo

    def test_un_tipo_invalido_se_rechaza_en_el_borde(self, cliente, proceso) -> None:
        """**422 y no un error de integridad de Postgres.**

        Con `str` en vez de `Literal`, un valor equivocado viaja hasta la base y
        vuelve como violacion del CHECK: un mensaje que habla de una restriccion
        cuyo nombre no le dice nada a quien llama.
        """
        r = cliente.patch(
            f"/api/v1/processes/{proceso['id']}", json={"process_type": "estrategico"}
        )
        assert r.status_code == 422, r.text
        # El valor en espanol es el error probable: el frontend tiene su propio
        # vocabulario (`estrategico`/`operativo`/`apoyo`) y lo traduce.
        assert "process_type" in r.text

    def test_reclasificar_no_pisa_el_resto_de_la_ficha(self, cliente, proceso) -> None:
        """Un PATCH parcial no puede vaciar lo que no menciona."""
        cliente.patch(
            f"/api/v1/processes/{proceso['id']}", json={"process_type": "support"}
        )
        vuelto = cliente.get(f"/api/v1/processes/{proceso['id']}").json()
        assert vuelto["name"] == "Proceso de prueba"
        assert vuelto["code"] == proceso["code"]
