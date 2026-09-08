"""El buscador transversal (RF-114, #76).

## Que vigila

| regla | lo que evita |
|---|---|
| los acentos se ignoran | cero resultados sobre 13 de las 24 normas del catalogo |
| solo devuelve lo que se puede leer | un oraculo: enterarse de titulos que no se pueden abrir |
| el minimo se explica | una lista vacia que se lee como "no hay coincidencias" |
| el grupo cortado avisa | que alguien deje de buscar creyendo que eso es todo |

El de los acentos no es teorico: este repositorio ya lo sufrio con la BCN
—*"`emision` no encuentra `EMISION` con tilde: devuelve cero resultados y
ningun error"*— y los titulos del catalogo estan en mayuscula **con** tilde.
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
from app.services.buscador import (  # noqa: E402
    FUENTES,
    MINIMO,
    TOPE_POR_GRUPO,
    buscar,
    familia_de_fuente,
)

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


def _buscar(cliente, q: str):
    return cliente.get("/api/v1/buscar/", params={"q": q})


def _grupo(cuerpo: dict, tipo: str) -> dict | None:
    return next((g for g in cuerpo["grupos"] if g["tipo"] == tipo), None)


class TestLosAcentos:
    """La trampa que este repositorio ya pago una vez."""

    def test_hay_titulos_con_tilde_que_medir(self, cliente) -> None:
        """La premisa de la prueba siguiente, comprobada y no supuesta.

        Si el catalogo dejara de tener titulos acentuados, la prueba de abajo
        pasaria sin medir nada — el peor tipo de prueba verde.
        """
        with SessionLocal() as db:
            n = db.execute(
                text("SELECT count(*) FROM legal_norms WHERE title ~ '[ÁÉÍÓÚÑ]'")
            ).scalar()
        assert n and n > 0, (
            "ninguna norma del catalogo tiene tilde, asi que la prueba del "
            "acento no mediria nada. Correr `sincronizar-bcn`."
        )

    def test_buscar_sin_tilde_encuentra_lo_acentuado(self, cliente) -> None:
        """`emision` tiene que encontrar `EMISIÓN`.

        Con `ILIKE` —la opcion corta— esto devuelve **cero y ningun error**,
        que se lee como que esa norma no esta en el sistema. El stemmer de la
        configuracion `spanish` normaliza los acentos, asi que no hace falta
        `unaccent`.
        """
        # **Se busca una norma cuyo titulo NO contenga la palabra sin tilde.**
        #
        # La primera version de esta prueba solo exigia que el grupo
        # `legal_norm` no viniera vacio, y **sobrevivio a la mutacion**: al
        # cambiar FTS por `ILIKE` las diez pruebas seguian en verde, porque hay
        # otras normas con "emision" sin acento en el titulo. Afirmaba algo
        # cierto que no era lo que decia probar — el tipo de prueba que este
        # repositorio ya conoce (`toBe(0)` sin preguntar que significaba el
        # cero).
        with SessionLocal() as db:
            fila = db.execute(
                text(
                    "SELECT id, title FROM legal_norms "
                    "WHERE title ~ 'EMISI[ÓO]N' AND title ~ '[ÁÉÍÓÚ]' "
                    "  AND title !~* 'emision' "
                    "LIMIT 1"
                )
            ).first()
        if not fila:
            pytest.skip("el catalogo no tiene una norma de 'emision' solo acentuada")
        norma_id, titulo = str(fila[0]), fila[1]

        r = _buscar(cliente, "emision")
        assert r.status_code == 200, r.text
        normas = _grupo(r.json(), "legal_norm")
        encontradas = [c["id"] for c in (normas or {}).get("coincidencias", [])]
        assert norma_id in encontradas, (
            f"buscar 'emision' sin tilde no encontro {titulo!r}, que solo la "
            "contiene acentuada. Es el defecto de la BCN otra vez: cero "
            "resultados y ningun error, que se lee como que esa norma no esta."
        )


class TestLoQueNoSeDevuelve:
    def test_sin_permiso_sobre_un_tipo_no_aparece(self, cliente) -> None:
        """El buscador no puede ser un oraculo.

        Se mide en el servicio y no por HTTP porque el modo `X-Tenant-Id` no
        tiene permisos que filtrar — que es correcto y esta dicho en el
        docstring del endpoint. Lo que se prueba es la regla: con una familia
        fuera de la lista, sus registros no salen.
        """
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            todas = {familia_de_fuente(f) for f in FUENTES}

            con_todo = buscar(db, "residuo", familias_permitidas=todas)
            sin_normas = buscar(
                db, "residuo", familias_permitidas=todas - {"legal_matrix"}
            )

        tipos_con = {g.tipo for g in con_todo.grupos}
        tipos_sin = {g.tipo for g in sin_normas.grupos}
        if "legal_norm" not in tipos_con:
            pytest.skip("no hay normas que coincidan con 'residuo'")
        assert "legal_norm" not in tipos_sin, (
            "quitando `legal_matrix` de los permisos igual devolvio normas: el "
            "buscador revela titulos que esa persona no puede abrir"
        )

    def test_el_filtro_se_aplica_a_los_comentarios_por_su_registro(self) -> None:
        """El permiso de un comentario es el del registro comentado.

        Sin esto, alguien sin `audit.read` leeria en el buscador lo que se
        conversó sobre una auditoria.
        """
        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            autor = db.execute(
                text(
                    "SELECT id FROM users WHERE deleted_at IS NULL "
                    "ORDER BY created_at, id LIMIT 1"
                )
            ).scalar()
            oblig = db.execute(
                text("SELECT id FROM obligations WHERE deleted_at IS NULL LIMIT 1")
            ).scalar()
            if not (autor and oblig):
                pytest.skip("el seed no tiene con que montar el caso")

            marca = f"zeolita{uuid.uuid4().hex[:6]}"
            db.execute(
                text(
                    "INSERT INTO comments (tenant_id, entity_type, entity_id, "
                    "author_user_id, body) VALUES (:t,'obligation',:e,:a,:b)"
                ),
                {"t": EMPRESA_A, "e": oblig, "a": autor, "b": f"Sobre la {marca}"},
            )
            db.commit()

            try:
                declarar(db, EMPRESA_A)
                con = buscar(db, marca, familias_permitidas={"obligation"})
                sin = buscar(db, marca, familias_permitidas={"document"})

                assert any(g.tipo == "comment" for g in con.grupos), (
                    "con `obligation.read` no aparecio el comentario"
                )
                assert not any(g.tipo == "comment" for g in sin.grupos), (
                    "sin permiso sobre la obligacion igual aparecio su comentario"
                )
            finally:
                declarar(db, EMPRESA_A)
                db.execute(
                    text("DELETE FROM comments WHERE body LIKE :b"),
                    {"b": f"%{marca}%"},
                )
                db.commit()


class TestLoQueSeDice:
    def test_una_consulta_muy_corta_se_rechaza_explicando(self, cliente) -> None:
        """No una lista vacia: eso afirmaria que no hay coincidencias."""
        r = _buscar(cliente, "a")
        assert r.status_code == 422, r.text
        assert str(MINIMO) in r.json()["detail"], r.json()

    def test_avisa_que_no_mira_dentro_de_los_archivos(self, cliente) -> None:
        """Sin esto, quien busque una frase que esta en el PDF de un
        procedimiento concluye que ese procedimiento no la menciona."""
        cuerpo = _buscar(cliente, "residuo").json()
        assert cuerpo["advertencias"], "el buscador no declara sus limites"
        assert any(
            "archivos" in a for a in cuerpo["advertencias"]
        ), cuerpo["advertencias"]

    def test_sin_coincidencias_devuelve_grupos_vacios_sin_error(self, cliente) -> None:
        r = _buscar(cliente, f"nohaynadaasi{uuid.uuid4().hex[:8]}")
        assert r.status_code == 200, r.text
        assert r.json()["grupos"] == []
        # Las advertencias se declaran igual: no encontrar nada no cambia que
        # el buscador no mira dentro de los archivos.
        assert r.json()["advertencias"]

    def test_el_tope_por_grupo_avisa(self, monkeypatch) -> None:
        """Un grupo cortado en silencio hace que alguien deje de buscar.

        **El tope se baja a 1 en vez de sembrar once filas.** La primera
        version media el tope real contra el catalogo y se saltaba sola —solo
        5 normas coinciden con "decreto"—, o sea que la regla quedaba sin
        probar y la corrida se veia igual de verde. Bajarlo prueba el
        mecanismo, que es lo que puede romperse.
        """
        from app.services import buscador as mod

        monkeypatch.setattr(mod, "TOPE_POR_GRUPO", 1)

        with SessionLocal() as db:
            declarar(db, EMPRESA_A)
            cuantas = db.execute(
                text(
                    "SELECT count(*) FROM legal_norms "
                    "WHERE to_tsvector('spanish', title) @@ "
                    "plainto_tsquery('spanish','decreto')"
                )
            ).scalar()
            if not cuantas or cuantas < 2:
                pytest.skip("hacen falta dos normas con 'decreto' para medir el corte")

            resultado = mod.buscar(db, "decreto")

        normas = next((g for g in resultado.grupos if g.tipo == "legal_norm"), None)
        assert normas is not None
        assert len(normas.coincidencias) == 1
        assert normas.hay_mas is True, (
            "el grupo se corto y no lo dice: la lista afirma que eso es todo lo "
            "que hay, y en un buscador esa afirmacion hace que alguien deje de "
            "buscar"
        )


class TestLoQueSeEncuentra:
    def test_encuentra_una_obligacion_por_su_codigo(self, cliente) -> None:
        """El codigo va por `ILIKE` y no por FTS: no es una palabra que el
        stemmer sepa tratar, y quien lo escribe quiere coincidencia literal."""
        r = cliente.post(
            "/api/v1/obligations/",
            json={"code": f"BUSCA-{uuid.uuid4().hex[:6].upper()}", "title": "Prueba"},
        )
        assert r.status_code == 201, r.text
        creada = r.json()
        try:
            grupo = _grupo(_buscar(cliente, creada["code"]).json(), "obligation")
            assert grupo, "no se encontro por codigo exacto"
            assert creada["id"] in [c["id"] for c in grupo["coincidencias"]]
        finally:
            cliente.delete(f"/api/v1/obligations/{creada['id']}")

    def test_las_familias_del_buscador_existen_en_el_catalogo(self) -> None:
        """Una familia inventada deja ese tipo invisible para todos.

        Y en un buscador el sintoma es el peor posible: no un error, sino
        resultados que faltan sin que nadie sepa que faltan.
        """
        with SessionLocal() as db:
            existentes = {
                c for (c,) in db.execute(text("SELECT code FROM permissions")).all()
            }
        faltan = {
            f"{familia_de_fuente(f)}.read" for f in FUENTES
        } - existentes
        assert not faltan, f"familias sin permiso en el catalogo: {sorted(faltan)}"
