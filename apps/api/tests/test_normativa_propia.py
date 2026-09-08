"""La normativa propia de cada empresa: su RCA y sus ISO (RF-10, RF-11).

## Que vigila

`db/29` activa RLS sobre **tres tablas que no la tenian** —el catalogo
normativo— y eso puede romper cosas que hoy funcionan sin que nadie lo note.
Las cuatro reglas:

| regla | lo que evita |
|---|---|
| la empresa B no ve la RCA de la A, **ni sus articulos** | mostrarle a una minera el permiso de otra |
| el catalogo publico se sigue viendo igual | 24 normas que desaparecen de todas las matrices |
| nadie puede escribir una norma sin dueno | que una empresa le escriba la ley a las demas |
| **la sincronizacion de la BCN sigue trayendo** | un catalogo que deja de actualizarse en silencio |

La ultima es la que justifica el `NO FORCE` de la migracion, y es la que
alguien romperia "por simetria" con las demas tablas.
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

from app.db import AdminSessionLocal, SessionLocal  # noqa: E402
from app.deps import declarar  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"


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


@pytest.fixture
def rca(cliente):
    """Una RCA de la empresa A, con un considerando."""
    cliente.headers["X-Tenant-Id"] = EMPRESA_A
    r = cliente.post(
        "/api/v1/compliance/normativa-propia/",
        json={
            "fuente": "RCA",
            "norm_type": "resolucion",
            "title": f"RCA Proyecto de prueba {uuid.uuid4().hex[:6]}",
            "norm_number": "RCA-123/2019",
            "issuing_body": "Comision de Evaluacion Ambiental",
            "articulos": [
                {
                    "article_number": "5.2",
                    "heading": "Caudal maximo de captacion",
                    "content": "El titular no podra captar mas de 30 l/s del estero.",
                }
            ],
        },
    )
    assert r.status_code == 201, r.text
    creada = r.json()
    yield creada
    # **Se limpia con el tenant DECLARADO, y eso no es un detalle.** La primera
    # version borraba con `AdminSessionLocal`, suponiendo que se salta RLS —y
    # sin `DATABASE_ADMIN_URL` esa sesion es `ambienta_app` **sin tenant**, que
    # por la politica de `db/29` no ve las filas propias—. O sea que el DELETE
    # no borraba nada y **no fallaba**: quedaron 24 RCAs de prueba en el
    # catalogo, y otras pruebas empezaron a elegirlas como si fueran normas
    # publicas. El borrado en cascada de versiones y articulos lo hace la FK.
    with SessionLocal() as db:
        declarar(db, EMPRESA_A)
        db.execute(text("DELETE FROM legal_norms WHERE id = :i"), {"i": creada["id"]})
        db.commit()


class TestLoQueNoSeComparte:
    def test_la_empresa_B_no_ve_la_RCA_de_la_A(self, cliente, rca) -> None:
        """Las condiciones de una RCA describen la operacion de la planta."""
        cliente.headers["X-Tenant-Id"] = EMPRESA_B
        try:
            propias = cliente.get("/api/v1/compliance/normativa-propia/").json()
            assert rca["id"] not in [n["id"] for n in propias], (
                "la empresa B ve la RCA de la A en su listado"
            )

            # Y tampoco por el catalogo, que es la otra puerta.
            catalogo = cliente.get("/api/v1/catalog/norms/?limit=200").json()
            assert rca["id"] not in [n["id"] for n in catalogo], (
                "la RCA de la empresa A aparece en el catalogo publico"
            )
        finally:
            cliente.headers["X-Tenant-Id"] = EMPRESA_A

    def test_la_empresa_B_tampoco_ve_sus_articulos(self, cliente, rca) -> None:
        """**Es lo que mas importa.** Una RCA sin sus considerandos es un
        titulo; los compromisos —caudales, horarios, monitoreos— estan en los
        articulos. Proteger la norma y dejar la tabla hija abierta seria poner
        la puerta y olvidar la pared."""
        with SessionLocal() as db:
            declarar(db, EMPRESA_B)
            visibles = db.execute(
                text(
                    "SELECT count(*) FROM legal_articles a "
                    "JOIN legal_norm_versions v ON v.id = a.norm_version_id "
                    "WHERE v.norm_id = :n"
                ),
                {"n": rca["id"]},
            ).scalar()
        assert visibles == 0, (
            f"la empresa B ve {visibles} articulos de la RCA de la A — ahi estan "
            "los compromisos de la planta"
        )

    def test_la_empresa_A_si_los_ve(self, cliente, rca) -> None:
        """La contraparte: sin esto, la prueba de arriba pasaria con la tabla
        vacia y no probaria nada."""
        assert rca["articulos"] == 1
        propias = cliente.get("/api/v1/compliance/normativa-propia/").json()
        mia = next((n for n in propias if n["id"] == rca["id"]), None)
        assert mia is not None and mia["articulos"] == 1


class TestElCatalogoPublicoSigueIgual:
    def test_las_normas_publicas_se_siguen_viendo(self, cliente) -> None:
        """Activar RLS sobre el catalogo **no debe** quitarle normas a nadie.

        Si esta prueba se pone en rojo, las matrices legales de todas las
        empresas se quedaron sin normativa — y el sintoma seria "el sistema no
        tiene normas", que no se parece a "se activo RLS".
        """
        normas = cliente.get("/api/v1/catalog/norms/?limit=200").json()
        assert len(normas) >= 20, (
            f"solo {len(normas)} normas publicas visibles. El catalogo tenia 24 "
            "el dia que se activo RLS."
        )
        assert all(n.get("tenant_id") is None for n in normas if "tenant_id" in n)

    def test_los_articulos_publicos_tambien(self, cliente) -> None:
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            n = db.execute(
                text("SELECT count(*) FROM legal_articles WHERE tenant_id IS NULL")
            ).scalar()
        assert n and n > 600, f"solo {n} articulos publicos; eran 689"


class TestNadieEscribeLaLeyAjena:
    def test_no_se_puede_registrar_una_norma_sin_dueno(self) -> None:
        """El `WITH CHECK` de la politica.

        Si el `USING` y el `WITH CHECK` dijeran lo mismo, cualquier empresa
        podria insertar una norma con `tenant_id` nulo y quedaria en el
        catalogo de todas.
        """
        from sqlalchemy.exc import ProgrammingError

        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            with pytest.raises(ProgrammingError):
                db.execute(
                    text(
                        "INSERT INTO legal_norms "
                        "(tenant_id, country_id, source_id, norm_type, title, status) "
                        "VALUES (NULL, 1, 3, 'resolucion', 'Ley inventada', 'vigente')"
                    )
                )
                db.flush()
            db.rollback()

    def test_tampoco_una_norma_de_otra_empresa(self) -> None:
        from sqlalchemy.exc import ProgrammingError

        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            with pytest.raises(ProgrammingError):
                db.execute(
                    text(
                        "INSERT INTO legal_norms "
                        "(tenant_id, country_id, source_id, norm_type, title, status) "
                        "VALUES (:b, 1, 3, 'resolucion', 'De la otra', 'vigente')"
                    ),
                    {"b": EMPRESA_B},
                )
                db.flush()
            db.rollback()

    def test_la_fuente_de_la_BCN_no_se_admite(self, cliente) -> None:
        """Una fila escrita a mano bajo `BCN_LEYCHILE` se confundiria con una
        importada — y la proxima sincronizacion podria adoptarla o duplicarla."""
        r = cliente.post(
            "/api/v1/compliance/normativa-propia/",
            json={"fuente": "BCN_LEYCHILE", "norm_type": "ley", "title": "Inventada"},
        )
        assert r.status_code == 422, r.text


class TestLaSincronizacionSigueFuncionando:
    """La prueba que justifica el `NO FORCE` de `db/29`.

    Con `FORCE ROW LEVEL SECURITY` el **dueno** de la tabla tambien queda
    sujeto a la politica, y la sincronizacion de la BCN escribe con
    `AdminSessionLocal` **sin tenant declarado**: su `INSERT` de una norma
    global no pasaria el `WITH CHECK`, porque `current_tenant_id()` es NULL.

    Sin esto, agregar `FORCE` por simetria con las demas migraciones dejaria el
    catalogo sin actualizarse y el sintoma seria "la BCN no trae nada".
    """

    def test_las_tres_tablas_estan_sin_FORCE(self) -> None:
        with AdminSessionLocal() as db:
            filas = db.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname IN "
                    "('legal_norms','legal_norm_versions','legal_articles')"
                )
            ).all()
        assert len(filas) == 3
        for nombre, rls, force in filas:
            assert rls is True, f"{nombre} quedo sin RLS"
            assert force is False, (
                f"{nombre} tiene FORCE ROW LEVEL SECURITY. Eso rompe la "
                "sincronizacion de la BCN, que escribe con el superusuario y "
                "sin tenant declarado. Ver db/29_normativa_propia.sql."
            )

    def test_la_sesion_de_administracion_escribe_una_norma_global(self) -> None:
        """El camino real de la sincronizacion, ejecutado.

        No se llama a `bcn.sincronizar()` porque sale a internet; lo que se
        prueba es **la escritura**, que es lo que la migracion pudo haber roto.
        """
        marca = f"PRUEBA-RLS-{uuid.uuid4().hex[:8]}"
        with AdminSessionLocal() as db:
            db.execute(
                text(
                    "INSERT INTO legal_norms "
                    "(tenant_id, country_id, source_id, norm_type, norm_number, title, status) "
                    "VALUES (NULL, 1, 1, 'ley', :m, 'Norma global de prueba', 'vigente')"
                ),
                {"m": marca},
            )
            db.commit()
            try:
                visible = db.execute(
                    text("SELECT tenant_id FROM legal_norms WHERE norm_number = :m"),
                    {"m": marca},
                ).scalar_one()
                assert visible is None, "la norma global quedo con dueno"
            finally:
                db.execute(
                    text("DELETE FROM legal_norms WHERE norm_number = :m"), {"m": marca}
                )
                db.commit()


class TestElArticuladoPublicoNoSeEdita:
    def test_no_se_le_agrega_un_considerando_a_una_norma_publica(
        self, cliente
    ) -> None:
        """Editarlo a mano dejaria la matriz de una empresa evaluando un texto
        que no es el de la ley."""
        publica = cliente.get("/api/v1/catalog/norms/?limit=1").json()
        if not publica:
            pytest.skip("el catalogo esta vacio")

        r = cliente.post(
            f"/api/v1/compliance/normativa-propia/{publica[0]['id']}/articulos",
            json={"article_number": "99", "content": "Inventado"},
        )
        assert r.status_code == 422, r.text
