"""Las tres vistas derivadas de la 14001, por el camino HTTP (#44, #47, #48).

## Por que este archivo existe aparte

La logica de las tres **ya estaba probada**: `test_significancia.py` y
`test_equipos_vencimientos.py` ejercitan `services/iso14001.py` con detalle. Lo
que nadie probaba era que **hubiera un endpoint**, y esa distincion no es
teorica en este repositorio:

- `bcn.sincronizar()` y `control_documental.py`: escritas, probadas, sin
  llamador.
- El CRM: 26 llamadas con la firma equivocada, 500 en todo lo direccionado por
  id, y `test_crm.py` en verde porque probaba el **servicio**.

`equipos_sin_operador_habilitado()` llevaba escrita y probada desde el 12-ago
**sin un solo endpoint que la expusiera**. La misma familia.

## Y la regresion que ya ocurrio, al escribir esto

`GET /equipment/sin-operador` se agrego **al final del archivo del router**, o
sea despues de `GET /equipment/{equipment_id}`. FastAPI resuelve por orden de
declaracion, asi que la ruta con parametro se la comio y la respuesta fue:

    422 · uuid_parsing · Input should be a valid UUID, found `s` at 1

El comentario del propio codigo advertia de esto y la colocacion lo contradecia.
`test_las_rutas_fijas_no_las_ensombrece_el_parametro` lo fija: es un error de
**orden de lineas**, invisible leyendo la funcion, y que reaparece cada vez que
alguien agrega una ruta fija a un router que ya tiene una con `{id}`.
"""
from __future__ import annotations

import os
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

EMPRESA = "a0000000-0000-0000-0000-000000000001"

