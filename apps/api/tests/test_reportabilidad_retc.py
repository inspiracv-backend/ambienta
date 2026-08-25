"""Sistemas del RETC y reportabilidad por instalacion (#102, #103, ADR-004).

Lo que se fija aca no es que los endpoints respondan: es que **el catalogo no
mienta** y que la reportabilidad de una empresa no se vea desde otra.

## Por que el catalogo importa mas que el CRUD

Este catalogo dice ante quien tiene que declarar una empresa. Una fila de mas o
de menos no da un error: da una instalacion que cree estar cubierta y no lo
esta, o una que declara donde no le toca. Por eso cada fila lleva `fuente` y
todas nacen `active = false` — es un borrador que negocio tiene que firmar, no
un catalogo cerrado, y hay pruebas que lo sostienen.

## Dos mutaciones sobreviven, y estan medidas

Romper el codigo a proposito dejo dos huecos que **no se taparon con una prueba
falsa**:

1. Quitar la validacion de `estado` en el router no rompe nada, porque el CHECK
   de la base tambien responde 422. Es defensa duplicada, no cobertura que
   falte: el router valida para dar un mensaje util en vez de un error de
   restriccion a mitad del commit.
2. Quitar el filtro de `deleted_at` del catalogo tampoco rompe nada, porque hoy
   **no hay forma de dar de baja un sistema**: no se expone `DELETE`, a
   proposito. El filtro es defensa por si eso cambia.

Lo que si aparecio y era real: sin comprobar la instalacion, una empresa podia
declarar sobre la planta de otra y la API respondia 200. Tiene prueba propia.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TENANT_1 = "a0000000-0000-0000-0000-000000000001"
TENANT_2 = "a0000000-0000-0000-0000-000000000002"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
ADMIN_URL = os.getenv(
    "DATABASE_ADMIN_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
)


@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import SessionLocal
    from app.main import app

    monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)
    motor = create_engine(URL)
    try:
        motor.connect().close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    original = SessionLocal.kw.get("bind")
    SessionLocal.configure(bind=motor)
    try:
        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original)
        motor.dispose()


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    sesion.execute(text("SET LOCAL ROLE ambienta_app"))
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_1}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


@pytest.fixture
def limpiar():
    """Borra la reportabilidad que crearon las pruebas. Como dueno de la base."""
    ids: list[str] = []
    yield ids
    admin = create_engine(ADMIN_URL)
    try:
        with admin.begin() as c:
            for fid in ids:
                c.execute(
                    text("DELETE FROM facility_retc_reporting WHERE facility_id = :f"),
                    {"f": fid},
                )
    finally:
        admin.dispose()


def _instalacion(db: Session, tenant: str) -> uuid.UUID | None:
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": tenant}
    )
    fila = db.execute(text("SELECT id FROM facilities LIMIT 1")).scalar()
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT_1}
    )
    return fila


class TestElCatalogo:
    """#103. Lo que se sembró y —sobre todo— lo que NO."""

    def test_trae_los_doce_sistemas_de_la_ventanilla_unica(self, cliente) -> None:
        r = cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_1}
        )
        assert r.status_code == 200, r.text
        codigos = {s["code"] for s in r.json()}

        # Los del portal oficial, consultado el 25-ago-2026.
        assert {"SINADER", "SIDREP", "DJA", "RUEA", "LEY_REP", "RILES"} <= codigos
        assert len(r.json()) == 12

    def test_ninguno_viene_confirmado(self, cliente) -> None:
        """**`active = false` en todos, y es deliberado.**

        ADR-004 habla de 21 portales (12 sectoriales + 9 de la SMA) y cita una
        fuente que **no existe en el repositorio**. Sembrar 12 y darlos por
        cerrados haria que alguien citara "el catalogo del RETC" con nueve
        sistemas de menos.
        """
        r = cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_1}
        )
        assert all(s["active"] is False for s in r.json())

    def test_cada_fila_dice_de_donde_salio(self, cliente) -> None:
        """Sin procedencia, un catalogo normativo no se puede auditar ni
        actualizar: nadie sabe si una fila es de una resolucion o de la memoria
        de alguien."""
        r = cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_1}
        )
        for sistema in r.json():
            assert sistema["fuente"], f"{sistema['code']} no dice de donde salio"

    def test_no_se_sembraron_los_nueve_de_la_sma(self, cliente) -> None:
        """**Esto documenta un faltante, no una garantia.**

        Los 9 sistemas de la SMA que menciona ADR-004 no tienen fuente
        verificable, asi que no se inventaron. El dia que aparezca la lista,
        esta prueba debe fallar y reescribirse — que es justo lo que se quiere:
        que alguien se entere.
        """
        r = cliente.get(
            "/api/v1/catalog/retc-systems?familia=sma",
            headers={"X-Tenant-Id": TENANT_1},
        )
        assert r.json() == []

    def test_la_periodicidad_va_vacia_y_no_inventada(self, cliente) -> None:
        """**Un calendario inventado genera vencimientos falsos**, que en este
        dominio es el peor error posible: la empresa cree que declaró a tiempo.

        El portal lista los sistemas pero no sus plazos, y ADR-004 dice que las
        fechas cambian por resolución cada año.
        """
        r = cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_1}
        )
        assert all(s["periodicidad"] is None for s in r.json())


