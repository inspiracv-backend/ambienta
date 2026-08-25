"""Que el registro de actividades se escriba solo, comprobado de punta a punta.

**Estas pruebas van contra la API real y la base real.** No podrian ser de otra
forma: lo que se quiere fijar es que un `POST` cualquiera deje rastro sin que el
router haga nada, y eso solo se ve atravesando el router, la dependencia, el
CRUD, la ORM y el `flush`. Una prueba con la sesion simulada verificaria que el
observador funciona cuando alguien lo llama, que es precisamente lo que no
estaba en duda.

El caso que motiva todo esto: `audit_log` estuvo con **cero filas** mientras
existian `registrar()`, el endpoint para leerla y la rotacion mensual. Todo
listo menos lo unico que importaba. Nada fallaba.
"""
from __future__ import annotations

import os
import uuid
import warnings

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TENANT = "a0000000-0000-0000-0000-000000000001"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    sesion.execute(text("SET LOCAL ROLE ambienta_app"))
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


@pytest.fixture
def cliente(monkeypatch):
    """La API con el camino de desarrollo, para no necesitar Clerk.

    Lo unico que cambia respecto de produccion es de donde sale el tenant. El
    resto del recorrido —router, `get_tenant_db`, CRUD, ORM, `flush`— es
    identico, y es el recorrido que se quiere probar.
    """
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import SessionLocal
    from app.main import app

    # Se apaga Clerk **sobre el objeto ya construido**, no limpiando la cache
    # de `get_settings`: reconstruirlo relee la configuracion entera, y eso no
    # arregla lo de abajo.
    monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)

    # La aplicacion apunta por defecto a `postgres`, el nombre del contenedor,
    # que **desde el host no resuelve**: la prueba fallaba con un error de DNS
    # que se lee como si la base estuviera caida. Se reapunta la fabrica de
    # sesiones, no se crea una nueva: el observador esta enganchado a *esta*, y
    # una fabrica nueva correria sin auditoria — la prueba pasaria a verificar
    # nada.
    original = SessionLocal.kw.get("bind")
    motor = create_engine(URL)
    SessionLocal.configure(bind=motor)
    try:
        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original)
        motor.dispose()


def _instalacion(codigo: str) -> dict:
    return {
        "code": codigo,
        "name": f"Planta {codigo}",
        "facility_type": "plant",
        "address": "Av. Matta 1200",
    }


def _eventos(db: Session, entity_id: str) -> list[dict]:
    filas = db.execute(
        text(
            "SELECT action, entity_type, entity_id, before_data, after_data, metadata "
            "FROM audit_log WHERE entity_id = :e ORDER BY id"
        ),
        {"e": entity_id},
    ).all()
    return [
        {
            "action": f[0],
            "entity_type": f[1],
            "entity_id": str(f[2]),
            "antes": f[3],
            "despues": f[4],
            "meta": f[5],
        }
        for f in filas
    ]


def _cuantas(db: Session) -> int:
    """Cuantas filas hay en el registro, mirando lo ya confirmado.

    Hace `rollback` primero: la sesion de la prueba tiene su propia transaccion
    abierta y **no ve** lo que confirmo el request, que corre en otra. Sin esto
    el conteo siempre da lo mismo y la prueba pasa sin comprobar nada.
    """
    db.rollback()
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT}
    )
    return db.execute(text("SELECT count(*) FROM audit_log")).scalar_one()


@pytest.fixture
def limpiar(db):
    """Borra lo que la prueba creo. **Como dueno de la base, no como la API.**

    `ambienta_app` tiene revocados `UPDATE` y `DELETE` sobre `audit_log`, que es
    lo que hace inmutable al registro. Que la limpieza necesite otra conexion no
    es un estorbo: es la propiedad funcionando.
    """
    creados: list[str] = []
    yield creados

    admin = create_engine(
        os.getenv(
            "DATABASE_ADMIN_URL",
            "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
        )
    )
    try:
        with admin.begin() as c:
            for eid in creados:
                c.execute(
                    text("DELETE FROM audit_log WHERE entity_id = :e"), {"e": eid}
                )
                c.execute(text("DELETE FROM facilities WHERE id = :e"), {"e": eid})
    except Exception as exc:  # pragma: no cover - sin credenciales de dueno
        # **Se avisa, no se traga.** La primera version hacia `pass` con una
        # contrasena equivocada: las pruebas pasaban en verde y dejaban un
        # reguero de filas en `audit_log` — 113 antes de que alguien mirara. Un
        # fallo de limpieza no debe hundir la prueba, pero tiene que verse.
        warnings.warn(f"No se pudo limpiar lo que creo la prueba: {exc}", stacklevel=2)
    finally:
        admin.dispose()


