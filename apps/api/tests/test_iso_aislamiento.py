"""Las claves foraneas del modulo ISO, contra lo que RLS deja ver (#44, #45).

## La fuga, medida

**Las claves foraneas de Postgres no pasan por Row Level Security.**
`fk_environmental_aspects_facility` solo exige que exista una fila en
`facilities` con ese id: no mira el tenant. Medido antes del arreglo:

    Planta de la empresa A: Planta Calama b0000000-...-0001
    La empresa B ve esa planta bajo RLS: 0 filas
    >>> ESCRITURA ACEPTADA: la empresa B colgo su aspecto de la planta de A

Cero filas visibles, y el `INSERT` aceptado igual. Es exactamente la fuga que ya
se midio y se corrigio en `POST /obligations/`, aca sobre cinco claves que
llegaban del cuerpo sin comprobar: `facility_id`, `process_id`,
`article_compliance_id`, `environmental_aspect_id` y `action_plan_id`.

**El dano no es solo una fila incoherente.** Distinguir "no existe" (falla la
restriccion) de "existe pero es de otro" (pasa) es un oraculo para enumerar
identificadores ajenos sin verlos nunca. Por eso las dos respuestas tienen que
ser **identicas**: mismo codigo y mismo mensaje.

Estas pruebas van por HTTP y no por el servicio, porque lo que se comprueba es
la guarda del router.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from app.main import app  # noqa: E402  (despues de fijar DATABASE_URL)

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"


@pytest.fixture(scope="module")
def cliente():
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        engine.connect().close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    engine.dispose()
    return TestClient(app)


@pytest.fixture(scope="module")
def planta_de_a():
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as con:
        con.execute(text("SET LOCAL ROLE ambienta_app"))
        con.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": EMPRESA_A}
        )
        fila = con.execute(
            text("SELECT id FROM facilities WHERE tenant_id = :t LIMIT 1"),
            {"t": EMPRESA_A},
        ).first()
    engine.dispose()
    if fila is None:
        pytest.skip("El seed no dejo plantas en la empresa A")
    return str(fila[0])


def _como(tenant: str) -> dict[str, str]:
    return {"X-Tenant-Id": tenant}


class TestUnaEmpresaNoPuedeApuntarALoDeOtra:
    def test_crear_un_aspecto_con_la_planta_ajena_se_rechaza(
        self, cliente, planta_de_a
    ) -> None:
        """El caso que estaba **aceptado** y quedaba escrito."""
        r = cliente.post(
            "/api/v1/iso14001/aspects",
            headers=_como(EMPRESA_B),
            json={
                "facility_id": planta_de_a,
                "activity": "Intento de fuga",
                "aspect": "Prueba",
                "impact_type": "Emision",
            },
        )
        assert r.status_code == 422, r.text
        assert "facility_id" in r.json()["detail"]

    def test_un_id_INVENTADO_responde_exactamente_lo_mismo(
        self, cliente
    ) -> None:
        """La mitad que evita el oraculo de existencia.

        Si "no existe" y "existe pero es de otro" dieran respuestas distintas,
        probando identificadores al azar se podrian enumerar los de otra
        empresa sin verlos nunca.
        """
        r = cliente.post(
            "/api/v1/iso14001/aspects",
            headers=_como(EMPRESA_B),
            json={
                "facility_id": str(uuid.uuid4()),
                "activity": "Intento con id inventado",
                "aspect": "Prueba",
                "impact_type": "Emision",
            },
        )
        assert r.status_code == 422, r.text
        assert "facility_id" in r.json()["detail"]

    def test_las_dos_respuestas_son_IDENTICAS(self, cliente, planta_de_a) -> None:
        """Mismo codigo y mismo mensaje, palabra por palabra."""
        cuerpo = {
            "activity": "Comparacion",
            "aspect": "Prueba",
            "impact_type": "Emision",
        }
        ajena = cliente.post(
            "/api/v1/iso14001/aspects",
            headers=_como(EMPRESA_B),
            json={**cuerpo, "facility_id": planta_de_a},
        )
        inventada = cliente.post(
            "/api/v1/iso14001/aspects",
            headers=_como(EMPRESA_B),
            json={**cuerpo, "facility_id": str(uuid.uuid4())},
        )
        assert ajena.status_code == inventada.status_code
        assert ajena.json() == inventada.json()

    def test_con_SU_PROPIA_planta_si_se_puede_crear(self, cliente) -> None:
        """Y esto es lo que impide que la guarda rechace todo.

        Una validacion que dice que no siempre no protege: bloquea el modulo, y
        las tres pruebas de arriba pasarian igual.
        """
        engine = create_engine(os.environ["DATABASE_URL"])
        with engine.connect() as con:
            con.execute(text("SET LOCAL ROLE ambienta_app"))
            con.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": EMPRESA_B},
            )
            fila = con.execute(
                text("SELECT id FROM facilities WHERE tenant_id = :t LIMIT 1"),
                {"t": EMPRESA_B},
            ).first()
        engine.dispose()
        if fila is None:
            pytest.skip("El seed no dejo plantas en la empresa B")

        r = cliente.post(
            "/api/v1/iso14001/aspects",
            headers=_como(EMPRESA_B),
            json={
                "facility_id": str(fila[0]),
                "activity": "Creacion legitima",
                "aspect": "Prueba",
                "impact_type": "Emision",
            },
        )
        assert r.status_code == 201, r.text
        # Se limpia: esta prueba escribe en una tabla viva.
        cliente.delete(
            f"/api/v1/iso14001/aspects/{r.json()['id']}", headers=_como(EMPRESA_B)
        )

    def test_un_riesgo_no_puede_colgar_del_aspecto_de_otra_empresa(
        self, cliente
    ) -> None:
        """`environmental_aspect_id` es la clave del vinculo de #49.

        Sin comprobarla, la trazabilidad §6.1.2 -> §6.1.4 de una empresa podria
        apuntar al aspecto de otra.
        """
        r = cliente.post(
            "/api/v1/iso14001/risks",
            headers=_como(EMPRESA_B),
            json={
                "code": f"R-{uuid.uuid4().hex[:6]}",
                "entry_type": "risk",
                "description": "Intento de fuga",
                "origin": "environmental_aspect",
                "environmental_aspect_id": str(uuid.uuid4()),
            },
        )
        assert r.status_code == 422, r.text
        assert "environmental_aspect_id" in r.json()["detail"]


class TestLaRutaLiteralNoQuedaTapada:
    def test_significant_untreated_responde_200_y_no_422(self, cliente) -> None:
        """FastAPI resuelve por **orden de declaracion**.

        Declarada despues de `/aspects/{aspect_id}`, esta ruta cae en la del
        parametro, que intenta leer "significant-untreated" como UUID y
        responde 422. Se midio: el endpoint existia en el OpenAPI y era
        **inalcanzable por HTTP**.

        Es el tipo de fallo que ninguna prueba del servicio ve, porque el
        servicio funciona perfectamente.
        """
        r = cliente.get(
            "/api/v1/iso14001/aspects/significant-untreated", headers=_como(EMPRESA_A)
        )
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)