class TestDeclararReportabilidad:
    """#102. Que sistemas le aplican a una instalacion."""

    def _sistema(self, cliente) -> int:
        return cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_1}
        ).json()[0]["id"]

    def test_declarar_y_volver_a_leer(self, cliente, db, limpiar) -> None:
        planta = _instalacion(db, TENANT_1)
        if planta is None:  # pragma: no cover
            pytest.skip("El seed no tiene instalaciones.")
        limpiar.append(str(planta))
        sistema = self._sistema(cliente)

        r = cliente.put(
            f"/api/v1/facilities/{planta}/reportabilidad/{sistema}",
            headers={"X-Tenant-Id": TENANT_1},
            json={"estado": "si", "variables": {"genera_respel": True}},
        )
        assert r.status_code == 200, r.text

        listado = cliente.get(
            f"/api/v1/facilities/{planta}/reportabilidad",
            headers={"X-Tenant-Id": TENANT_1},
        ).json()
        assert [s["retc_system_id"] for s in listado] == [sistema]
        assert listado[0]["variables"] == {"genera_respel": True}

    def test_declarar_dos_veces_corrige_en_vez_de_duplicar(
        self, cliente, db, limpiar
    ) -> None:
        """**Por eso es `PUT` y no `POST`.**

        Dos filas para la misma pareja serian dos verdades sobre si hay que
        declarar, y la pantalla mostraria la que ordene primero. La unicidad lo
        impide en la base; el verbo hace que corregir sea lo natural.
        """
        planta = _instalacion(db, TENANT_1)
        if planta is None:  # pragma: no cover
            pytest.skip("El seed no tiene instalaciones.")
        limpiar.append(str(planta))
        sistema = self._sistema(cliente)
        h = {"X-Tenant-Id": TENANT_1}

        cliente.put(
            f"/api/v1/facilities/{planta}/reportabilidad/{sistema}",
            headers=h,
            json={"estado": "si"},
        )
        r = cliente.put(
            f"/api/v1/facilities/{planta}/reportabilidad/{sistema}",
            headers=h,
            json={"estado": "na"},
        )

        assert r.status_code == 200, r.text
        listado = cliente.get(
            f"/api/v1/facilities/{planta}/reportabilidad", headers=h
        ).json()
        assert len(listado) == 1
        assert listado[0]["estado"] == "na"

    def test_condicional_sin_decir_de_que_depende_se_rechaza(
        self, cliente, db, limpiar
    ) -> None:
        """**La negacion que sostiene todo el modelo.**

        `condicional` significa "aplica si se cumple algo". Sin decir qué, la
        decisión no se puede revisar un año después sin repetir la entrevista
        entera — que es el trabajo de días que este módulo existe para evitar.
        """
        planta = _instalacion(db, TENANT_1)
        if planta is None:  # pragma: no cover
            pytest.skip("El seed no tiene instalaciones.")
        limpiar.append(str(planta))
        sistema = self._sistema(cliente)

        r = cliente.put(
            f"/api/v1/facilities/{planta}/reportabilidad/{sistema}",
            headers={"X-Tenant-Id": TENANT_1},
            json={"estado": "condicional"},
        )

        assert r.status_code == 422
        assert "depende" in r.json()["detail"]

    def test_condicional_con_su_condicion_se_acepta(
        self, cliente, db, limpiar
    ) -> None:
        planta = _instalacion(db, TENANT_1)
        if planta is None:  # pragma: no cover
            pytest.skip("El seed no tiene instalaciones.")
        limpiar.append(str(planta))
        sistema = self._sistema(cliente)

        r = cliente.put(
            f"/api/v1/facilities/{planta}/reportabilidad/{sistema}",
            headers={"X-Tenant-Id": TENANT_1},
            json={
                "estado": "condicional",
                "condicion": "Solo si la bodega supera las 12 toneladas.",
            },
        )
        assert r.status_code == 200, r.text

    def test_un_estado_inventado_se_rechaza(self, cliente, db, limpiar) -> None:
        planta = _instalacion(db, TENANT_1)
        if planta is None:  # pragma: no cover
            pytest.skip("El seed no tiene instalaciones.")
        sistema = self._sistema(cliente)

        r = cliente.put(
            f"/api/v1/facilities/{planta}/reportabilidad/{sistema}",
            headers={"X-Tenant-Id": TENANT_1},
            json={"estado": "quizas"},
        )
        assert r.status_code == 422

    def test_un_sistema_que_no_existe_da_404(self, cliente, db) -> None:
        planta = _instalacion(db, TENANT_1)
        if planta is None:  # pragma: no cover
            pytest.skip("El seed no tiene instalaciones.")

        r = cliente.put(
            f"/api/v1/facilities/{planta}/reportabilidad/9999",
            headers={"X-Tenant-Id": TENANT_1},
            json={"estado": "si"},
        )
        assert r.status_code == 404