class TestSeEscribeSolo:
    def test_un_post_deja_rastro_sin_que_el_router_lo_pida(
        self, cliente, db, limpiar
    ) -> None:
        """**La prueba que no existia y por eso la tabla estaba vacia.**

        Ningun router llama a `registrar()`. Si esto pasa, es porque el rastro
        lo deja el `flush`.
        """
        codigo = f"AUD-{uuid.uuid4().hex[:6].upper()}"
        r = cliente.post(
            "/api/v1/facilities/", headers={"X-Tenant-Id": TENANT}, json=_instalacion(codigo)
        )
        assert r.status_code == 201, r.text
        fid = r.json()["id"]
        limpiar.append(fid)

        eventos = _eventos(db, fid)
        assert [e["action"] for e in eventos] == ["create"]
        assert eventos[0]["entity_type"] == "facilities"
        assert eventos[0]["despues"]["code"] == codigo

    def test_la_creacion_dice_cual_fila_creo(self, cliente, db, limpiar) -> None:
        """`entity_id` relleno, no vacio.

        Salia `NULL`: el id lo genera Postgres y en `before_flush` todavia no
        existe. Un "se creo una instalacion" que no dice cual no permite
        reconstruir nada, y es justo el evento donde mas importa saberlo.
        """
        codigo = f"AUD-{uuid.uuid4().hex[:6].upper()}"
        fid = cliente.post(
            "/api/v1/facilities/", headers={"X-Tenant-Id": TENANT}, json=_instalacion(codigo)
        ).json()["id"]
        limpiar.append(fid)

        assert _eventos(db, fid)[0]["entity_id"] == fid

    def test_una_edicion_guarda_el_antes_y_el_despues(
        self, cliente, db, limpiar
    ) -> None:
        codigo = f"AUD-{uuid.uuid4().hex[:6].upper()}"
        h = {"X-Tenant-Id": TENANT}
        fid = cliente.post(
            "/api/v1/facilities/", headers=h, json=_instalacion(codigo)
        ).json()["id"]
        limpiar.append(fid)

        cliente.patch(f"/api/v1/facilities/{fid}", headers=h, json={"address": "Dorsal 400"})

        edicion = _eventos(db, fid)[1]
        assert edicion["action"] == "update"
        # **Solo el campo que cambio**, no la fila entera: lo que se audita es
        # el cambio, y una fila completa por edicion multiplica el tamano de la
        # tabla sin agregar informacion.
        assert edicion["antes"] == {"address": "Av. Matta 1200"}
        assert edicion["despues"] == {"address": "Dorsal 400"}

    def test_una_baja_se_registra_como_delete_y_no_como_update(
        self, cliente, db, limpiar
    ) -> None:
        """El borrado logico llega al flush como un `UPDATE` de `deleted_at`.

        Anotarlo como `update` escondería la baja entre las ediciones — y la
        baja es el evento que mas se busca en un registro de auditoria.
        """
        codigo = f"AUD-{uuid.uuid4().hex[:6].upper()}"
        h = {"X-Tenant-Id": TENANT}
        fid = cliente.post(
            "/api/v1/facilities/", headers=h, json=_instalacion(codigo)
        ).json()["id"]
        limpiar.append(fid)

        assert cliente.delete(f"/api/v1/facilities/{fid}", headers=h).status_code == 204

        assert [e["action"] for e in _eventos(db, fid)] == ["create", "delete"]

    def test_queda_de_donde_vino(self, cliente, db, limpiar) -> None:
        """La ruta y la IP. Sin eso, "se cambio la direccion" no se puede rastrear."""
        codigo = f"AUD-{uuid.uuid4().hex[:6].upper()}"
        fid = cliente.post(
            "/api/v1/facilities/", headers={"X-Tenant-Id": TENANT}, json=_instalacion(codigo)
        ).json()["id"]
        limpiar.append(fid)

        assert _eventos(db, fid)[0]["meta"]["ruta"] == "POST /api/v1/facilities/"


