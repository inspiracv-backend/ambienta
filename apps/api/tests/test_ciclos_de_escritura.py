"""El ciclo de escritura completo de los recursos del camino de demostración.

## Por que existe

`test_humo_de_routers.py` ejecuta las **lecturas** sin parametros: 53 de 289
operaciones, el 18 %. Las escrituras —crear, editar, retirar— no las ejecutaba
nadie, y ahi vivian los 26 defectos del CRM y los tres del registro de mejora.

Este archivo recorre el ciclo entero de los recursos por los que pasa una
demostracion: **crear, leer, editar, retirar**. No comprueba que la respuesta
sea la correcta —para eso estan las pruebas de cada modulo— sino que la
operacion **se ejecute**.

## Por que pasa por `TestClient` y no llama al handler

Es la leccion del 4-sep, y costo una sonda entera. Llamar a la funcion del
router directo se salta los **manejadores de excepcion de la aplicacion**, asi
que un dato invalido —que `app/errores.py` traduce a un 422 con el nombre de la
restriccion— aparece como una excepcion sin atrapar y se lee como un fallo del
servidor.

Con esa sonda casi se publica que "89 campos devuelven 500 con un valor fuera
del CHECK". Por el camino real dan **422**, con la restriccion nombrada. El
metodo de medicion decide que defectos se pueden ver, y tambien cuales se
inventan.

Los dos caminos sirven para cosas distintas:

| Camino | Caza | No caza |
|---|---|---|
| Handler directo | firmas mal escritas (el CRM, `verify`) | nada que dependa de los manejadores |
| `TestClient` | el ciclo real de una peticion | lo que agrega uvicorn (cabeceras, limites) |

## Lo que se limpia, y en que sentido

Cada prueba llama al `DELETE` de lo que creo. **Eso es borrado logico**: la fila
queda con `deleted_at` y desaparece de los listados, pero sigue en la tabla. Se
dice asi y no «borra» porque son cosas distintas y la diferencia importa: las
filas se acumulan corrida tras corrida.

No ensucian la demostracion —los listados filtran por `deleted_at IS NULL`— y
todas llevan el prefijo `PRB-`, asi que se pueden barrer cuando molesten:

    DELETE FROM obligations WHERE code LIKE 'PRB-%' AND deleted_at IS NOT NULL;

Se prefiere esto a que cada prueba abra su propia transaccion y la revierta:
pasar por `TestClient` significa pasar por las sesiones que abre la aplicacion,
y envolverlas desde afuera obligaria a intervenir `get_tenant_db` — o sea, a
probar algo que no es lo que corre.
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
        pytest.skip(
            f"Sin base de datos disponible ({exc}). Esto NO comprueba los ciclos "
            "de escritura: hace falta `docker compose up -d`."
        )

    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as c:
        c.headers["X-Tenant-Id"] = EMPRESA
        yield c


@pytest.fixture(scope="module")
def planta(cliente) -> str:
    plantas = cliente.get("/api/v1/facilities/").json()
    assert plantas, "el seed tiene plantas en esta empresa"
    return plantas[0]["id"]


@pytest.fixture(scope="module")
def persona(cliente) -> str:
    gente = cliente.get("/api/v1/users/").json()
    assert gente, "el seed tiene usuarios en esta empresa"
    return gente[0]["id"]


def _codigo() -> str:
    return f"PRB-{uuid.uuid4().hex[:8].upper()}"


def _sin_5xx(respuesta, que: str) -> None:
    assert respuesta.status_code < 500, (
        f"{que} respondio {respuesta.status_code}. Un 5xx en una escritura bien "
        f"formada es codigo que nunca se ejecuto: {respuesta.text[:300]}"
    )


class TestObligaciones:
    """El nucleo del producto: lo que vence y hay que declarar."""

    def test_ciclo_completo(self, cliente) -> None:
        crear = cliente.post(
            "/api/v1/obligations/",
            json={"code": _codigo(), "title": "Declaracion de prueba"},
        )
        _sin_5xx(crear, "POST /obligations/")
        assert crear.status_code == 201
        oid = crear.json()["id"]

        try:
            _sin_5xx(cliente.get(f"/api/v1/obligations/{oid}"), "GET por id")
            editar = cliente.patch(
                f"/api/v1/obligations/{oid}", json={"title": "Otro titulo"}
            )
            _sin_5xx(editar, "PATCH")
            assert editar.json()["title"] == "Otro titulo"
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")

    def test_las_tareas_de_una_obligacion(self, cliente) -> None:
        oid = cliente.post(
            "/api/v1/obligations/",
            json={"code": _codigo(), "title": "Con tareas"},
        ).json()["id"]
        try:
            crear = cliente.post(
                f"/api/v1/obligations/{oid}/tasks", json={"title": "Tarea de prueba"}
            )
            _sin_5xx(crear, "POST /obligations/{id}/tasks")
            tid = crear.json()["id"]

            _sin_5xx(cliente.get(f"/api/v1/obligations/{oid}/tasks"), "GET tareas")
            _sin_5xx(cliente.get(f"/api/v1/obligations/tasks/{tid}"), "GET tarea")
            _sin_5xx(
                cliente.patch(
                    f"/api/v1/obligations/tasks/{tid}", json={"title": "Otra"}
                ),
                "PATCH tarea",
            )
            _sin_5xx(
                cliente.delete(f"/api/v1/obligations/tasks/{tid}"), "DELETE tarea"
            )
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")

    def test_presentar_la_declaracion(self, cliente) -> None:
        """RF-31. `fulfill` respondia 422 en el 100 % de los casos hasta el
        26-ago: escribia un estado que el CHECK no admite."""
        oid = cliente.post(
            "/api/v1/obligations/", json={"code": _codigo(), "title": "Para presentar"}
        ).json()["id"]
        try:
            _sin_5xx(cliente.post(f"/api/v1/obligations/{oid}/submit"), "submit")
        finally:
            cliente.delete(f"/api/v1/obligations/{oid}")


class TestIso14001:
    """Aspectos, riesgos y equipos: las tres matrices de la 14001."""

    def test_ciclo_de_un_aspecto_ambiental(self, cliente, planta) -> None:
        crear = cliente.post(
            "/api/v1/iso14001/aspects",
            json={
                "facility_id": planta,
                "activity": "Actividad de prueba",
                "aspect": "Emision de prueba",
                "impact_type": "aire",
            },
        )
        _sin_5xx(crear, "POST /iso14001/aspects")
        assert crear.status_code == 201
        aid = crear.json()["id"]

        try:
            _sin_5xx(cliente.get(f"/api/v1/iso14001/aspects/{aid}"), "GET aspecto")
            _sin_5xx(
                cliente.patch(
                    f"/api/v1/iso14001/aspects/{aid}", json={"activity": "Otra"}
                ),
                "PATCH aspecto",
            )
        finally:
            cliente.delete(f"/api/v1/iso14001/aspects/{aid}")

    def test_ciclo_de_un_riesgo(self, cliente, planta) -> None:
        crear = cliente.post(
            "/api/v1/iso14001/risks",
            json={
                "facility_id": planta,
                "code": _codigo(),
                "entry_type": "risk",
                "description": "Riesgo de prueba",
                "origin": "context",
            },
        )
        _sin_5xx(crear, "POST /iso14001/risks")
        rid = crear.json()["id"]

        try:
            _sin_5xx(cliente.get(f"/api/v1/iso14001/risks/{rid}"), "GET riesgo")
            _sin_5xx(
                cliente.patch(
                    f"/api/v1/iso14001/risks/{rid}", json={"description": "Otro"}
                ),
                "PATCH riesgo",
            )
        finally:
            cliente.delete(f"/api/v1/iso14001/risks/{rid}")

    def test_ciclo_de_un_equipo_y_su_operador(self, cliente, planta, persona) -> None:
        """El operador con certificacion vigente es lo que distingue un equipo
        conforme de uno que no: `01_schema` lo dice explicito."""
        crear = cliente.post(
            "/api/v1/iso14001/equipment",
            json={
                "facility_id": planta,
                "name": "Caldera de prueba",
                "equipment_type": "caldera",
            },
        )
        _sin_5xx(crear, "POST /iso14001/equipment")
        eid = crear.json()["id"]

        try:
            _sin_5xx(cliente.get(f"/api/v1/iso14001/equipment/{eid}"), "GET equipo")
            _sin_5xx(
                cliente.patch(
                    f"/api/v1/iso14001/equipment/{eid}", json={"name": "Otra"}
                ),
                "PATCH equipo",
            )
            _sin_5xx(
                cliente.post(
                    f"/api/v1/iso14001/equipment/{eid}/operators/{persona}", json={}
                ),
                "POST operador",
            )
            _sin_5xx(
                cliente.get(f"/api/v1/iso14001/equipment/{eid}/operators"),
                "GET operadores",
            )
            _sin_5xx(
                cliente.delete(
                    f"/api/v1/iso14001/equipment/{eid}/operators/{persona}"
                ),
                "DELETE operador",
            )
        finally:
            cliente.delete(f"/api/v1/iso14001/equipment/{eid}")


class TestUnValorFueraDelCheckDa422:
    """La otra mitad, y la que corrige una medicion equivocada.

    `app/errores.py` traduce las violaciones de Postgres a respuestas de
    cliente: `CheckViolation` a **422 con el nombre de la restriccion**,
    `UniqueViolation` a 409. Existe desde antes, y una sonda que llamaba a los
    handlers directo —saltandose los manejadores— casi lo da por ausente.

    Estas pruebas fijan que sigue enchufado, porque desconectarlo devolveria
    toda esa familia a 500 sin que nada mas fallara.
    """

    @pytest.mark.parametrize(
        ("ruta", "cuerpo", "restriccion"),
        [
            (
                "/api/v1/audits/nonconformities/",
                {
                    "code": "PRB-Y",
                    "title": "t",
                    "description": "d",
                    "severity": "major",
                    "record_type": "INVENTADO",
                },
                "record_type",
            ),
        ],
    )
    def test_da_422_y_nombra_la_restriccion(
        self, cliente, ruta: str, cuerpo: dict, restriccion: str
    ) -> None:
        respuesta = cliente.post(ruta, json=cuerpo)

        assert respuesta.status_code == 422, (
            f"Un valor fuera del CHECK respondio {respuesta.status_code}. Un 500 "
            "dice que el problema es del servidor, y es del dato enviado."
        )
        assert restriccion in respuesta.json()["detail"], (
            "El 422 no dice que restriccion se violo, y sin eso quien llama "
            "tiene que adivinar cual de los campos corrigio mal."
        )

    def test_una_severidad_inventada_la_ataja_el_catalogo_antes(self, cliente) -> None:
        """Este caso **ya no llega al CHECK**, y es a proposito.

        Estaba en la lista de arriba: `severity: "INVENTADA"` viajaba hasta
        Postgres y volvia como 422 nombrando `nonconformities_severity_check`.
        Desde los catalogos por empresa (#41, RF-100) lo ataja antes
        `comprobar_severidad`, que es una barrera **mas estrecha** —la escala de
        esta empresa, no la de todas— y ademas contesta mejor: dice cuales hay.

        Se deja escrito en vez de borrar el caso porque un 422 que cambia de
        emisor se lee igual desde afuera, y sin esto la proxima persona que mire
        creeria que sigue probando `app/errores.py`. Quien lo prueba ahora es el
        caso de `record_type`, que no tiene catalogo y sigue bajando a la base.
        """
        respuesta = cliente.post(
            "/api/v1/audits/nonconformities/",
            json={
                "code": "PRB-SEV",
                "title": "t",
                "description": "d",
                "severity": "INVENTADA",
            },
        )

        assert respuesta.status_code == 422, respuesta.text
        detalle = respuesta.json()["detail"]
        assert "INVENTADA" in detalle, "el error no dice que valor se rechazo"
        assert "minor" in detalle, (
            "El error no enumera los niveles disponibles, y esa es la mitad de "
            "su utilidad: la escala es de cada empresa, asi que quien llama no "
            "puede adivinarla."
        )
