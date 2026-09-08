"""Un mensaje del asistente puede guardar sus citas (para el AI Service).

## Que estaba roto, medido el 8-sep-2026

`chatbot_messages` tiene `citations` y `cited_norm_ids` desde el principio.
**Nadie las escribia nunca**, y por eso convivian dos defectos que se tapaban
entre si:

1. `ChatbotMessageCreate` **no las declaraba**, asi que Pydantic las descartaba
   en silencio: se mandaban las citas, respondia **201**, y la fila quedaba
   vacia. El defecto de campo descartado que este repositorio ya sufrio con
   `planned_start_date` y con `process_id`.
2. El modelo declaraba `cited_norm_ids` como **JSONB** y la columna real es
   **`uuid[]`**. O sea que si el primer defecto no hubiera existido, escribirla
   habria dado **500**: `column "cited_norm_ids" is of type uuid[] but
   expression is of type jsonb`.
3. `ChatbotMessageUpdate` declaraba `citations` como **`dict`** mientras la
   columna y `ChatbotMessageRead` la declaran **`list`**: dos esquemas del mismo
   campo diciendo tipos distintos.

Y `cited_norm_ids` **no salia en ninguna respuesta**, asi que ni escribiendola
se podia leer.

## Por que importa mas que un campo cualquiera

Es lo que el asistente existe para dar: una respuesta **con de donde la saco**.
Una respuesta normativa sin cita no se puede verificar, y en cumplimiento eso
es todo lo que importa — quien la reciba no puede distinguir un articulo real
de uno inventado.
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

EMPRESA = "a0000000-0000-0000-0000-000000000001"

CITAS = [
    {"norma": "Ley 19.300", "articulo": "11", "texto": "Los proyectos requeriran un EIA si..."}
]


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
def conversacion(cliente):
    with SessionLocal() as db:
        declarar(db, EMPRESA)
        uid = db.execute(
            text(
                "SELECT id FROM users WHERE deleted_at IS NULL "
                "ORDER BY created_at, id LIMIT 1"
            )
        ).scalar()
    if uid is None:  # pragma: no cover
        pytest.skip("el seed no tiene usuarios")

    r = cliente.post(
        "/api/v1/support/chatbot",
        json={"user_id": str(uid), "title": "Prueba de citas", "scope": "tenant"},
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    yield cid

    with SessionLocal() as db:
        declarar(db, EMPRESA)
        db.execute(
            text("DELETE FROM chatbot_messages WHERE conversation_id = :c"), {"c": cid}
        )
        db.execute(text("DELETE FROM chatbot_conversations WHERE id = :c"), {"c": cid})
        db.commit()


class TestLasCitasSeGuardan:
    def test_un_mensaje_conserva_sus_citas(self, cliente, conversacion) -> None:
        """El caso que motiva todo: antes respondia 201 y guardaba `[]`."""
        norma = str(uuid.uuid4())
        r = cliente.post(
            f"/api/v1/support/chatbot/{conversacion}/messages",
            json={
                "conversation_id": conversacion,
                "role": "assistant",
                "content": "El titular debe presentar un EIA.",
                "citations": CITAS,
                "cited_norm_ids": [norma],
            },
        )
        assert r.status_code == 201, r.text
        cuerpo = r.json()

        assert cuerpo["citations"] == CITAS, (
            "el mensaje se guardo SIN sus citas. Una respuesta normativa sin "
            "cita no se puede verificar, que es justo para lo que existe el "
            "asistente."
        )
        assert cuerpo["cited_norm_ids"] == [norma]

    def test_al_releer_siguen_ahi(self, cliente, conversacion) -> None:
        """La respuesta del POST puede venir del objeto en memoria; esto lee de
        la base."""
        cliente.post(
            f"/api/v1/support/chatbot/{conversacion}/messages",
            json={
                "conversation_id": conversacion,
                "role": "assistant",
                "content": "Con cita",
                "citations": CITAS,
            },
        )
        mensajes = cliente.get(
            f"/api/v1/support/chatbot/{conversacion}/messages"
        ).json()
        assert mensajes and mensajes[0]["citations"] == CITAS

    def test_cited_norm_ids_sale_en_la_respuesta(self, cliente, conversacion) -> None:
        """Estaba en la tabla y en ninguna respuesta: se podia escribir y no leer."""
        norma = str(uuid.uuid4())
        cliente.post(
            f"/api/v1/support/chatbot/{conversacion}/messages",
            json={
                "conversation_id": conversacion,
                "role": "assistant",
                "content": "Cita por id",
                "cited_norm_ids": [norma],
            },
        )
        mensajes = cliente.get(
            f"/api/v1/support/chatbot/{conversacion}/messages"
        ).json()
        assert any(m.get("cited_norm_ids") == [norma] for m in mensajes)

    def test_un_mensaje_sin_citas_queda_vacio_no_falla(
        self, cliente, conversacion
    ) -> None:
        """La pregunta del usuario no cita nada, y eso es normal.

        Tambien es el caso de una respuesta que **se abstiene** por falta de
        evidencia: sin citas, y correcta.
        """
        r = cliente.post(
            f"/api/v1/support/chatbot/{conversacion}/messages",
            json={
                "conversation_id": conversacion,
                "role": "user",
                "content": "Necesito un EIA?",
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["citations"] == []
        assert r.json()["cited_norm_ids"] == []


class TestLosTiposCoinciden:
    def test_cited_norm_ids_es_uuid_en_la_base(self) -> None:
        """El modelo decia JSONB y la columna es `uuid[]`.

        Con el modelo equivocado la escritura daba **500**, no un 422: es un
        error de tipo en el `INSERT`, no de validacion. Y nadie lo veia porque
        el otro defecto descartaba el campo antes de llegar.
        """
        from sqlalchemy.dialects.postgresql import ARRAY

        from app.models.support import ChatbotMessage

        columna = ChatbotMessage.__table__.c.cited_norm_ids
        assert isinstance(columna.type, ARRAY), (
            f"el modelo declara {columna.type!r} y la columna real es uuid[]"
        )

    def test_los_tres_esquemas_dicen_lo_mismo_de_citations(self) -> None:
        """Crear, leer y editar tienen que coincidir en el tipo.

        `ChatbotMessageUpdate` decia `dict` mientras la lectura dice `list`: un
        PATCH escribia algo que despues no validaba contra su propio contrato.
        """
        from app.schemas.support import (
            ChatbotMessageCreate,
            ChatbotMessageRead,
            ChatbotMessageUpdate,
        )

        for esquema in (ChatbotMessageCreate, ChatbotMessageRead, ChatbotMessageUpdate):
            campo = esquema.model_fields.get("citations")
            assert campo is not None, f"{esquema.__name__} no declara `citations`"
            assert "list" in str(campo.annotation), (
                f"{esquema.__name__}.citations es {campo.annotation}, y la "
                "columna es una lista JSONB"
            )
