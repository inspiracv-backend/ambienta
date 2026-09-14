"""Lo que el backend le debe al AI Service.

Fuente: *Informe de requerimientos Backend para integracion del AI Service*.

## Que vigila, y por que estos casos

| regla | lo que evita |
|---|---|
| `updated_since` compara con `>` | recibir siempre la ultima fila de la corrida anterior |
| el articulado por fecha respeta `valid_to IS NULL` | **cero articulos justo para la version vigente** |
| una fecha sin texto devuelve lista vacia | un 404 sobre una norma que existe |
| el checksum viaja con el enlace | validar el archivo contra el hash de otro texto |
| las cabeceras estan en el contrato | tener que adivinar si hay mas paginas |

El segundo es el filo del cambio: `valid_to` nulo significa **"todavia rige"**,
y escrito al reves la consulta deja fuera precisamente la version que mas se
consulta — sin error, con una lista vacia.
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

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.deps import declarar  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"


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


def _una_norma_publica(cliente) -> dict:
    normas = cliente.get("/api/v1/catalog/norms/?limit=1").json()
    if not normas:
        pytest.skip("el catalogo esta vacio")
    return normas[0]


class TestSincronizacionIncremental:
    def test_sin_el_parametro_responde_como_siempre(self, cliente) -> None:
        """Compatibilidad: es el primer criterio de aceptacion del informe."""
        r = cliente.get("/api/v1/catalog/norms/?limit=5")
        assert r.status_code == 200, r.text
        assert len(r.json()) > 0

    def test_una_fecha_futura_no_devuelve_nada(self, cliente) -> None:
        futuro = (date.today() + timedelta(days=3650)).isoformat() + "T00:00:00Z"
        r = cliente.get("/api/v1/catalog/norms/", params={"updated_since": futuro})
        assert r.status_code == 200, r.text
        assert r.json() == []

    def test_una_fecha_antigua_las_devuelve_todas(self, cliente) -> None:
        r = cliente.get(
            "/api/v1/catalog/norms/",
            params={"updated_since": "2000-01-01T00:00:00Z", "limit": 200},
        )
        assert r.status_code == 200, r.text
        # Contra lo que hay en la base, no contra un numero: con el catalogo del
        # seed son 8 y con la BCN sincronizada 24, y la regla es la misma.
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            publicas = db.execute(
                text("SELECT count(*) FROM legal_norms WHERE tenant_id IS NULL AND deleted_at IS NULL")
            ).scalar()
        assert len(r.json()) == min(publicas, 200)

    def test_el_corte_es_estricto(self, cliente) -> None:
        """`>` y no `>=`, que es lo que hace util el corte.

        Quien indexa guarda el `updated_at` maximo que vio y lo manda como
        corte. Con `>=` esa misma fila vuelve **en cada corrida**, para
        siempre.
        """
        normas = cliente.get("/api/v1/catalog/norms/?limit=200").json()
        assert normas, "el catalogo esta vacio"
        corte = max(n["updated_at"] for n in normas)

        devueltas = cliente.get(
            "/api/v1/catalog/norms/", params={"updated_since": corte, "limit": 200}
        ).json()
        assert devueltas == [], (
            "pidiendo desde el `updated_at` mas alto volvio a devolver filas: "
            "el corte esta comparando con >= y quien indexe recibira esas filas "
            "en cada corrida"
        )

    def test_convive_con_la_paginacion(self, cliente) -> None:
        r = cliente.get(
            "/api/v1/catalog/norms/",
            params={"updated_since": "2000-01-01T00:00:00Z", "limit": 2, "skip": 0},
        )
        assert r.status_code == 200
        assert len(r.json()) <= 2
        assert r.headers.get("X-Has-More") in {"true", "false"}

    def test_updated_at_sigue_viniendo(self, cliente) -> None:
        """Es de donde sale el proximo corte. Sin el, el cliente tendria que
        usar su reloj — y uno adelantado se saltaria filas en silencio."""
        assert "updated_at" in _una_norma_publica(cliente)

    def test_los_documentos_tambien(self, cliente) -> None:
        futuro = (date.today() + timedelta(days=3650)).isoformat() + "T00:00:00Z"
        r = cliente.get("/api/v1/documents/", params={"updated_since": futuro})
        assert r.status_code == 200, r.text
        assert r.json() == []


class TestVersionesDeUnaNorma:
    def test_se_listan_con_su_vigencia(self, cliente) -> None:
        # Una norma **que tenga versiones**: las del seed no las tienen, las de
        # la BCN si. Tomar la primera del listado medía el seed, no el endpoint.
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            norma_id = db.execute(
                text(
                    "SELECT n.id FROM legal_norms n JOIN legal_norm_versions v ON v.norm_id = n.id "
                    "WHERE n.tenant_id IS NULL AND n.deleted_at IS NULL LIMIT 1"
                )
            ).scalar()
        if norma_id is None:
            pytest.skip("ninguna norma publica tiene versiones (base sin sincronizar con la BCN)")
        r = cliente.get(f"/api/v1/catalog/norms/{norma_id}/versions")
        assert r.status_code == 200, r.text
        versiones = r.json()
        assert versiones, "la norma no tiene ninguna version"

        v = versiones[0]
        for campo in ("id", "valid_from", "valid_to", "is_current", "content_hash"):
            assert campo in v, f"falta {campo}, que el informe pide"

    def test_la_vigente_se_identifica_sin_ambiguedad(self, cliente) -> None:
        norma = _una_norma_publica(cliente)
        versiones = cliente.get(f"/api/v1/catalog/norms/{norma['id']}/versions").json()
        vigentes = [v for v in versiones if v["is_current"]]
        assert len(vigentes) <= 1, (
            f"{len(vigentes)} versiones marcadas vigentes a la vez. La BCN hace "
            "eso —ya se midio en la Ley 19.300— y el consumidor no puede "
            "resolverlo solo."
        )

    def test_una_norma_que_no_existe_es_404(self, cliente) -> None:
        r = cliente.get(f"/api/v1/catalog/norms/{uuid.uuid4()}/versions")
        assert r.status_code == 404


class TestArticuladoPorFecha:
    def test_sin_el_parametro_devuelve_el_vigente(self, cliente) -> None:
        norma = _una_norma_publica(cliente)
        r = cliente.get(f"/api/v1/catalog/norms/{norma['id']}/articles")
        assert r.status_code == 200, r.text

    def test_hoy_devuelve_lo_mismo_que_sin_parametro(self, cliente) -> None:
        """**El filo del cambio.**

        `valid_to` nulo significa "todavia rige". Escrita al reves, la
        condicion de vigencia deja fuera justo la version actual y devuelve
        **cero articulos** — sin error, con una lista vacia que se lee como
        "esta norma no tiene articulado".
        """
        norma = _una_norma_publica(cliente)
        sin_fecha = cliente.get(f"/api/v1/catalog/norms/{norma['id']}/articles").json()
        if not sin_fecha:
            pytest.skip("esa norma no tiene articulado vigente")

        con_hoy = cliente.get(
            f"/api/v1/catalog/norms/{norma['id']}/articles",
            params={"vigente_el": date.today().isoformat()},
        ).json()

        assert [a["id"] for a in con_hoy] == [a["id"] for a in sin_fecha], (
            "pedir el articulado de hoy no devuelve lo mismo que pedirlo sin "
            "fecha. Casi seguro `valid_to IS NULL` quedo tratado como 'ya no "
            "rige' en vez de 'todavia rige'."
        )

    def test_una_fecha_sin_texto_devuelve_lista_vacia_no_404(self, cliente) -> None:
        """La norma existe; lo que no hay es texto para esa fecha."""
        norma = _una_norma_publica(cliente)
        r = cliente.get(
            f"/api/v1/catalog/norms/{norma['id']}/articles",
            params={"vigente_el": "1900-01-01"},
        )
        assert r.status_code == 200, r.text
        assert r.json() == []

    def test_una_fecha_pasada_puede_dar_otro_texto(self, cliente) -> None:
        """Con dos versiones, cada fecha trae la suya.

        Se monta la version anterior a mano porque el catalogo real puede tener
        una sola: sin esto la prueba pasaria sin comparar nada.
        """
        norma = _una_norma_publica(cliente)
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            vigente = db.execute(
                text(
                    "SELECT id, valid_from FROM legal_norm_versions "
                    "WHERE norm_id = :n AND is_current AND deleted_at IS NULL"
                ),
                {"n": norma["id"]},
            ).first()
            if vigente is None:
                pytest.skip("esa norma no tiene version vigente")
            _, desde = vigente
            anterior = uuid.uuid4()
            # Catalogo publico: se escribe sin tenant declarado (db/29).
            db.execute(text("SELECT set_config('ambienta.tenant_id','',true)"))
            db.execute(
                text(
                    "INSERT INTO legal_norm_versions "
                    "(id, norm_id, valid_from, valid_to, is_current, content_hash) "
                    "VALUES (:i, :n, :d, :h, false, :c)"
                ),
                {
                    "i": anterior,
                    "n": norma["id"],
                    "d": desde - timedelta(days=730),
                    "h": desde - timedelta(days=1),
                    "c": uuid.uuid4().hex * 2,
                },
            )
            db.execute(
                text(
                    "INSERT INTO legal_articles "
                    "(norm_version_id, article_number, content, display_order) "
                    "VALUES (:v, 'ANT-1', 'Texto anterior', 1)"
                ),
                {"v": anterior},
            )
            db.commit()

        try:
            en_el_pasado = cliente.get(
                f"/api/v1/catalog/norms/{norma['id']}/articles",
                params={"vigente_el": (desde - timedelta(days=30)).isoformat()},
            ).json()
            assert [a["article_number"] for a in en_el_pasado] == ["ANT-1"], (
                "el articulado de una fecha pasada no es el de la version que "
                f"regia entonces: {en_el_pasado}"
            )
        finally:
            with SessionLocal() as db:
                declarar(db, EMPRESA_A)
                db.execute(text("SELECT set_config('ambienta.tenant_id','',true)"))
                db.execute(
                    text("DELETE FROM legal_norm_versions WHERE id = :i"),
                    {"i": anterior},
                )
                db.commit()


class TestElContratoDiceComoSeUsa:
    def test_las_cabeceras_de_pagina_estan_declaradas(self) -> None:
        """Se emiten desde siempre y no estaban en el contrato: un cliente
        generado desde OpenAPI no sabia como saber si hay mas paginas."""
        esquema = app.openapi()
        cabeceras = esquema["paths"]["/api/v1/catalog/norms"]["get"]["responses"][
            "200"
        ].get("headers", {})
        assert "X-Has-More" in cabeceras
        assert "X-Page-Limit" in cabeceras

    def test_se_declaran_en_todas_las_paginadas(self) -> None:
        """Derivadas, no escritas una por una: son ~30 rutas y olvidarse de
        alguna no falla, solo deja el contrato mintiendo en esa."""
        esquema = app.openapi()
        sin_declarar = []
        for ruta, metodos in esquema["paths"].items():
            for metodo, op in metodos.items():
                if not isinstance(op, dict):
                    continue
                nombres = {p.get("name") for p in op.get("parameters", [])}
                if not {"skip", "limit"} <= nombres:
                    continue
                cab = op.get("responses", {}).get("200", {}).get("headers", {})
                if "X-Has-More" not in cab:
                    sin_declarar.append(f"{metodo.upper()} {ruta}")
        assert not sin_declarar, sin_declarar

    def test_x_tenant_id_se_describe_como_respaldo_de_desarrollo(self) -> None:
        """Aparecia como un header opcional mas, y con Clerk **se ignora**."""
        import json

        texto = json.dumps(app.openapi())
        assert "Respaldo de desarrollo" in texto
        assert "se ignora por completo" in texto


class TestDescargaVerificable:
    def test_el_enlace_declara_el_checksum(self) -> None:
        """Lo unico que le faltaba al endpoint que ya existia.

        Se comprueba sobre el contrato y no pidiendo un enlace: emitirlo exige
        credenciales de Backblaze, que en las pruebas no estan — y esa
        dependencia ya tiene sus propias pruebas, marcadas para saltarse.
        """
        esquema = app.openapi()
        enlace = esquema["components"]["schemas"]["EnlaceDeDescarga"]["properties"]
        assert "checksum_sha256" in enlace, (
            "el enlace de descarga no trae la huella, asi que quien descargue "
            "no puede verificar el archivo sin una segunda llamada — y entre "
            "las dos la revision puede cambiar"
        )
        assert "url" in enlace and "expires_in" in enlace