class TestNoSeCruzaEntreEmpresas:
    """Esta tabla dice donde declara cada planta de cada cliente.

    **Es informacion competitiva**, no solo dato interno: saber que una empresa
    declara en SIDREP dice que genera residuos peligrosos.
    """

    def test_la_reportabilidad_de_una_empresa_no_se_ve_desde_la_otra(
        self, cliente, db, limpiar
    ) -> None:
        planta_1 = _instalacion(db, TENANT_1)
        if planta_1 is None:  # pragma: no cover
            pytest.skip("El seed no tiene instalaciones.")
        limpiar.append(str(planta_1))
        sistema = cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_1}
        ).json()[0]["id"]

        cliente.put(
            f"/api/v1/facilities/{planta_1}/reportabilidad/{sistema}",
            headers={"X-Tenant-Id": TENANT_1},
            json={"estado": "si"},
        )

        # La segunda empresa pide la instalacion de la primera por su id.
        r = cliente.get(
            f"/api/v1/facilities/{planta_1}/reportabilidad",
            headers={"X-Tenant-Id": TENANT_2},
        )

        # 404 y no una lista vacia: la instalacion **no existe** para quien
        # pregunta. Devolver `[]` diria "existe y no tiene nada declarado", que
        # ya es informacion.
        assert r.status_code == 404, r.text

    def test_no_se_puede_declarar_sobre_la_planta_de_otra_empresa(
        self, cliente, db, limpiar
    ) -> None:
        """**La negacion que hay que sostener a mano.**

        Aparecio rompiendo el codigo a proposito: sin la comprobacion de la
        instalacion, la empresa 2 declara sobre la planta de la empresa 1 y la
        API responde **200**, creando una fila cruzada. Comprobado.

        RLS no lo impide, y el motivo esta documentado en este repo: **las FK de
        Postgres no pasan por Row Level Security**. `fk_facility_retc_facility`
        solo exige que la planta exista, no mira el tenant. La fila nace con el
        `tenant_id` de quien escribe y apuntando afuera.
        """
        planta_1 = _instalacion(db, TENANT_1)
        if planta_1 is None:  # pragma: no cover
            pytest.skip("El seed no tiene instalaciones.")
        limpiar.append(str(planta_1))
        sistema = cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_1}
        ).json()[0]["id"]

        r = cliente.put(
            f"/api/v1/facilities/{planta_1}/reportabilidad/{sistema}",
            headers={"X-Tenant-Id": TENANT_2},
            json={"estado": "si"},
        )

        assert r.status_code == 404, (
            f"Declaro sobre una planta ajena: {r.status_code} {r.text}"
        )

        # Y no quedo nada escrito, que es lo que de verdad importa.
        vistas = cliente.get(
            f"/api/v1/facilities/{planta_1}/reportabilidad",
            headers={"X-Tenant-Id": TENANT_1},
        ).json()
        assert vistas == []

    def test_el_catalogo_si_es_comun_a_las_dos(self, cliente) -> None:
        """Los portales del Estado **no** son dato de empresa.

        Copiarlos por empresa obligaria a aplicar cada resolucion del MMA una
        vez por cliente, y en la practica quedarian desincronizados.
        """
        de_una = cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_1}
        ).json()
        de_otra = cliente.get(
            "/api/v1/catalog/retc-systems", headers={"X-Tenant-Id": TENANT_2}
        ).json()

        assert [s["code"] for s in de_una] == [s["code"] for s in de_otra]
