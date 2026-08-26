"""El vinculo bidireccional Matriz Legal ↔ Obligaciones (RF-09, RF-14, #110).

## El gap que cierra

La issue estaba marcada `needs-decision` y el analisis decia que *"requiere
decidir como se vincula un `Articulo` con una `Obligation`, lo cual no esta
definido en ningun RF con suficiente detalle"*. Al medir aparecio que media
decision ya estaba tomada **en la base**: `obligations.article_compliance_id`
existe con su clave foranea desde `01_schema.sql`. Lo que no existia era nada
que la escribiera ni la leyera.

## Y algo que no estaba en el ticket

`POST /obligations/` aceptaba `article_compliance_id` sin mirarlo. Medido con
una sonda antes de tocar nada, desde la empresa B:

    un id inventado              -> 422
    un id real de la empresa A    -> 201   ← la obligacion quedo creada

No es solo un oraculo de existencia: la empresa B **colgo una obligacion de la
evaluacion de la empresa A**, y la fila se escribio. Las claves foraneas no
pasan por RLS, y aca no habia nada mas que las comprobara.

Las pruebas de `TestNoSePuedeApuntarAOtraEmpresa` son las que importan: crear un
vinculo se ve funcionando en pantalla, rechazarlo no.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.vinculo_matriz_obligacion import (
    PREFIJO,
    EvaluacionInvisible,
    contar_por_articulo,
    crear_obligacion_desde_articulo,
    desvincular,
    obligaciones_de_articulo,
    vincular,
)

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EMPRESA_B = uuid.UUID("a0000000-0000-0000-0000-000000000002")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


def _sesion(engine, tenant_id: uuid.UUID) -> Session:
    """Una sesion con la empresa declarada, como la arma la API."""
    conexion = engine.connect()
    s = Session(bind=conexion)
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )
    s.info["_conexion"] = conexion
    return s


@pytest.fixture
def engine():
    e = create_engine(URL)
    try:
        e.connect().close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    yield e
    e.dispose()


@pytest.fixture
def db(engine):
    """Empresa A. **Todo se deshace al terminar** — se escribe en tablas vivas."""
    s = _sesion(engine, EMPRESA_A)
    try:
        yield s
    finally:
        s.rollback()
        s.info["_conexion"].close()
        s.close()


@pytest.fixture
def evaluacion(db: Session):
    """Una evaluacion de articulo de la empresa A, con su norma y su planta."""
    fila = db.execute(
        text(
            "SELECT ac.id, ac.matrix_norm_id, ac.facility_id, ac.responsible_user_id "
            "FROM article_compliance ac WHERE ac.deleted_at IS NULL LIMIT 1"
        )
    ).first()
    if fila is None:  # pragma: no cover - seed vacio
        pytest.skip("El seed no tiene evaluaciones de articulo.")
    return {
        "id": fila[0],
        "matrix_norm_id": fila[1],
        "facility_id": fila[2],
        "responsible_user_id": fila[3],
    }


def _obligacion_suelta(db: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    """Una obligacion creada libremente, sin vinculo con la matriz."""
    return db.execute(
        text(
            "INSERT INTO obligations (tenant_id, code, title, status) "
            "VALUES (:t, :c, 'Obligacion libre', 'draft') RETURNING id"
        ),
        {"t": str(tenant_id), "c": f"LIBRE-{uuid.uuid4().hex[:8].upper()}"},
    ).scalar_one()


class TestGenerarDesdeUnArticulo:
    """Sentido matriz → obligacion (RF-09)."""

    def test_la_obligacion_queda_colgada_del_articulo(self, db, evaluacion) -> None:
        obl = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        assert obl.article_compliance_id == evaluacion["id"]

    def test_la_norma_y_la_planta_salen_de_la_evaluacion(self, db, evaluacion) -> None:
        """**La propiedad que evita una obligacion que se contradice.**

        Las tres claves foraneas son independientes: si la norma viniera del
        cuerpo, la obligacion podria declarar la norma B mientras cuelga de un
        articulo de la norma A, y la base no lo notaria.
        """
        obl = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        assert obl.matrix_norm_id == evaluacion["matrix_norm_id"]
        assert obl.facility_id == evaluacion["facility_id"]

    def test_hereda_el_responsable_del_articulo(self, db, evaluacion) -> None:
        """Quien responde por cumplir el articulo responde por la obligacion.

        Obligar a elegirlo de nuevo invita a dejarlo vacio, y una obligacion sin
        responsable no le llega a nadie.

        **La prueba pone el responsable antes de medirlo.** La primera version
        afirmaba contra el valor del seed, que es `NULL` en las seis
        evaluaciones: comparaba `None == None` y pasaba con la herencia
        borrada. La mutacion la delato.
        """
        persona = db.execute(
            text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
        ).scalar_one()
        db.execute(
            text("UPDATE article_compliance SET responsible_user_id = :u WHERE id = :i"),
            {"u": persona, "i": evaluacion["id"]},
        )

        obl = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        assert obl.owner_user_id == persona

    def test_un_responsable_explicito_gana_sobre_el_heredado(self, db, evaluacion) -> None:
        otro = db.execute(
            text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
        ).scalar_one()

        obl = crear_obligacion_desde_articulo(
            db,
            article_compliance_id=evaluacion["id"],
            tenant_id=EMPRESA_A,
            owner_user_id=otro,
        )

        assert obl.owner_user_id == otro

    def test_el_codigo_lo_pone_el_servidor_y_se_distingue(self, db, evaluacion) -> None:
        """Prefijo `MTZ`: se ve de un vistazo cual nacio de un requisito."""
        obl = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        assert obl.code.startswith(f"{PREFIJO}-")

    def test_dos_obligaciones_del_mismo_articulo_no_chocan(self, db, evaluacion) -> None:
        """`uq_obligations_tenant_code` es por empresa. Repetir codigo seria un 500.

        Y generar dos obligaciones del mismo articulo es legitimo: un requisito
        anual produce una por periodo.
        """
        a = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )
        b = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        assert a.code != b.code

    def test_el_codigo_no_se_repite_tras_un_borrado(self, db, evaluacion) -> None:
        """Con borrado logico la fila sigue ocupando su codigo."""
        a = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )
        db.execute(
            text("UPDATE obligations SET deleted_at = now() WHERE id = :i"), {"i": a.id}
        )

        b = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        assert b.code != a.code

    def test_un_hueco_en_la_numeracion_no_hace_repetir_un_codigo(
        self, db, evaluacion
    ) -> None:
        """**Contar filas no sirve, y por eso se mira el maximo.**

        La version anterior de esta prueba solo borraba y volvia a crear, y
        `len(usados) + 1` daba el mismo resultado que `max + 1` porque la
        numeracion iba densa: la mutacion sobrevivio. Lo que separa a las dos
        formulas es un **hueco**, y un hueco aparece en cuanto alguien escribe
        un codigo `MTZ-` a mano o se borra una fila de verdad.

        Con `len`, esto choca contra `uq_obligations_tenant_code` y sale un 500.
        """
        db.execute(
            text(
                "INSERT INTO obligations (tenant_id, code, title, status) "
                "VALUES (:t, 'MTZ-0099', 'escrita a mano', 'draft')"
            ),
            {"t": str(EMPRESA_A)},
        )

        obl = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        assert obl.code == "MTZ-0100", f"con un hueco salio {obl.code}"


class TestElOtroSentido:
    """Sentido obligacion → matriz (RF-14), y volver a soltarla."""

    def test_una_obligacion_libre_se_puede_atar_despues(self, db, evaluacion) -> None:
        from app.models.obligations import Obligation

        oid = _obligacion_suelta(db, EMPRESA_A)
        obl = db.get(Obligation, oid)

        vincular(db, obligacion=obl, article_compliance_id=evaluacion["id"])

        assert obl.article_compliance_id == evaluacion["id"]
        assert obl.matrix_norm_id == evaluacion["matrix_norm_id"]

    def test_desvincular_no_borra_la_obligacion(self, db, evaluacion) -> None:
        """Soltar el vinculo no es deshacer: la obligacion sigue venciendo."""
        obl = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        desvincular(db, obligacion=obl)

        assert obl.article_compliance_id is None
        assert obl.matrix_norm_id is None
        assert obl.deleted_at is None
        assert db.execute(
            text("SELECT count(*) FROM obligations WHERE id = :i"), {"i": obl.id}
        ).scalar_one() == 1

    def test_desvincular_conserva_la_planta(self, db, evaluacion) -> None:
        """La planta sigue siendo la planta aunque el vinculo desaparezca."""
        obl = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )
        planta = obl.facility_id

        desvincular(db, obligacion=obl)

        assert obl.facility_id == planta


class TestLeerDesdeLaMatriz:
    """El sentido de lectura que hace util el vinculo en pantalla."""

    def test_lista_las_obligaciones_del_articulo(self, db, evaluacion) -> None:
        a = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )
        b = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        ids = {o.id for o in obligaciones_de_articulo(db, evaluacion["id"])}

        assert {a.id, b.id} <= ids

    def test_una_obligacion_borrada_no_aparece(self, db, evaluacion) -> None:
        obl = crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )
        db.execute(
            text("UPDATE obligations SET deleted_at = now() WHERE id = :i"), {"i": obl.id}
        )

        assert obl.id not in {o.id for o in obligaciones_de_articulo(db, evaluacion["id"])}

    def test_contar_por_articulo_no_pregunta_uno_por_uno(self, db, evaluacion) -> None:
        """El DS 40 tiene 210 articulos: preguntar por cada uno son 210 viajes."""
        crear_obligacion_desde_articulo(
            db, article_compliance_id=evaluacion["id"], tenant_id=EMPRESA_A
        )

        cuenta = contar_por_articulo(db, [evaluacion["id"]])

        assert cuenta[evaluacion["id"]] >= 1

    def test_contar_sin_ids_no_consulta_nada(self, db) -> None:
        assert contar_por_articulo(db, []) == {}


class TestNoSePuedeApuntarAOtraEmpresa:
    """**Las tres negaciones, y son las que importan.**

    Vincular se ve funcionando; rechazar un vinculo ajeno no se ve. Un fallo
    aca deja una obligacion colgada de la evaluacion de otra empresa, y nada en
    la pantalla lo delata.
    """

    def test_un_articulo_inventado_no_genera_nada(self, db) -> None:
        with pytest.raises(EvaluacionInvisible):
            crear_obligacion_desde_articulo(
                db, article_compliance_id=uuid.uuid4(), tenant_id=EMPRESA_A
            )

    def test_un_articulo_de_otra_empresa_tampoco(self, engine, db, evaluacion) -> None:
        """El caso medido: antes daba **201** y escribia la fila."""
        otra = _sesion(engine, EMPRESA_B)
        try:
            with pytest.raises(EvaluacionInvisible):
                crear_obligacion_desde_articulo(
                    db=otra,
                    article_compliance_id=evaluacion["id"],
                    tenant_id=EMPRESA_B,
                )
        finally:
            otra.rollback()
            otra.info["_conexion"].close()
            otra.close()

    def test_inventado_y_ajeno_fallan_IGUAL(self, engine, db, evaluacion) -> None:
        """**La propiedad que cierra el oraculo de existencia.**

        Si "no existe" y "existe pero es de otro" dieran errores distintos,
        quien prueba identificadores al azar podria enumerar filas ajenas sin
        verlas nunca. Por eso se comparan los dos mensajes, no solo el tipo.
        """
        otra = _sesion(engine, EMPRESA_B)
        try:
            with pytest.raises(EvaluacionInvisible) as inventado:
                crear_obligacion_desde_articulo(
                    db=otra, article_compliance_id=uuid.uuid4(), tenant_id=EMPRESA_B
                )
            with pytest.raises(EvaluacionInvisible) as ajeno:
                crear_obligacion_desde_articulo(
                    db=otra,
                    article_compliance_id=evaluacion["id"],
                    tenant_id=EMPRESA_B,
                )

            assert str(inventado.value) == str(ajeno.value)
        finally:
            otra.rollback()
            otra.info["_conexion"].close()
            otra.close()

    def test_listar_las_obligaciones_de_un_articulo_ajeno_no_devuelve_vacio(
        self, engine, db, evaluacion
    ) -> None:
        """Un vacio tranquilo sobre un id ajeno se lee como "no tiene ninguna"."""
        otra = _sesion(engine, EMPRESA_B)
        try:
            with pytest.raises(EvaluacionInvisible):
                obligaciones_de_articulo(otra, evaluacion["id"])
        finally:
            otra.rollback()
            otra.info["_conexion"].close()
            otra.close()

    def test_vincular_a_un_articulo_ajeno_no_toca_la_obligacion(
        self, engine, db, evaluacion
    ) -> None:
        """Y si falla, **no deja la fila a medio escribir**."""
        from app.models.obligations import Obligation

        otra = _sesion(engine, EMPRESA_B)
        try:
            oid = _obligacion_suelta(otra, EMPRESA_B)
            obl = otra.get(Obligation, oid)

            with pytest.raises(EvaluacionInvisible):
                vincular(otra, obligacion=obl, article_compliance_id=evaluacion["id"])

            assert obl.article_compliance_id is None
            assert obl.matrix_norm_id is None
        finally:
            otra.rollback()
            otra.info["_conexion"].close()
            otra.close()


# ── Y ahora por la API, que es por donde entra el dano ────────────────────
#
# Las pruebas de arriba ejercitan el servicio. **No cubren `validar_visible` en
# `POST /obligations/`**, que es un camino distinto: ahi el vinculo llega en el
# cuerpo y no pasa por el servicio.
#
# La distincion no es teorica en este repo: ya hubo una guarda probada en
# aislamiento que pasaba en verde **con el router sin protegerla**. Por eso
# estas van contra la aplicacion montada.

@pytest.fixture
def cliente(monkeypatch):
    """La API con el camino de desarrollo, para no necesitar Clerk."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import SessionLocal
    from app.main import app

    monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)

    original = SessionLocal.kw.get("bind")
    motor = create_engine(URL)
    SessionLocal.configure(bind=motor)
    try:
        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original)
        motor.dispose()


