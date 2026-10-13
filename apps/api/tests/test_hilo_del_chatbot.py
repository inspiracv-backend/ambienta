"""El hilo del asistente se lee en orden y no acepta conversaciones ajenas.

## Que estaba roto, medido el 8-sep-2026

`GET /support/chatbot/{id}/messages` y su `POST` eran **los dos unicos
endpoints anidados de `routers/support.py` que no comprobaban nada**. Sus
vecinos —los mensajes de ticket, el mensaje suelto del chatbot— usan
`obtener_o_404` y `verificar_padre` desde siempre.

Tres defectos, y ninguno fallaba:

1. **La lectura no tenia `ORDER BY`.** Postgres devuelve las filas como quiera,
   y un `UPDATE` mueve la fila al final del heap: el `PATCH` que existe para
   agregarle las citas a un mensaje lo mandaba al final del hilo. En un chat el
   orden **es** la conversacion.
2. **Escribir en una conversacion inexistente daba 500**, no 404 — revienta la
   clave foranea. Un servicio que reintenta ante 5xx reintenta para siempre.
3. **Escribir en la conversacion de otra empresa daba 201.** Las claves
   foraneas no pasan por RLS (CLAUDE.md §4), asi que la fila quedaba escrita
   con el `tenant_id` propio colgando de un hilo ajeno.

## Por que importa mas que en otro modulo

De aca sale el contexto que el servicio de IA le manda al modelo. Un historial
barajado le hace contestar otra cosa, y no hay ningun sintoma: la respuesta
llega, se ve bien redactada, y contesta a una conversacion que nadie tuvo.
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


def _un_usuario(empresa: str) -> str | None:
    with SessionLocal() as db:
        declarar(db, empresa)
        return db.execute(
            text(
                "SELECT id FROM users WHERE deleted_at IS NULL "
                "ORDER BY created_at, id LIMIT 1"
            )
        ).scalar()


def _borrar(empresa: str, cid: str) -> None:
    with SessionLocal() as db:
        declarar(db, empresa)
        db.execute(
            text("DELETE FROM chatbot_messages WHERE conversation_id = :c"), {"c": cid}
        )
        db.execute(text("DELETE FROM chatbot_conversations WHERE id = :c"), {"c": cid})
        db.commit()


@pytest.fixture
def conversacion(cliente):
    uid = _un_usuario(EMPRESA_A)
    if uid is None:  # pragma: no cover
        pytest.skip("el seed no tiene usuarios")

    r = cliente.post(
        "/api/v1/support/chatbot",
        json={"user_id": str(uid), "title": "Prueba de hilo", "scope": "tenant"},
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    yield cid
    _borrar(EMPRESA_A, cid)


def _decir(cliente, cid: str, role: str, content: str) -> int:
    r = cliente.post(
        f"/api/v1/support/chatbot/{cid}/messages",
        json={"conversation_id": cid, "role": role, "content": content},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestElHiloSeLeeEnOrden:
    def test_los_turnos_salen_como_se_dijeron(self, cliente, conversacion) -> None:
        """El caso base: cuatro turnos, en el orden en que se escribieron."""
        dichos = ["Necesito un EIA?", "Depende.", "De que?", "Del articulo 11."]
        for i, texto in enumerate(dichos):
            _decir(cliente, conversacion, "user" if i % 2 == 0 else "assistant", texto)

        leidos = [
            m["content"]
            for m in cliente.get(
                f"/api/v1/support/chatbot/{conversacion}/messages"
            ).json()
        ]
        assert leidos == dichos

    def test_anotar_las_normas_citadas_no_manda_el_mensaje_al_final(
        self, cliente, conversacion
    ) -> None:
        """**El caso que motiva el `ORDER BY`, y el `PATCH` importa cual es.**

        Sin orden explicito la consulta devuelve el orden fisico del heap, y un
        `UPDATE` mueve la fila **solo si no puede ser HOT**. Medido el 8-sep con
        cuatro mensajes seguidos:

        | operacion | lo que devuelve la consulta sin `ORDER BY` |
        |---|---|
        | recien insertados | `[37, 38, 39, 40]` |
        | `PATCH citations` | `[37, 38, 39, 40]` |
        | **`PATCH cited_norm_ids`** | **`[37, 39, 40, 38]`** |

        La diferencia es `ix_msg_citednorms`, el indice GIN sobre
        `cited_norm_ids`: tocar una columna indexada descarta HOT, la fila nueva
        se escribe al final y el mensaje se va con ella.

        O sea que la operacion que baraja el hilo es **anotar que normas cito el
        asistente** — justo lo que el servicio de IA existe para escribir.

        Por eso esta prueba usa esa columna y no `citations`: la primera version
        patcheaba `citations`, la mutacion la sobrevivio y la prueba no
        comprobaba nada. Si alguna vez vuelve a sobrevivir, la causa es HOT, no
        que el endpoint este bien.
        """
        primero = _decir(cliente, conversacion, "assistant", "El titular debe.")
        _decir(cliente, conversacion, "user", "Segundo turno.")
        _decir(cliente, conversacion, "assistant", "Tercer turno.")

        r = cliente.patch(
            f"/api/v1/support/chatbot/{conversacion}/messages/{primero}",
            json={"cited_norm_ids": [str(uuid.uuid4())]},
        )
        assert r.status_code == 200, r.text

        leidos = cliente.get(
            f"/api/v1/support/chatbot/{conversacion}/messages"
        ).json()
        assert leidos[0]["id"] == primero, (
            "el mensaje anotado se fue al final del hilo. El contexto que se le "
            "manda al modelo queda barajado y no hay ningun sintoma."
        )
        assert [m["content"] for m in leidos] == [
            "El titular debe.",
            "Segundo turno.",
            "Tercer turno.",
        ]


class TestLaConversacionSeComprueba:
    def test_leer_una_conversacion_inexistente_es_404(self, cliente) -> None:
        """Y no `[]`, que se leeria como «esta conversacion no tiene mensajes»."""
        r = cliente.get(f"/api/v1/support/chatbot/{uuid.uuid4()}/messages")
        assert r.status_code == 404, r.text

    def test_escribir_en_una_inexistente_es_404_y_no_500(self, cliente) -> None:
        """Antes reventaba la clave foranea.

        Importa el codigo y no solo que falle: un servicio que reintenta ante
        5xx reintentaria para siempre algo que nunca va a funcionar.
        """
        r = cliente.post(
            f"/api/v1/support/chatbot/{uuid.uuid4()}/messages",
            json={
                "conversation_id": str(uuid.uuid4()),
                "role": "user",
                "content": "Hola?",
            },
        )
        assert r.status_code == 404, r.text

    def test_no_se_puede_escribir_en_la_conversacion_de_otra_empresa(
        self, cliente
    ) -> None:
        """**Las claves foraneas no pasan por RLS.**

        La empresa B abre una conversacion; la empresa A manda un mensaje a ese
        id. Antes: 201, y la fila quedaba escrita con el `tenant_id` de A
        colgando de un hilo de B.
        """
        uid_b = _un_usuario(EMPRESA_B)
        if uid_b is None:  # pragma: no cover
            pytest.skip("la segunda empresa del seed no tiene usuarios")

        # La conversacion se crea con la sesion de B, no con la del cliente.
        with SessionLocal() as db:
            declarar(db, EMPRESA_B)
            ajena = db.execute(
                text(
                    "INSERT INTO chatbot_conversations (tenant_id, user_id, title) "
                    "VALUES (:t, :u, 'Hilo de la otra empresa') RETURNING id"
                ),
                {"t": EMPRESA_B, "u": uid_b},
            ).scalar()
            db.commit()

        try:
            r = cliente.post(  # el cliente lleva X-Tenant-Id de la empresa A
                f"/api/v1/support/chatbot/{ajena}/messages",
                json={
                    "conversation_id": str(ajena),
                    "role": "user",
                    "content": "Esto no deberia quedar escrito.",
                },
            )
            assert r.status_code == 404, (
                f"la empresa A escribio en el hilo de B ({r.status_code}). Las "
                "claves foraneas no comprueban el tenant."
            )

            with SessionLocal() as db:
                declarar(db, EMPRESA_B)
                cuantos = db.execute(
                    text(
                        "SELECT count(*) FROM chatbot_messages "
                        "WHERE conversation_id = :c"
                    ),
                    {"c": ajena},
                ).scalar()
            assert cuantos == 0
        finally:
            _borrar(EMPRESA_B, str(ajena))