class TestLoQueNoSeRegistra:
    def test_guardar_sin_cambiar_nada_no_deja_fila(
        self, cliente, db, limpiar
    ) -> None:
        """La regla que pidio el negocio: *"si el user no mete datos, no sale log"*.

        No es cosmetica. El ruido es lo que despues hace que nadie encuentre el
        cambio que importa, y lo que engorda la tabla que justamente se quiere
        rotar todos los meses.
        """
        codigo = f"AUD-{uuid.uuid4().hex[:6].upper()}"
        h = {"X-Tenant-Id": TENANT}
        fid = cliente.post(
            "/api/v1/facilities/", headers=h, json=_instalacion(codigo)
        ).json()["id"]
        limpiar.append(fid)

        # Se manda el mismo valor que ya tiene, dos veces.
        cliente.patch(f"/api/v1/facilities/{fid}", headers=h, json={"address": "Av. Matta 1200"})
        cliente.patch(f"/api/v1/facilities/{fid}", headers=h, json={"address": "Av. Matta 1200"})

        assert [e["action"] for e in _eventos(db, fid)] == ["create"]

    def test_el_registro_no_se_registra_a_si_mismo(
        self, cliente, db, limpiar
    ) -> None:
        """Una escritura deja **una** fila, ni dos ni ninguna.

        Las otras pruebas filtran por `entity_id`, asi que verian una sola fila
        aunque el observador estuviera escribiendo tres. Esta cuenta el total.

        Lo que **no** demuestra, aunque lo parezca: que el filtro contra
        auto-auditarse sirva. Se probo quitandolo y el conteo sigue dando uno —
        las filas de auditoria entran a la sesion despues de la fotografia. El
        filtro es defensa por si eso cambia, y no esta cubierto.
        """
        antes = _cuantas(db)

        codigo = f"AUD-{uuid.uuid4().hex[:6].upper()}"
        fid = cliente.post(
            "/api/v1/facilities/", headers={"X-Tenant-Id": TENANT}, json=_instalacion(codigo)
        ).json()["id"]
        limpiar.append(fid)

        assert _cuantas(db) - antes == 1

    def test_leer_no_registra_nada(self, cliente, db, limpiar) -> None:
        """Un `GET` no es un evento.

        Si lo fuera, cada carga de pantalla escribiria en la tabla y el registro
        de cambios se volveria un registro de trafico — inservible para lo que
        se necesita, y varios ordenes de magnitud mas grande.
        """
        antes = db.execute(text("SELECT count(*) FROM audit_log")).scalar_one()

        cliente.get("/api/v1/facilities/", headers={"X-Tenant-Id": TENANT})
        cliente.get("/api/v1/departments/", headers={"X-Tenant-Id": TENANT})

        db.rollback()  # para ver lo que otras transacciones ya confirmaron
        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT}
        )
        assert db.execute(text("SELECT count(*) FROM audit_log")).scalar_one() == antes


class TestElRegistroEsInmutable:
    def test_la_api_no_puede_editar_ni_borrar_lo_ya_escrito(self, db) -> None:
        """La garantia esta en la base, no en la buena conducta del codigo.

        `ambienta_app` tiene `INSERT` y `SELECT` y nada mas. Un endpoint mal
        escrito —o comprometido— no puede tapar sus huellas.
        """
        for sentencia in (
            "UPDATE audit_log SET action = 'create'",
            "DELETE FROM audit_log",
        ):
            with pytest.raises(Exception) as exc:
                db.execute(text(sentencia))
                db.flush()
            assert "permission denied" in str(exc.value).lower()
            db.rollback()
            db.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT}
            )