@pytest.fixture
def limpiar():
    """Borra lo que las pruebas de API dejaron confirmado.

    Estas si escriben de verdad —el endpoint hace `commit`— asi que el
    `rollback` de la sesion de prueba no alcanza.
    """
    codigos: list[str] = []
    yield codigos

    admin = create_engine(
        os.getenv(
            "DATABASE_ADMIN_URL",
            "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
        )
    )
    try:
        with admin.begin() as c:
            for codigo in codigos:
                c.execute(text("DELETE FROM obligations WHERE code = :c"), {"c": codigo})
    finally:
        admin.dispose()


class TestPorLaApi:
    def test_generar_desde_un_articulo_responde_201(
        self, cliente, evaluacion, limpiar
    ) -> None:
        r = cliente.post(
            f"/api/v1/compliance/article-compliance/{evaluacion['id']}/obligations",
            headers={"X-Tenant-Id": str(EMPRESA_A)},
            json={"title": "Declaracion anual"},
        )

        assert r.status_code == 201, r.text
        cuerpo = r.json()
        limpiar.append(cuerpo["code"])
        assert cuerpo["article_compliance_id"] == str(evaluacion["id"])
        assert cuerpo["matrix_norm_id"] == str(evaluacion["matrix_norm_id"])

    def test_el_articulo_de_otra_empresa_responde_422(self, cliente, evaluacion) -> None:
        """**El caso medido antes de escribir esto: respondia 201.**"""
        r = cliente.post(
            f"/api/v1/compliance/article-compliance/{evaluacion['id']}/obligations",
            headers={"X-Tenant-Id": str(EMPRESA_B)},
            json={"title": "sonda"},
        )

        assert r.status_code == 422, r.text

    def test_crear_una_obligacion_apuntando_a_otra_empresa_responde_422(
        self, cliente, evaluacion
    ) -> None:
        """El camino que tenia el agujero: `POST /obligations/` con el id en el cuerpo."""
        r = cliente.post(
            "/api/v1/obligations/",
            headers={"X-Tenant-Id": str(EMPRESA_B)},
            json={
                "code": f"SONDA-{uuid.uuid4().hex[:6].upper()}",
                "title": "sonda",
                "article_compliance_id": str(evaluacion["id"]),
            },
        )

        assert r.status_code == 422, r.text

    def test_inventado_y_ajeno_responden_LO_MISMO_por_la_api(
        self, cliente, evaluacion
    ) -> None:
        """Mismo codigo **y mismo cuerpo**: si difirieran, el oraculo seguiria abierto."""
        h = {"X-Tenant-Id": str(EMPRESA_B)}
        cuerpo = lambda ac: {  # noqa: E731
            "code": f"SONDA-{uuid.uuid4().hex[:6].upper()}",
            "title": "sonda",
            "article_compliance_id": str(ac),
        }

        inventado = cliente.post("/api/v1/obligations/", headers=h, json=cuerpo(uuid.uuid4()))
        ajeno = cliente.post("/api/v1/obligations/", headers=h, json=cuerpo(evaluacion["id"]))

        assert inventado.status_code == ajeno.status_code == 422
        assert inventado.json() == ajeno.json()

    def test_vincular_y_soltar_por_la_api(self, cliente, evaluacion, limpiar) -> None:
        h = {"X-Tenant-Id": str(EMPRESA_A)}
        codigo = f"LIBRE-{uuid.uuid4().hex[:6].upper()}"
        oid = cliente.post(
            "/api/v1/obligations/", headers=h, json={"code": codigo, "title": "libre"}
        ).json()["id"]
        limpiar.append(codigo)

        atada = cliente.put(
            f"/api/v1/obligations/{oid}/matrix-link",
            headers=h,
            json={"article_compliance_id": str(evaluacion["id"])},
        )
        assert atada.status_code == 200, atada.text
        assert atada.json()["article_compliance_id"] == str(evaluacion["id"])

        suelta = cliente.delete(f"/api/v1/obligations/{oid}/matrix-link", headers=h)
        assert suelta.status_code == 200, suelta.text
        assert suelta.json()["article_compliance_id"] is None
