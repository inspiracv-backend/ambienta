"""La conversacion de un ticket: en orden, del ticket correcto, con su autor real.

## Que estaba roto, medido el 13-sep-2026

Los mismos dos defectos que el 8-sep se arreglaron en los mensajes del chatbot,
y un tercero que aca pesa mas:

1. **La lectura no tenia `ORDER BY`.** Postgres devuelve el orden fisico.
2. **La escritura no comprobaba el ticket.** Inexistente daba 500 —revienta la
   clave foranea—; el de otra empresa daba 201 y la fila quedaba escrita, porque
   las claves foraneas no pasan por RLS.
3. **`author_user_id` salia del cuerpo.** Quien mandaba la peticion elegia el
   nombre bajo el que quedaba el mensaje.

## Por que el tercero importa

Desde el 13-sep **las correcciones de un registro erroneo (RF-83) viven aca**,
como `internal_note`. La pantalla promete *"queda registrado con tu nombre y la
fecha, y no se puede editar despues"* — y hasta hoy la correccion no llegaba a la
base, y el endpoint al que habria llegado dejaba elegir el nombre. Una correccion
atribuida a otro es lo que un auditor no puede distinguir de una real.
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


def _ticket(empresa: str) -> str:
    with SessionLocal() as db:
        declarar(db, empresa)
        tid = db.execute(
            text(
                "INSERT INTO support_tickets (tenant_id, guest_email, category, subject, description) "
                "VALUES (:t, 'qa@prueba.cl', 'other', '[QA] Ticket de prueba', 'para medir mensajes') "
                "RETURNING id"
            ),
            {"t": empresa},
        ).scalar()
        db.commit()
    return str(tid)


def _borrar(tid: str, empresa: str) -> None:
    with SessionLocal() as db:
        declarar(db, empresa)
        db.execute(
            text("DELETE FROM support_ticket_messages WHERE ticket_id = :t"), {"t": tid}
        )
        db.execute(text("DELETE FROM support_tickets WHERE id = :t"), {"t": tid})
        db.commit()


@pytest.fixture
def ticket(cliente):
    cliente.headers["X-Tenant-Id"] = EMPRESA_A
    tid = _ticket(EMPRESA_A)
    yield tid
    _borrar(tid, EMPRESA_A)


def _decir(cliente, tid: str, cuerpo: str, **extra) -> dict:
    r = cliente.post(
        f"/api/v1/support/tickets/{tid}/messages",
        json={"ticket_id": tid, "body": cuerpo, **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestElHiloSeLeeEnOrden:
    def test_los_mensajes_salen_como_se_escribieron(self, cliente, ticket) -> None:
        dichos = ["Primer mensaje", "Segundo", "Tercero", "Cuarto"]
        for d in dichos:
            _decir(cliente, ticket, d)
        leidos = [
            m["body"]
            for m in cliente.get(f"/api/v1/support/tickets/{ticket}/messages").json()
        ]
        assert leidos == dichos

    def test_marcar_un_mensaje_interno_no_lo_manda_al_final(
        self, cliente, ticket
    ) -> None:
        """Un `UPDATE` que no puede ser HOT mueve la fila al final del heap.

        `is_internal` no esta indexado, asi que por si solo seria HOT; lo que se
        comprueba es que el orden no dependa de eso, cambiando tambien el
        cuerpo en una transaccion aparte.
        """
        primero = _decir(cliente, ticket, "El primero")
        _decir(cliente, ticket, "El segundo")
        _decir(cliente, ticket, "El tercero")
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            db.execute(
                text(
                    "UPDATE support_ticket_messages "
                    "SET body = repeat('x', 3000), is_internal = true WHERE id = :i"
                ),
                {"i": primero["id"]},
            )
            db.commit()

        leidos = cliente.get(f"/api/v1/support/tickets/{ticket}/messages").json()
        assert leidos[0]["id"] == primero["id"], (
            "el mensaje editado dejo de ser el primero: el hilo se lee sin orden"
        )


class TestElTicketSeComprueba:
    def test_leer_un_ticket_inexistente_es_404(self, cliente) -> None:
        """Y no `[]`, que se leeria como «este ticket no tiene mensajes»."""
        r = cliente.get(f"/api/v1/support/tickets/{uuid.uuid4()}/messages")
        assert r.status_code == 404, r.text

    def test_escribir_en_uno_inexistente_es_404_y_no_500(self, cliente) -> None:
        tid = str(uuid.uuid4())
        r = cliente.post(
            f"/api/v1/support/tickets/{tid}/messages",
            json={"ticket_id": tid, "body": "Hola?"},
        )
        assert r.status_code == 404, r.text

    def test_no_se_escribe_en_el_ticket_de_otra_empresa(self, cliente) -> None:
        """**Las claves foraneas no pasan por RLS.**"""
        ajeno = _ticket(EMPRESA_B)
        try:
            r = cliente.post(  # el cliente va como la empresa A
                f"/api/v1/support/tickets/{ajeno}/messages",
                json={"ticket_id": ajeno, "body": "No deberia quedar"},
            )
            assert r.status_code == 404, r.text
            with SessionLocal() as db:
                declarar(db, EMPRESA_B)
                cuantos = db.execute(
                    text(
                        "SELECT count(*) FROM support_ticket_messages WHERE ticket_id = :t"
                    ),
                    {"t": ajeno},
                ).scalar()
            assert cuantos == 0
        finally:
            _borrar(ajeno, EMPRESA_B)


class TestElAutorNoSeElige:
    def test_no_se_puede_firmar_con_alguien_de_otra_empresa(
        self, cliente, ticket
    ) -> None:
        """Sin sesion identificada, un `author_user_id` del cuerpo solo vale si
        es de esta empresa. Antes lo aceptaba igual: la clave foranea solo mira
        que la fila exista."""
        with SessionLocal() as db:
            declarar(db, EMPRESA_B)
            ajeno = db.execute(
                text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
            ).scalar()
        if ajeno is None:  # pragma: no cover
            pytest.skip("la segunda empresa no tiene usuarios")

        r = cliente.post(
            f"/api/v1/support/tickets/{ticket}/messages",
            json={
                "ticket_id": ticket,
                "body": "Firmado por alguien de otra empresa",
                "author_user_id": str(ajeno),
            },
        )
        assert r.status_code == 422, r.text

    def test_una_correccion_se_guarda_como_nota_interna(
        self, cliente, ticket
    ) -> None:
        """El contrato que usa la pantalla para RF-83."""
        m = _decir(
            cliente,
            ticket,
            "Se corrigio la fecha de deteccion, estaba mal ingresada.",
            message_type="internal_note",
            is_internal=True,
        )
        assert m["message_type"] == "internal_note"
        assert m["is_internal"] is True
        leidos = cliente.get(f"/api/v1/support/tickets/{ticket}/messages").json()
        assert any("fecha de deteccion" in x["body"] for x in leidos), (
            "la correccion no quedo en el ticket al releer"
        )

    def test_una_correccion_no_se_reescribe(self, cliente, ticket) -> None:
        """La pantalla promete que no se puede editar despues, y la tabla no
        tiene `updated_at`: reescrita, no quedaria rastro."""
        m = _decir(
            cliente, ticket, "Texto original de la correccion",
            message_type="internal_note", is_internal=True,
        )
        r = cliente.patch(
            f"/api/v1/support/tickets/{ticket}/messages/{m['id']}",
            json={"body": "Texto cambiado"},
        )
        assert r.status_code == 409, r.text
        leidos = cliente.get(f"/api/v1/support/tickets/{ticket}/messages").json()
        assert [x["body"] for x in leidos] == ["Texto original de la correccion"]

    def test_un_comentario_si_se_corrige(self, cliente, ticket) -> None:
        """La regla es de las notas internas, no de todos los mensajes."""
        m = _decir(cliente, ticket, "Hola, tengo un problema con el acesso")
        r = cliente.patch(
            f"/api/v1/support/tickets/{ticket}/messages/{m['id']}",
            json={"body": "Hola, tengo un problema con el acceso"},
        )
        assert r.status_code == 200, r.text
