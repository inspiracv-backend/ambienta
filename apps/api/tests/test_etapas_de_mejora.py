"""Las cinco etapas del registro de mejora, tipadas (RF-97, RF-98, #38, #43).

## Que reemplaza

`nonconformities.improvement_stages` era JSONB provisorio desde el principio, y
su propio comentario en `01_schema.sql` lo decia. La decision #57 se tomo el
10-sep-2026: **tabla**. El motivo no es purismo — con JSONB el responsable de
cada etapa es un texto sin clave foranea, y el generador de avisos tendria que
leer dentro del JSON para saber a quien escribirle. Este repositorio ya se quemo
con eso: el generador de vencimientos **se saltaba en silencio las obligaciones
sin responsable**, 3 de 8 en el seed.

**No migro datos, y se midio:** las 293 no conformidades tenian
`improvement_stages = '{}'`, 292 de ellas borradas logicamente.

## Lo que estas pruebas fijan

La regla que justifica el modulo: **el cierre exige `eficaz is True`, no un
valor truthy**. Los cinco campos del seguimiento son `Seleccione… / SI / NO` en
el sistema del cliente, y como booleano "todavia no lo verifique" se vuelve
"No" — que en tres de las cuatro preguntas es la respuesta **favorable**. El
defecto silencioso cerraria la verificacion a favor, justo donde la norma pide
rigor.

Por eso hay tres pruebas y no una: sin verificar, verificado que no, y
verificado que si son **tres estados distintos** con tres arreglos distintos.
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
        c.headers["X-Tenant-Id"] = EMPRESA_A
        yield c


def _borrar(nc_id: str, empresa: str = EMPRESA_A) -> None:
    with SessionLocal() as db:
        declarar(db, empresa)
        db.execute(
            text("DELETE FROM improvement_stage_entries WHERE nonconformity_id = :n"),
            {"n": nc_id},
        )
        db.execute(text("DELETE FROM nonconformities WHERE id = :n"), {"n": nc_id})
        db.commit()


@pytest.fixture
def registro(cliente):
    """Una no conformidad de la empresa A. El prefijo `PRB-` no es decoracion:
    un hallazgo inventado sin marcar, en un modulo que lee un certificador, se
    lee como un hallazgo de la empresa."""
    cliente.headers["X-Tenant-Id"] = EMPRESA_A
    r = cliente.post(
        BASE + "/",
        json={
            "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
            "title": "[QA] Registro para medir el ciclo",
            "description": "Creado por las pruebas de etapas.",
            "severity": "major",
        },
    )
    assert r.status_code == 201, r.text
    nc = r.json()["id"]
    yield nc
    _borrar(nc)


def _completar_todas(cliente, nc: str) -> None:
    for etapa in cliente.get(f"{BASE}/{nc}/etapas").json():
        cliente.patch(
            f"{BASE}/{nc}/etapas/{etapa['id']}",
            json={"fecha_ejecucion": "2026-09-12"},
        )


class TestElCicloSeSiembra:
    def test_las_cinco_en_el_orden_de_la_norma(self, cliente, registro) -> None:
        """Primero reaccionar, despues analizar — ISO 9001 §10.2.1."""
        r = cliente.post(f"{BASE}/{registro}/etapas")
        assert r.status_code == 201, r.text
        assert [e["kind"] for e in r.json()] == [
            "registro",
            "correccion",
            "analisis_causa",
            "accion_correctiva",
            "seguimiento",
        ]

    def test_sembrar_dos_veces_no_duplica(self, cliente, registro) -> None:
        """Tambien sirve para reparar un registro que quedo a medias."""
        cliente.post(f"{BASE}/{registro}/etapas")
        cliente.post(f"{BASE}/{registro}/etapas")
        assert len(cliente.get(f"{BASE}/{registro}/etapas").json()) == 5

    def test_se_leen_en_el_orden_del_ciclo_y_no_por_fecha(
        self, cliente, registro
    ) -> None:
        """Ordenar por `created_at` mostraria el orden en que alguien completo
        los formularios, que no es el orden del proceso."""
        cliente.post(f"{BASE}/{registro}/etapas")
        etapas = cliente.get(f"{BASE}/{registro}/etapas").json()
        # Se completa la ultima primero: el orden de lectura no debe cambiar.
        cliente.patch(
            f"{BASE}/{registro}/etapas/{etapas[-1]['id']}",
            json={"fecha_ejecucion": "2026-09-01"},
        )
        assert [e["kind"] for e in cliente.get(f"{BASE}/{registro}/etapas").json()][
            0
        ] == "registro"


class TestElCierreExigeEficaciaAfirmativa:
    """**Los tres estados del seguimiento, que no son dos.**"""

    def test_con_etapas_sin_completar_no_se_cierra(self, cliente, registro) -> None:
        cliente.post(f"{BASE}/{registro}/etapas")
        r = cliente.get(f"{BASE}/{registro}/puede-cerrarse").json()
        assert r["puede"] is False
        assert "sin completar" in r["motivo"]

    def test_sin_verificar_NO_es_no_fue_eficaz(self, cliente, registro) -> None:
        """El caso que motiva el tri-estado.

        Con `eficaz` como booleano, "todavia no lo verifique" seria `False` — y
        el mensaje diria que la accion no funciono, que es otra cosa y se
        arregla distinto.
        """
        cliente.post(f"{BASE}/{registro}/etapas")
        _completar_todas(cliente, registro)

        r = cliente.get(f"{BASE}/{registro}/puede-cerrarse").json()
        assert r["puede"] is False
        assert "no dice si la accion fue eficaz" in r["motivo"], (
            f"el motivo confunde sin verificar con no eficaz: {r['motivo']}"
        )

    def test_eficaz_false_devuelve_a_tratamiento(self, cliente, registro) -> None:
        cliente.post(f"{BASE}/{registro}/etapas")
        _completar_todas(cliente, registro)
        seguimiento = next(
            e
            for e in cliente.get(f"{BASE}/{registro}/etapas").json()
            if e["kind"] == "seguimiento"
        )
        cliente.patch(
            f"{BASE}/{registro}/etapas/{seguimiento['id']}", json={"eficaz": False}
        )

        r = cliente.get(f"{BASE}/{registro}/puede-cerrarse").json()
        assert r["puede"] is False
        assert "NO fue eficaz" in r["motivo"]

    def test_eficaz_true_cierra(self, cliente, registro) -> None:
        cliente.post(f"{BASE}/{registro}/etapas")
        _completar_todas(cliente, registro)
        seguimiento = next(
            e
            for e in cliente.get(f"{BASE}/{registro}/etapas").json()
            if e["kind"] == "seguimiento"
        )
        cliente.patch(
            f"{BASE}/{registro}/etapas/{seguimiento['id']}", json={"eficaz": True}
        )

        r = cliente.get(f"{BASE}/{registro}/puede-cerrarse").json()
        assert r["puede"] is True, r["motivo"]
        assert r["motivo"] is None


class TestLaBaseSostieneLasReglas:
    def test_una_correccion_no_puede_decir_que_fue_eficaz(
        self, cliente, registro
    ) -> None:
        """El CHECK, no el codigo. Una guarda que solo vive en Python se salta
        con un `UPDATE` a mano, y esa columna se exporta a un certificador."""
        cliente.post(f"{BASE}/{registro}/etapas")
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            with pytest.raises(Exception):
                db.execute(
                    text(
                        "UPDATE improvement_stage_entries SET eficaz = true "
                        "WHERE nonconformity_id = :n AND kind = 'correccion'"
                    ),
                    {"n": registro},
                )
                db.commit()
            db.rollback()

    def test_completada_exige_fecha(self, cliente, registro) -> None:
        """Una etapa cerrada sin fecha no se puede ubicar en el tiempo, y el
        informe de auditoria ordena por eso."""
        cliente.post(f"{BASE}/{registro}/etapas")
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            with pytest.raises(Exception):
                db.execute(
                    text(
                        "UPDATE improvement_stage_entries SET completada_en = now() "
                        "WHERE nonconformity_id = :n AND kind = 'registro'"
                    ),
                    {"n": registro},
                )
                db.commit()
            db.rollback()

    def test_la_tabla_no_se_ve_entre_empresas(self, cliente, registro) -> None:
        """Una tabla nacida en una migracion **no hereda** la politica de RLS ni
        los GRANT: `db/30` los declara por su cuenta, y esto lo comprueba."""
        cliente.post(f"{BASE}/{registro}/etapas")
        try:
            cliente.headers["X-Tenant-Id"] = EMPRESA_B
            assert cliente.get(f"{BASE}/{registro}/etapas").status_code == 404
        finally:
            cliente.headers["X-Tenant-Id"] = EMPRESA_A


class TestLoQueNoRecorreLasCinco:
    def test_un_riesgo_salta_correccion_y_analisis(self, cliente) -> None:
        """No hay "correccion inmediata" de una oportunidad, ni causa raiz que
        analizar. Hacerlos pasar por las cinco con los campos vacios seria peor
        dato: un registro que dice "corregido: (nada)" afirma algo falso.
        """
        r = cliente.post(
            BASE + "/",
            json={
                "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
                "title": "[QA] Riesgo para medir el ciclo reducido",
                "description": "Creado por las pruebas de etapas.",
                "severity": "minor",
                "record_type": "riesgo",
            },
        )
        assert r.status_code == 201, r.text
        nc = r.json()["id"]
        try:
            etapas = cliente.post(f"{BASE}/{nc}/etapas").json()
            assert [e["kind"] for e in etapas] == [
                "registro",
                "accion_correctiva",
                "seguimiento",
            ]
        finally:
            _borrar(nc)


class TestElPlazoSaleDelCatalogo:
    def test_sin_plazo_declarado_la_fecha_queda_vacia(
        self, cliente, registro
    ) -> None:
        """**`None` no es cero.** El catalogo de severidades nace con
        `days_to_close` en NULL a proposito: sembrar 60/30/15 seria inventarle
        el compromiso a la empresa, y un plazo falso produce una fecha limite
        que nadie acordo — la empresa cree que va a tiempo.
        """
        etapas = cliente.post(f"{BASE}/{registro}/etapas").json()
        assert all(e["due_date"] is None for e in etapas)

    def test_con_plazo_declarado_se_calcula(self, cliente) -> None:
        """Y esto es lo que hace que el catalogo no sea decorativo.

        **El plazo se declara ANTES de crear el registro**, y la primera version
        de esta prueba lo hacia al reves: fallaba porque el ciclo se siembra al
        crear la no conformidad, no al pedir las etapas.

        Eso mismo es el comportamiento que hay que saber: **la fecha limite se
        fija cuando nace el registro y no se recalcula despues**. Cambiar el
        catalogo no le mueve el plazo a lo que ya estaba en tratamiento — el
        compromiso es el que regia cuando se detecto el hallazgo, igual que
        `due_date` de la propia no conformidad.
        """
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            previo = db.execute(
                text(
                    "SELECT days_to_close FROM improvement_severities "
                    "WHERE tenant_id = :t AND code = 'major' AND deleted_at IS NULL"
                ),
                {"t": EMPRESA_A},
            ).scalar()
            db.execute(
                text(
                    "UPDATE improvement_severities SET days_to_close = 30 "
                    "WHERE tenant_id = :t AND code = 'major' AND deleted_at IS NULL"
                ),
                {"t": EMPRESA_A},
            )
            db.commit()

        nc = None
        try:
            r = cliente.post(
                BASE + "/",
                json={
                    "code": f"PRB-{uuid.uuid4().hex[:8].upper()}",
                    "title": "[QA] Registro con plazo declarado",
                    "description": "Creado por las pruebas de etapas.",
                    "severity": "major",
                },
            )
            assert r.status_code == 201, r.text
            nc = r.json()["id"]
            etapas = cliente.get(f"{BASE}/{nc}/etapas").json()
            assert etapas, "el ciclo no se sembro al crear el registro"
            assert all(e["due_date"] is not None for e in etapas), (
                "la empresa declaro el plazo y la fecha limite siguio vacia: "
                "`days_to_close` volvio a ser decorativo"
            )
        finally:
            if nc:
                _borrar(nc)
            with SessionLocal() as db:
                declarar(db, EMPRESA_A)
                db.execute(
                    text(
                        "UPDATE improvement_severities SET days_to_close = :d "
                        "WHERE tenant_id = :t AND code = 'major' AND deleted_at IS NULL"
                    ),
                    {"d": previo, "t": EMPRESA_A},
                )
                db.commit()
