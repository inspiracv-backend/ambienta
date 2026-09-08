"""Un documento y lo que respalda (RF-108, #73).

## Que vigila esto

`entity_documents` no tiene clave foranea y no puede tenerla: `entity_id`
apunta a trece tablas distintas segun `entity_type`. O sea que **la unica
comprobacion posible es la de la aplicacion**, y hasta el 7-sep-2026 no
existia. Medido con una sonda contra la base real, desde la empresa A:

| lo que se mandaba | respuesta |
|---|---|
| un `entity_id` inventado | **201, y la fila quedaba escrita** |
| una obligacion **real de la empresa B** | **201, y la fila quedaba escrita** |

Lo grave no es una fuga de lectura —la fila nace en el tenant de quien la
escribe— sino que deja escrito que un documento respalda algo que en esta
empresa no existe. En un sistema de cumplimiento, un respaldo inventado es
justo el dato que se discute ante un fiscalizador.

Las pruebas van **por el camino HTTP real** y no llamando al handler: es lo
unico que pasa por `app/errores.py`, y sin eso un 422 se confunde con un fallo
del servidor.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.vinculos_de_documentos import ANCLAJES  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"

MIGRACION = Path(__file__).resolve().parents[3] / "db" / "27_vinculos_de_documentos.sql"


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
def documento(cliente):
    """Un documento de la empresa A, retirado al terminar."""
    r = cliente.post(
        "/api/v1/documents/",
        json={"document_type": "procedimiento", "title": "Documento de prueba"},
    )
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    yield did
    cliente.headers["X-Tenant-Id"] = EMPRESA_A
    # **Los vinculos primero.** Borrar el documento es logico y no se lleva sus
    # `entity_documents`, asi que cada corrida dejaba filas apuntando a normas y
    # procesos del seed. Se descubrio construyendo la linea de tiempo (#75): una
    # prueba que necesitaba un registro sin historia encontro 16 adjuntos
    # inventados colgando de una norma del catalogo.
    for v in cliente.get(f"/api/v1/documents/{did}/entities").json():
        cliente.delete(f"/api/v1/documents/{did}/entities/{v['id']}")
    cliente.delete(f"/api/v1/documents/{did}")


def _obligacion(cliente, empresa: str) -> str:
    anterior = cliente.headers.get("X-Tenant-Id")
    cliente.headers["X-Tenant-Id"] = empresa
    r = cliente.post(
        "/api/v1/obligations/",
        json={"code": f"VIN-{uuid.uuid4().hex[:8].upper()}", "title": "Para vincular"},
    )
    assert r.status_code == 201, r.text
    cliente.headers["X-Tenant-Id"] = anterior
    return r.json()["id"]


class TestLoQueNoSePuedeVincular:
    def test_las_dos_negativas_son_identicas(self, cliente, documento) -> None:
        """Un id inventado y uno real de otra empresa responden **lo mismo**.

        Distinguirlos convertiria el endpoint en un oraculo: mandando
        identificadores al azar se averiguaria cuales corresponden a registros
        reales de otras empresas sin verlos nunca. Es la misma decision que
        `validar_visible` y que el 403 del gestor.
        """
        ajena = _obligacion(cliente, EMPRESA_B)
        try:
            respuestas = []
            for entity_id in (str(uuid.uuid4()), ajena):
                r = cliente.post(
                    f"/api/v1/documents/{documento}/entities",
                    json={
                        "entity_type": "obligation",
                        "entity_id": entity_id,
                        "purpose": "evidence",
                    },
                )
                respuestas.append((r.status_code, r.json().get("detail")))

            inventado, de_la_otra = respuestas
            assert inventado[0] == 422, f"un id inventado quedo escrito: {inventado}"
            assert de_la_otra[0] == 422, (
                f"una obligacion de la empresa B quedo vinculada a un documento "
                f"de la A: {de_la_otra}"
            )
            assert inventado == de_la_otra, (
                "las dos negativas se distinguen, y eso es un oraculo para "
                f"enumerar identificadores ajenos: {respuestas}"
            )

            assert cliente.get(f"/api/v1/documents/{documento}/entities").json() == []
        finally:
            cliente.headers["X-Tenant-Id"] = EMPRESA_B
            cliente.delete(f"/api/v1/obligations/{ajena}")
            cliente.headers["X-Tenant-Id"] = EMPRESA_A

    def test_un_tipo_desconocido_no_pasa(self, cliente, documento) -> None:
        """Un `entity_type` que no esta en el mapa se rechaza, no se ignora.

        Dejarlo pasar seria peor que un error: la base lo rechazaria despues
        por el CHECK, y eso llega como **500** en vez de como un mensaje.
        """
        r = cliente.post(
            f"/api/v1/documents/{documento}/entities",
            json={
                "entity_type": "invento",
                "entity_id": str(uuid.uuid4()),
                "purpose": "evidence",
            },
        )
        assert r.status_code == 422, r.text


class TestLoQueSiSeVincula:
    def test_una_obligacion_propia(self, cliente, documento) -> None:
        propia = _obligacion(cliente, EMPRESA_A)
        try:
            r = cliente.post(
                f"/api/v1/documents/{documento}/entities",
                json={
                    "entity_type": "obligation",
                    "entity_id": propia,
                    "purpose": "evidence",
                },
            )
            assert r.status_code == 201, r.text
        finally:
            cliente.delete(f"/api/v1/obligations/{propia}")

    def test_una_norma_del_catalogo(self, cliente, documento) -> None:
        """RF-108 nombra la norma, y hasta `db/27` el CHECK no la admitia.

        `legal_norms` es catalogo **global**: no lleva `tenant_id` ni RLS, asi
        que cualquier empresa puede colgar su politica de la norma que la
        exige. Si algun dia se le pusiera RLS, esta prueba se pondria en rojo
        — que es exactamente lo que tiene que pasar.
        """
        normas = cliente.get("/api/v1/catalog/norms/?limit=1").json()
        if not normas:
            pytest.skip("el catalogo esta vacio")
        r = cliente.post(
            f"/api/v1/documents/{documento}/entities",
            json={
                "entity_type": "legal_norm",
                "entity_id": normas[0]["id"],
                "purpose": "support",
            },
        )
        assert r.status_code == 201, r.text

    def test_un_proceso(self, cliente, documento) -> None:
        """El otro que faltaba: un procedimiento y el proceso que describe."""
        procesos = cliente.get("/api/v1/processes/?limit=1").json()
        if not procesos:
            pytest.skip("la empresa no tiene procesos")
        r = cliente.post(
            f"/api/v1/documents/{documento}/entities",
            json={
                "entity_type": "process",
                "entity_id": procesos[0]["id"],
                "purpose": "support",
            },
        )
        assert r.status_code == 201, r.text


class TestElSentidoInverso:
    def test_desde_la_obligacion_se_ve_su_respaldo(self, cliente, documento) -> None:
        """El sentido que la gente usa.

        La pregunta de un fiscalizador senala un requisito y pide la
        evidencia; "que respalda este documento" no contesta eso.
        """
        propia = _obligacion(cliente, EMPRESA_A)
        try:
            cliente.post(
                f"/api/v1/documents/{documento}/entities",
                json={
                    "entity_type": "obligation",
                    "entity_id": propia,
                    "purpose": "evidence",
                },
            )
            r = cliente.get(
                "/api/v1/documents/vinculados",
                params={"entity_type": "obligation", "entity_id": propia},
            )
            assert r.status_code == 200, r.text
            assert [d["id"] for d in r.json()] == [documento]
        finally:
            cliente.delete(f"/api/v1/obligations/{propia}")

    def test_no_queda_ensombrecido_por_el_id(self, cliente) -> None:
        """`/vinculados` va declarada ANTES de `/{document_id}`.

        FastAPI resuelve por orden de declaracion. Puesta despues, la ruta del
        id se come la palabra y responde **422 leyendo "vinculados" como
        UUID** — un error de orden de lineas, invisible leyendo la funcion. Ya
        paso con `/equipment/sin-operador`.
        """
        r = cliente.get(
            "/api/v1/documents/vinculados",
            params={"entity_type": "obligation", "entity_id": str(uuid.uuid4())},
        )
        detalle = str(r.json().get("detail", ""))
        assert "uuid" not in detalle.lower(), (
            f"la ruta quedo ensombrecida por /{{document_id}}: {r.status_code} {detalle}"
        )

    def test_una_entidad_ajena_no_devuelve_lista_vacia(self, cliente) -> None:
        """Vacio significaria "no tiene documentos", que es una respuesta.

        Preguntar por un registro de otra empresa no puede contestarse con una
        lista vacia: eso afirma algo sobre un registro que esta sesion no
        deberia poder ni nombrar.
        """
        ajena = _obligacion(cliente, EMPRESA_B)
        try:
            r = cliente.get(
                "/api/v1/documents/vinculados",
                params={"entity_type": "obligation", "entity_id": ajena},
            )
            assert r.status_code == 422, f"respondio {r.status_code}: {r.text[:120]}"
        finally:
            cliente.headers["X-Tenant-Id"] = EMPRESA_B
            cliente.delete(f"/api/v1/obligations/{ajena}")
            cliente.headers["X-Tenant-Id"] = EMPRESA_A


class TestLasDosListasDicenLoMismo:
    """El CHECK de la base y el mapa `ANCLAJES` no se pueden separar.

    Un tipo en el CHECK y no en el mapa: la aplicacion lo rechaza con 422
    aunque la base lo admita. Un tipo en el mapa y no en el CHECK: pasa la
    comprobacion y **revienta al escribir**, con un 500 en vez de un mensaje.

    La diferencia recien se veria usando el sistema, asi que la compara una
    maquina. Mismo criterio que la prueba que lee `db/22_crm.sql` y la que lee
    los Dockerfile.
    """

    def test_el_check_y_el_mapa_coinciden(self) -> None:
        sql = MIGRACION.read_text(encoding="utf-8")
        cuerpo = re.search(
            r"CHECK \(entity_type IN \((.*?)\)\)", sql, re.DOTALL
        )
        assert cuerpo, "no se encontro el CHECK en la migracion"

        # Se leen las comillas simples y no se parte por comas: los comentarios
        # `--` intercalados llevan texto libre. La primera version del guardian
        # de las dos listas del registro de mejora uso una expresion sobre
        # comas y **perdio una fila en silencio**.
        del_sql = set(re.findall(r"'([^']+)'", cuerpo.group(1)))

        assert del_sql == set(ANCLAJES), (
            "el CHECK de db/27 y el mapa ANCLAJES dicen cosas distintas.\n"
            f"  solo en el SQL:   {sorted(del_sql - set(ANCLAJES))}\n"
            f"  solo en el mapa:  {sorted(set(ANCLAJES) - del_sql)}"
        )

    def test_ningun_anclaje_se_quedo_sin_modelo(self) -> None:
        """Un `None` en el mapa se leeria como "nada que comprobar"."""
        assert all(ANCLAJES.values()), "hay anclajes sin modelo"
