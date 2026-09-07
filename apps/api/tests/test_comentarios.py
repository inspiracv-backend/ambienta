"""La conversacion sobre un registro: hilos y menciones (RF-111, RF-112, #74).

## Que vigilan estas pruebas

No que se pueda escribir un comentario —eso se ve leyendo el router— sino las
cuatro reglas que **cambian lo que queda escrito** en un registro que se
exporta a un auditor:

| regla | lo que evita |
|---|---|
| el autor es obligatorio | dejar escrito que alguien dijo algo que no dijo |
| el hilo es de un nivel | que una respuesta le conteste a otra persona |
| la mencion ajena falla igual que la inexistente | un oraculo para enumerar usuarios |
| borrar la raiz conserva las respuestas | que una persona borre lo que escribieron otras |

Van **por el camino HTTP real**, que es lo unico que pasa por `app/errores.py`.
La identidad se simula con `dependency_overrides[get_current_user]` —el mismo
recurso que `test_perfil_empresa.py`—: lo unico simulado es **de donde sale**
el usuario; la guarda del router corre entera.
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

from app.auth import CurrentUser  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.deps import declarar, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
EMPRESA_B = "a0000000-0000-0000-0000-000000000002"


def _hay_base() -> bool:
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
        return True
    except Exception:  # pragma: no cover - entorno sin base
        return False


@pytest.fixture(scope="module")
def gente():
    """Dos usuarios de la empresa A y uno de la B, con `clerk_id` conocido.

    Se **escriben** en la base porque la guarda del router corre en la sesion
    del request y no ve una transaccion abierta aparte. Se restaura al final.
    """
    if not _hay_base():
        pytest.skip("Sin base de datos disponible. Hace falta docker compose.")

    previos: list[tuple] = []
    salida: dict[str, dict] = {}
    with SessionLocal() as db:
        for etiqueta, empresa in (("autor", EMPRESA_A), ("companero", EMPRESA_A), ("ajeno", EMPRESA_B)):
            declarar(db, empresa)
            fila = db.execute(
                # **`ORDER BY created_at, id` y no solo la fecha.** Los cinco
                # usuarios del seed se insertan en la misma sentencia, asi que
                # comparten `created_at` **al microsegundo** y el orden queda
                # sin definir: dos consultas con OFFSET 0 y OFFSET 1 pueden
                # devolver la misma fila. Paso: "autor" y "companero" eran la
                # misma persona, y dos pruebas fallaron acusando al codigo
                # —una decia que cualquiera edita el comentario de otro— cuando
                # el error estaba aca.
                text(
                    "SELECT id, clerk_id, full_name FROM users "
                    "WHERE deleted_at IS NULL ORDER BY created_at, id "
                    "OFFSET :o LIMIT 1"
                ),
                {"o": 1 if etiqueta == "companero" else 0},
            ).first()
            if fila is None:  # pragma: no cover
                pytest.skip(f"El seed no tiene suficientes usuarios en {empresa}.")
            uid, clerk_previo, nombre = fila
            clerk = clerk_previo or f"user_prueba_{uuid.uuid4().hex[:10]}"
            db.execute(
                text("UPDATE users SET clerk_id = :c WHERE id = :u"),
                {"c": clerk, "u": uid},
            )
            previos.append((empresa, uid, clerk_previo))
            salida[etiqueta] = {
                "id": str(uid),
                "clerk": clerk,
                "nombre": nombre,
                "tenant": empresa,
            }
        db.commit()

    yield salida

    with SessionLocal() as db:
        for empresa, uid, clerk_previo in previos:
            declarar(db, empresa)
            db.execute(
                text("UPDATE users SET clerk_id = :c WHERE id = :u"),
                {"c": clerk_previo, "u": uid},
            )
        db.commit()


@pytest.fixture
def como(gente):
    """Un cliente HTTP actuando como una de esas personas.

    **Ojo: `dependency_overrides` es global**, asi que actua el ultimo `como()`
    que se haya llamado — tener dos clientes "a la vez" no funciona. Se
    descubrio con una prueba de aca que creaba la obligacion ajena **despues**
    de tomar el cliente del autor, y terminaba comentando como el usuario de la
    empresa B: la prueba acusaba al codigo y el error era del arnes. Las
    pruebas llaman a `como()` **inmediatamente antes** de cada peticion cuyo
    autor importe.
    """
    from app.config import get_settings

    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    get_settings.cache_clear()

    def hacer(etiqueta: str = "autor") -> TestClient:
        quien = gente[etiqueta]
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id=quien["clerk"], tenant_id=quien["tenant"]
        )
        c = TestClient(app)
        c.headers["X-Tenant-Id"] = quien["tenant"]
        return c

    yield hacer
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def obligacion(como):
    """Una obligacion de la empresa A sobre la que conversar."""
    c = como("autor")
    r = c.post(
        "/api/v1/obligations/",
        json={"code": f"CMT-{uuid.uuid4().hex[:8].upper()}", "title": "Para conversar"},
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    yield oid
    c.delete(f"/api/v1/obligations/{oid}")
    # **Y su conversacion.** Borrar la obligacion no se lleva los comentarios
    # —a proposito: el borrado es logico y el rastro se conserva— asi que sin
    # esto cada corrida deja filas huerfanas en la base de desarrollo. Se
    # descubrio contando: 159 comentarios de prueba despues de unas pocas
    # corridas. No rompe nada y ensucia la demostracion.
    with SessionLocal() as db:
        declarar(db, EMPRESA_A)
        db.execute(
            text(
                "DELETE FROM comment_mentions WHERE comment_id IN "
                "(SELECT id FROM comments WHERE entity_id = :e)"
            ),
            {"e": oid},
        )
        db.execute(text("DELETE FROM comments WHERE entity_id = :e"), {"e": oid})
        db.execute(
            text("DELETE FROM notifications WHERE dedupe_key LIKE 'mencion:%' "
                 "AND context->>'entity_id' = :e"),
            {"e": oid},
        )
        db.commit()


def _comentar(c: TestClient, oid: str, **extra):
    cuerpo = {"entity_type": "obligation", "entity_id": oid, "body": "Un comentario"}
    cuerpo.update(extra)
    return c.post("/api/v1/comentarios/", json=cuerpo)


class TestElAutorNoSeInventa:
    def test_sin_sesion_identificada_responde_409(self, obligacion) -> None:
        """No se atribuye al primer administrador de la empresa.

        Esa es la salida comoda y deja escrito que esa persona dijo algo que no
        dijo — en el registro que lee un auditor. Mismo criterio que aprobar
        una revision documental.
        """
        app.dependency_overrides.pop(get_current_user, None)
        c = TestClient(app)
        c.headers["X-Tenant-Id"] = EMPRESA_A

        r = _comentar(c, obligacion)
        assert r.status_code == 409, f"escribio un comentario sin autor: {r.text[:150]}"

        assert c.get(
            "/api/v1/comentarios/",
            params={"entity_type": "obligation", "entity_id": obligacion},
        ).json() == []

    def test_el_comentario_lleva_quien_lo_escribio(self, como, gente, obligacion) -> None:
        c = como("autor")
        r = _comentar(c, obligacion)
        assert r.status_code == 201, r.text
        assert r.json()["author_user_id"] == gente["autor"]["id"]
        # El nombre viene resuelto: sin eso la pantalla tendria que pedir
        # `/users/` y quedarse sin autor si esa llamada falla.
        assert r.json()["author_name"] == gente["autor"]["nombre"]


class TestElHiloEsDeUnNivel:
    def test_una_respuesta_cuelga_de_su_comentario(self, como, obligacion) -> None:
        c = como("autor")
        raiz = _comentar(c, obligacion).json()
        respuesta = _comentar(c, obligacion, parent_id=raiz["id"], body="Contesto")
        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["parent_id"] == raiz["id"]

    def test_responder_a_una_respuesta_se_rechaza_diciendo_la_raiz(
        self, como, obligacion
    ) -> None:
        """No se reacomoda contra la raiz, se rechaza.

        Aplanarla es lo que hace un chat y aca cambia el registro: en una
        discusion sobre si una evidencia sirve, colgar la respuesta del
        comentario equivocado le atribuye al autor que le contestaba a otra
        persona. Un 422 que dice la raiz el cliente sabe manejarlo; que su
        respuesta se mueva sola, no.
        """
        c = como("autor")
        raiz = _comentar(c, obligacion).json()
        respuesta = _comentar(c, obligacion, parent_id=raiz["id"], body="Contesto").json()

        r = _comentar(c, obligacion, parent_id=respuesta["id"], body="Y ademas")
        assert r.status_code == 422, f"anido dos niveles: {r.text[:150]}"
        assert raiz["id"] in r.json()["detail"], (
            "el rechazo no dice cual es la raiz, que es lo unico que lo hace util: "
            f"{r.json()['detail']}"
        )

    def test_no_se_responde_a_un_comentario_de_otro_registro(
        self, como, obligacion
    ) -> None:
        """Un hilo pertenece a un registro: partido en dos fichas no es un hilo."""
        c = como("autor")
        ajeno = _comentar(c, obligacion).json()
        otra = c.post(
            "/api/v1/obligations/",
            json={"code": f"CMT-{uuid.uuid4().hex[:8].upper()}", "title": "Otra"},
        ).json()
        try:
            r = _comentar(c, otra["id"], parent_id=ajeno["id"])
            assert r.status_code == 422, r.text
        finally:
            c.delete(f"/api/v1/obligations/{otra['id']}")


class TestLasMenciones:
    def test_mencionar_registra_y_encola_un_aviso(self, como, gente, obligacion) -> None:
        c = como("autor")
        r = _comentar(c, obligacion, menciones=[gente["companero"]["id"]])
        assert r.status_code == 201, r.text
        assert r.json()["menciones"] == [gente["companero"]["id"]]

        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            encolados = db.execute(
                text(
                    "SELECT count(*) FROM notifications "
                    "WHERE dedupe_key = :k AND recipient_user_id = :u"
                ),
                {"k": f"mencion:{r.json()['id']}", "u": gente["companero"]["id"]},
            ).scalar()
        assert encolados == 1, (
            "la mencion no encolo aviso. RF-112 es 'menciones **con "
            "notificacion**': sin el aviso, mencionar a alguien no hace nada."
        )

    def test_mencionarse_a_uno_mismo_no_encola_nada(self, como, gente, obligacion) -> None:
        """Es frecuente al escribir ("me lo llevo yo") y un aviso por eso
        entrena a ignorarlos."""
        c = como("autor")
        r = _comentar(c, obligacion, menciones=[gente["autor"]["id"]])
        assert r.status_code == 201, r.text

        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            n = db.execute(
                text("SELECT count(*) FROM notifications WHERE dedupe_key = :k"),
                {"k": f"mencion:{r.json()['id']}"},
            ).scalar()
        assert n == 0, "se auto-notifico"
        # Pero la mencion **si** queda registrada: es parte del texto.
        assert r.json()["menciones"] == [gente["autor"]["id"]]

    def test_alguien_de_otra_empresa_falla_como_uno_inexistente(
        self, como, gente, obligacion
    ) -> None:
        """Mismo codigo y mismo mensaje.

        Distinguirlos convertiria el campo en un oraculo: mandando ids al azar
        se averiguaria cuales son usuarios reales de otras empresas.
        """
        c = como("autor")
        respuestas = []
        for uid in (str(uuid.uuid4()), gente["ajeno"]["id"]):
            r = _comentar(c, obligacion, menciones=[uid])
            respuestas.append((r.status_code, r.json().get("detail")))

        inventado, de_la_otra = respuestas
        assert inventado[0] == 422, inventado
        assert de_la_otra[0] == 422, (
            f"se menciono a un usuario de la empresa B: {de_la_otra}"
        )
        assert inventado == de_la_otra, (
            f"las dos negativas se distinguen, y eso es un oraculo: {respuestas}"
        )

    def test_mencionar_dos_veces_a_la_misma_persona_es_una_mencion(
        self, como, gente, obligacion
    ) -> None:
        """"@juan, avisale a @juan" no le manda dos avisos — y sin deduplicar
        el indice unico de la base responderia 500."""
        c = como("autor")
        uid = gente["companero"]["id"]
        r = _comentar(c, obligacion, menciones=[uid, uid])
        assert r.status_code == 201, r.text
        assert r.json()["menciones"] == [uid]


class TestLoQueQuedaEscrito:
    def test_editar_deja_marca(self, como, obligacion) -> None:
        c = como("autor")
        creado = _comentar(c, obligacion).json()
        assert creado["edited_at"] is None

        r = c.patch(f"/api/v1/comentarios/{creado['id']}", json={"body": "Corregido"})
        assert r.status_code == 200, r.text
        assert r.json()["body"] == "Corregido"
        assert r.json()["edited_at"] is not None, (
            "un comentario editado despues de que alguien lo respondio cambia "
            "lo que quedo escrito, y quien lo lea tiene que poder saberlo"
        )

    def test_nadie_edita_el_comentario_de_otro(self, como, obligacion) -> None:
        """No hay caso legitimo: editar el comentario de otro es cambiar lo que
        esa persona dijo. 404 y no 403, para no confirmar que existe."""
        creado = _comentar(como("autor"), obligacion).json()
        r = como("companero").patch(
            f"/api/v1/comentarios/{creado['id']}", json={"body": "Lo cambio yo"}
        )
        assert r.status_code == 404, r.text

    def test_borrar_la_raiz_conserva_las_respuestas(self, como, obligacion) -> None:
        """Eliminarlas haria que la decision de una persona borrara lo que
        escribieron otras."""
        c = como("autor")
        raiz = _comentar(c, obligacion, body="La pregunta").json()
        _comentar(c, obligacion, parent_id=raiz["id"], body="La respuesta de otro")

        assert c.delete(f"/api/v1/comentarios/{raiz['id']}").status_code == 204

        hilo = c.get(
            "/api/v1/comentarios/",
            params={"entity_type": "obligation", "entity_id": obligacion},
        ).json()
        cuerpos = [x["body"] for x in hilo]
        assert "La pregunta" not in cuerpos
        assert "La respuesta de otro" in cuerpos, (
            f"borrar la raiz se llevo las respuestas: {cuerpos}"
        )


class TestElPermiso:
    """La guarda no la pone la ruta, la pone el handler — y hay que probarlo.

    `comentarios` esta en `SIN_GUARDA_DE_PERMISO` porque el permiso sale del
    **cuerpo** y no del camino: una sola ruta cubre trece entidades. Sin estas
    pruebas, esa excepcion seria indistinguible de una ruta sin permisos, y el
    rol `servicio_lectura` —que solo tiene lecturas— podria escribir
    comentarios en cualquier ficha de la empresa.
    """

    def test_las_familias_existen_en_el_catalogo(self) -> None:
        """Una familia inventada es un 403 para todos.

        Es la leccion del CRM: un permiso que ningun rol concede no protege,
        deja la funcionalidad muerta — y el sintoma, "no puedo comentar", no se
        parece en nada a la causa.
        """
        from sqlalchemy import text as sql

        from app.services.vinculos_de_documentos import ANCLAJES

        if not _hay_base():
            pytest.skip("Sin base de datos disponible.")

        with SessionLocal() as db:
            existentes = {
                c for (c,) in db.execute(sql("SELECT code FROM permissions")).all()
            }

        faltan = {
            f"{a.familia}.{accion}"
            for a in ANCLAJES.values()
            for accion in ("read", "write")
        } - existentes
        assert not faltan, (
            f"Familias de ANCLAJES sin permiso en el catalogo: {sorted(faltan)}. "
            "Comentar sobre esas entidades responderia 403 a todo el mundo."
        )

    def test_sin_el_permiso_de_escritura_responde_403(
        self, como, gente, obligacion
    ) -> None:
        """Se le quita `obligation.write` a la persona y se mide."""
        from sqlalchemy import text as sql

        from app.deps import declarar as declarar_tenant

        uid = gente["autor"]["id"]
        with SessionLocal() as db:
            declarar_tenant(db, EMPRESA_A)
            db.execute(
                sql(
                    # `granted = false` es la denegacion individual, y **gana
                    # sobre el rol**: es el permiso efectivo que describe
                    # CLAUDE.md. La columna es `granted`, no `effect` — la
                    # primera version de esta prueba invento el nombre.
                    "INSERT INTO user_permissions (tenant_id, user_id, permission_id, granted) "
                    "SELECT :t, :u, id, false FROM permissions WHERE code = 'obligation.write' "
                    "ON CONFLICT (user_id, permission_id) DO UPDATE SET granted = false"
                ),
                {"t": EMPRESA_A, "u": uid},
            )
            db.commit()
        try:
            r = _comentar(como("autor"), obligacion)
            assert r.status_code == 403, (
                "sin `obligation.write` igual escribio el comentario: "
                f"{r.status_code} {r.text[:120]}"
            )
        finally:
            with SessionLocal() as db:
                declarar_tenant(db, EMPRESA_A)
                db.execute(
                    sql("DELETE FROM user_permissions WHERE user_id = :u AND granted = false"),
                    {"u": uid},
                )
                db.commit()


class TestElAnclaje:
    def test_no_se_comenta_sobre_un_registro_de_otra_empresa(
        self, como, obligacion
    ) -> None:
        """Mismo servicio que RF-108: el anclaje se comprueba con RLS."""
        # La ajena se crea PRIMERO: `dependency_overrides` es global, asi que
        # tomar el cliente del autor y despues actuar como el de la empresa B
        # deja al "autor" siendo el otro. Ver el fixture `como`.
        ajena = como("ajeno").post(
            "/api/v1/obligations/",
            json={"code": f"CMT-{uuid.uuid4().hex[:8].upper()}", "title": "De la B"},
        ).json()
        try:
            r = _comentar(como("autor"), ajena["id"])
            assert r.status_code == 422, f"comento sobre la empresa B: {r.text[:150]}"
        finally:
            como("ajeno").delete(f"/api/v1/obligations/{ajena['id']}")

    def test_un_tipo_desconocido_no_se_comenta(self, como, obligacion) -> None:
        c = como("autor")
        r = c.post(
            "/api/v1/comentarios/",
            json={"entity_type": "invento", "entity_id": obligacion, "body": "hola"},
        )
        assert r.status_code == 422, r.text

    def test_un_comentario_vacio_no_es_un_comentario(self, como, obligacion) -> None:
        """El CHECK de la base exige lo mismo; comprobarlo antes da un 422 con
        explicacion en vez de un 500 con un error de Postgres."""
        c = como("autor")
        assert _comentar(c, obligacion, body="   ").status_code == 422