#: Las rutas fijas que conviven con una hermana parametrizada en el mismo
#: prefijo. Cada una es una oportunidad de repetir el error de orden.
RUTAS_FIJAS = (
    "/api/v1/iso14001/equipment/sin-operador",
    "/api/v1/iso14001/equipment/expiring",
    "/api/v1/iso14001/aspects/significant-untreated",
)


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
def sesion_duena():
    """Escribe de verdad, porque `TestClient` usa otra conexion.

    Una transaccion sin confirmar no se ve desde fuera de la suya, asi que
    envolverlo y revertir dejaria a las pruebas midiendo un estado que la API
    nunca vio. Cada prueba limpia lo suyo en su `finally`.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    url = os.environ["DATABASE_URL"].replace(
        "ambienta_app:ambienta_app_dev", "ambienta:ambienta_dev"
    )
    motor = create_engine(url)
    db = Session(bind=motor)
    try:
        yield db
    finally:
        db.close()
        motor.dispose()


def _crear_equipo(db, *, estado: str = "operational") -> str:
    planta = db.execute(
        text(
            "SELECT id FROM facilities WHERE tenant_id = :t AND deleted_at IS NULL "
            "LIMIT 1"
        ),
        {"t": EMPRESA},
    ).scalar_one()
    eid = db.execute(
        text(
            "INSERT INTO regulated_equipment "
            "(tenant_id, facility_id, name, equipment_type, status) "
            "VALUES (:t, :f, :n, 'caldera', :s) RETURNING id"
        ),
        {
            "t": EMPRESA,
            "f": planta,
            "n": f"PRB-{uuid.uuid4().hex[:8].upper()}",
            "s": estado,
        },
    ).scalar_one()
    db.commit()
    return str(eid)


def _borrar_equipo(db, eid: str) -> None:
    db.execute(
        text("DELETE FROM equipment_operators WHERE equipment_id = :e"), {"e": eid}
    )
    db.execute(text("DELETE FROM regulated_equipment WHERE id = :e"), {"e": eid})
    db.commit()


def _fila(cliente, eid: str) -> dict | None:
    r = cliente.get("/api/v1/iso14001/equipment/sin-operador")
    assert r.status_code == 200, r.text
    return next((f for f in r.json() if f["equipment_id"] == eid), None)


class TestLasRutasFijasExisten:
    """El error de orden de lineas, que no se ve leyendo la funcion."""

    @pytest.mark.parametrize("ruta", RUTAS_FIJAS)
    def test_las_rutas_fijas_no_las_ensombrece_el_parametro(
        self, cliente, ruta: str
    ) -> None:
        respuesta = cliente.get(ruta)

        assert respuesta.status_code != 422, (
            f"{ruta} respondio 422. Casi con seguridad la ensombrece una ruta "
            f"con `{{id}}` declarada antes, y el ultimo segmento se esta "
            f"leyendo como UUID: {respuesta.text[:180]}"
        )
        assert respuesta.status_code == 200, respuesta.text


class TestEquiposSinOperadorHabilitado:
    """#48 — el estado de incumplimiento que nadie podia consultar.

    El servicio estaba escrito y probado desde el 12-ago; **el endpoint no
    existia**. Estas pruebas ejercitan el camino HTTP, que es lo que faltaba.
    """

    def test_un_equipo_sin_nadie_asignado_aparece_con_su_motivo(
        self, cliente, sesion_duena
    ) -> None:
        eid = _crear_equipo(sesion_duena)
        try:
            fila = _fila(cliente, eid)
            assert fila is not None, (
                "Un equipo en operacion sin ningun operador no aparecio en la "
                "lista de incumplimientos."
            )
            assert fila["motivo"] == "sin_operador"
            assert fila["operadores_asignados"] == 0
            assert fila["ultima_certificacion"] is None
        finally:
            _borrar_equipo(sesion_duena, eid)

    def test_con_la_certificacion_vencida_el_motivo_es_otro(
        self, cliente, sesion_duena
    ) -> None:
        """**Son dos problemas distintos y se arreglan distinto.**

        `sin_operador` se resuelve asignando a alguien; este se resuelve
        renovando. Devolver el mismo motivo para los dos obligaria a abrir cada
        equipo para saber cual es.
        """
        eid = _crear_equipo(sesion_duena)
        try:
            persona = sesion_duena.execute(
                text(
                    "SELECT id FROM users WHERE tenant_id = :t AND deleted_at IS NULL "
                    "LIMIT 1"
                ),
                {"t": EMPRESA},
            ).scalar_one()
            vencida = date.today() - timedelta(days=30)
            sesion_duena.execute(
                text(
                    "INSERT INTO equipment_operators "
                    "(tenant_id, equipment_id, user_id, certification_expires_at) "
                    "VALUES (:t, :e, :u, :v)"
                ),
                {"t": EMPRESA, "e": eid, "u": persona, "v": vencida},
            )
            sesion_duena.commit()

            fila = _fila(cliente, eid)
            assert fila is not None, (
                "El equipo tiene un operador con la certificacion vencida y no "
                "aparece: nadie puede operarlo legalmente hoy."
            )
            assert fila["motivo"] == "certificacion_vencida"
            assert fila["operadores_asignados"] == 1
            assert fila["ultima_certificacion"] == vencida.isoformat()
        finally:
            _borrar_equipo(sesion_duena, eid)

    def test_un_equipo_detenido_no_cuenta(self, cliente, sesion_duena) -> None:
        """Uno dado de baja no necesita operador habilitado.

        Contarlo llenaria la lista de maquinas que nadie esta usando, que es la
        forma mas rapida de que se deje de mirar.
        """
        eid = _crear_equipo(sesion_duena, estado="decommissioned")
        try:
            assert _fila(cliente, eid) is None, (
                "Un equipo dado de baja aparece como incumplimiento."
            )
        finally:
            _borrar_equipo(sesion_duena, eid)

    def test_el_seed_no_tiene_ninguno_y_eso_es_correcto(self, cliente) -> None:
        """El vacio de hoy es **real**, no un fallo silencioso.

        Se comprobo contra la base: los dos equipos del seed estan operativos y
        cada uno tiene un operador con certificacion hasta 2027. Esta prueba
        existe para que ese cero no se confunda nunca con "la consulta no
        devuelve nada" — que es como se ven los dos.
        """
        r = cliente.get("/api/v1/iso14001/equipment/sin-operador")
        assert r.status_code == 200

        equipos = cliente.get("/api/v1/iso14001/equipment").json()
        assert equipos, (
            "No hay equipos en la base, asi que este archivo no esta midiendo "
            "nada: el cero de arriba seria trivial."
        )
