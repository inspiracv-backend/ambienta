"""La historia de un registro (RF-113, #75).

## Que vigila

Lo que hace que la linea de tiempo diga la verdad, no que devuelva filas:

| regla | lo que evita |
|---|---|
| el vocabulario se traduce | mostrar **cero** eventos con 9.575 filas en la base |
| las fuentes pendientes se declaran | que una historia sin correos parezca completa |
| el tope avisa | que una lista cortada afirme "esto es todo lo que paso" |
| el anclaje se comprueba | leer la historia de un registro de otra empresa |

El desajuste de vocabulario es el defecto de fondo y no se ve en ninguna
pantalla: `audit_log.entity_type` guarda `obligations` —el nombre de la tabla,
porque lo escribe el observador del `flush`— mientras comentarios y adjuntos
guardan `obligation`. Una union ingenua devuelve una lista vacia, que se lee
como "sobre este registro no paso nada".
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
from app.services.historial import FUENTES_PENDIENTES, tabla_de  # noqa: E402
from app.services.vinculos_de_documentos import ANCLAJES  # noqa: E402

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
def obligacion(cliente):
    r = cliente.post(
        "/api/v1/obligations/",
        json={"code": f"HIS-{uuid.uuid4().hex[:8].upper()}", "title": "Con historia"},
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    yield oid
    cliente.delete(f"/api/v1/obligations/{oid}")


def _historia(cliente, oid: str, tipo: str = "obligation"):
    return cliente.get(
        "/api/v1/historial/", params={"entity_type": tipo, "entity_id": oid}
    )


class TestElVocabularioSeTraduce:
    """El defecto de fondo, y el que no se ve en ninguna pantalla."""

    def test_la_tabla_sale_del_modelo_y_no_de_una_lista(self) -> None:
        """Si alguien escribiera la traduccion a mano, esto lo delataria.

        `tabla_de` deriva de `ANCLAJES[..].modelo.__tablename__`, asi que una
        entidad nueva no necesita que nadie se acuerde de agregarla en un
        cuarto lugar. La prueba fija que la derivacion siga siendo esa y no una
        constante disfrazada.
        """
        assert tabla_de("obligation") == "obligations"
        assert tabla_de("audit") == "audits"
        assert tabla_de("process") == "processes"
        # El caso que delata un mapa escrito a mano: dominio y tabla iguales.
        assert tabla_de("article_compliance") == "article_compliance"
        for tipo, anclaje in ANCLAJES.items():
            assert tabla_de(tipo) == anclaje.modelo.__tablename__

    def test_la_actividad_aparece_de_verdad(self, cliente, obligacion) -> None:
        """Crear la obligacion ya dejo un evento en `audit_log`.

        **Esta es la prueba que caza el desajuste.** Con la traduccion
        desconectada la lista sale vacia y la pantalla dice "sobre este registro
        no paso nada" — sobre un registro que se acaba de crear.
        """
        cliente.patch(
            f"/api/v1/obligations/{obligacion}", json={"title": "Con historia (v2)"}
        )
        r = _historia(cliente, obligacion)
        assert r.status_code == 200, r.text

        actividad = [e for e in r.json()["eventos"] if e["tipo"] == "actividad"]
        assert actividad, (
            "cero eventos de actividad sobre una obligacion recien creada y "
            "modificada. Es el desajuste de vocabulario: `audit_log` guarda "
            f"'{tabla_de('obligation')}' y la consulta pregunta por otra cosa."
        )


class TestLasTresFuentes:
    def test_la_conversacion_entra_en_la_historia(self, cliente, obligacion) -> None:
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            autor = db.execute(
                text(
                    "SELECT id FROM users WHERE deleted_at IS NULL "
                    "ORDER BY created_at, id LIMIT 1"
                )
            ).scalar()
            db.execute(
                text(
                    "INSERT INTO comments (tenant_id, entity_type, entity_id, "
                    "author_user_id, body) VALUES (:t, 'obligation', :e, :a, :b)"
                ),
                {
                    "t": EMPRESA_A,
                    "e": obligacion,
                    "a": autor,
                    "b": "La evidencia no coincide con el periodo",
                },
            )
            db.commit()
        try:
            eventos = _historia(cliente, obligacion).json()["eventos"]
            comentarios = [e for e in eventos if e["tipo"] == "comentario"]
            assert len(comentarios) == 1, eventos
            assert "evidencia" in comentarios[0]["detalle"]["cuerpo"]
            # El nombre resuelto: sin el, la pantalla mostraria un UUID.
            assert comentarios[0]["actor"], "el autor salio sin nombre"
        finally:
            with SessionLocal() as db:
                declarar(db, EMPRESA_A)
                db.execute(
                    text("DELETE FROM comments WHERE entity_id = :e"), {"e": obligacion}
                )
                db.commit()

    def test_un_adjunto_entra_en_la_historia(self, cliente, obligacion) -> None:
        doc = cliente.post(
            "/api/v1/documents/",
            json={"document_type": "procedimiento", "title": "Respaldo"},
        )
        assert doc.status_code == 201, doc.text
        did = doc.json()["id"]
        try:
            v = cliente.post(
                f"/api/v1/documents/{did}/entities",
                json={
                    "entity_type": "obligation",
                    "entity_id": obligacion,
                    "purpose": "evidence",
                },
            )
            assert v.status_code == 201, v.text

            adjuntos = [
                e for e in _historia(cliente, obligacion).json()["eventos"]
                if e["tipo"] == "adjunto"
            ]
            assert len(adjuntos) == 1, adjuntos
            assert adjuntos[0]["detalle"]["titulo"] == "Respaldo"
        finally:
            cliente.delete(f"/api/v1/documents/{did}")

    def test_los_eventos_vienen_del_mas_reciente_al_mas_antiguo(
        self, cliente, obligacion
    ) -> None:
        """En una fiscalizacion la primera pregunta es que paso al final."""
        cliente.patch(f"/api/v1/obligations/{obligacion}", json={"title": "Otro"})
        fechas = [e["ocurrido_el"] for e in _historia(cliente, obligacion).json()["eventos"]]
        assert fechas == sorted(fechas, reverse=True), fechas


class TestLoQueNoSeCalla:
    def test_declara_que_el_correo_es_una_fuente_pendiente(
        self, cliente, obligacion
    ) -> None:
        """RF-113 nombra cuatro fuentes y la captura de correos no existe.

        Mostrar tres y callarse la cuarta deja una linea de tiempo que **se ve
        completa**, y alguien concluye que sobre ese registro no hubo correos
        cuando lo que pasa es que el sistema todavia no los mira. En un modulo
        cuya razon de ser es "la informacion se maneja por correo y se pierde",
        esa omision seria el error que viene a arreglar.
        """
        cuerpo = _historia(cliente, obligacion).json()
        assert "correo" in cuerpo["fuentes_pendientes"], (
            "la historia no dice que le falta el correo, asi que se lee como "
            f"completa: {cuerpo['fuentes_pendientes']}"
        )
        assert "correo" not in cuerpo["fuentes"]
        assert set(cuerpo["fuentes"]) == {"actividad", "comentario", "adjunto"}

    def test_la_constante_no_se_vacia_sola(self) -> None:
        """El dia que RF-107 (#72) exista, esto **debe** ponerse en rojo.

        Es el mismo criterio que las pruebas que fijan los 12 sistemas del RETC
        y no los 9 de la SMA: la prueba marca un pendiente, y borrarla es parte
        de terminarlo.
        """
        assert FUENTES_PENDIENTES == ("correo",), (
            "cambio la lista de fuentes pendientes. Si es porque la captura de "
            "correos ya existe, esta prueba y el `fuentes_pendientes` del "
            "servicio se actualizan juntos."
        )

    def test_una_historia_vacia_es_una_respuesta(self, cliente) -> None:
        """Sin eventos, lista vacia — pero con las fuentes igual declaradas.

        **El registro vacio es una norma del catalogo, y no una obligacion a la
        que se le borro la actividad.** La primera version de esta prueba hacia
        `DELETE FROM audit_log` y la base la freno: `ambienta_app` tiene
        `REVOKE UPDATE, DELETE` sobre esa tabla a proposito — un registro de
        auditoria que la aplicacion puede borrar no sirve como registro de
        auditoria. La restriccion tenia razon y la prueba estaba mal.

        `legal_norms` no tiene ninguna fila en `audit_log` porque el catalogo
        lo sincroniza una tarea, no un usuario. Si algun dia la tuviera, esta
        prueba se pondria en rojo y habria que buscar otro registro sin
        historia — no desactivarla.
        """
        normas = cliente.get("/api/v1/catalog/norms/?limit=1").json()
        if not normas:
            pytest.skip("el catalogo esta vacio")

        cuerpo = _historia(cliente, normas[0]["id"], tipo="legal_norm").json()
        assert cuerpo["eventos"] == [], (
            "esta norma tiene historia, asi que ya no sirve para medir el vacio"
        )
        assert cuerpo["hay_mas"] is False
        # Vacia, y aun asi declara lo que le falta: el vacio no significa
        # "no hubo correos", significa "no hay nada de las tres que si miro".
        assert cuerpo["fuentes_pendientes"] == ["correo"]


class TestElAnclaje:
    def test_no_se_lee_la_historia_de_otra_empresa(self, cliente) -> None:
        cliente.headers["X-Tenant-Id"] = EMPRESA_B
        ajena = cliente.post(
            "/api/v1/obligations/",
            json={"code": f"HIS-{uuid.uuid4().hex[:8].upper()}", "title": "De la B"},
        ).json()["id"]
        cliente.headers["X-Tenant-Id"] = EMPRESA_A
        try:
            r = _historia(cliente, ajena)
            assert r.status_code == 422, (
                "devolvio la historia —o una lista vacia, que afirma que no "
                f"paso nada— de un registro de otra empresa: {r.status_code}"
            )
        finally:
            cliente.headers["X-Tenant-Id"] = EMPRESA_B
            cliente.delete(f"/api/v1/obligations/{ajena}")
            cliente.headers["X-Tenant-Id"] = EMPRESA_A

    def test_un_tipo_desconocido_no_tiene_historia(self, cliente, obligacion) -> None:
        assert _historia(cliente, obligacion, tipo="invento").status_code == 422
