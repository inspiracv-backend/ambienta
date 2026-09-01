"""El cron diario de avisos, con RLS puesto (#119).

## El error que estas pruebas existen para cazar

La tarea recorre empresa por empresa **con el contexto de RLS declarado**, en
vez de correr una sola pasada como dueña de la base. Eso es lo correcto —RLS es
la unica barrera (CLAUDE.md §4)— pero tiene una trampa que no da ningun error:

`SET LOCAL` dura lo que dure la transaccion, y el despachador **confirma cada
aviso por separado**. Con el alcance por defecto, el primer commit deja la
sesion sin empresa declarada; a partir de ahi `tomar_uno` devuelve **cero
filas** y la tarea termina informando "nada que hacer" habiendo despachado uno
solo.

Falla cerrado, que es lo bueno. Falla **en silencio**, que es lo malo: el
informe dice 1 entregado y todo el resto sigue encolado sin que nadie se entere.
Por eso `test_despacha_MAS_DE_UNO_por_empresa` siembra dos y comprueba los dos.
No se puede comprobar mirando un solo aviso.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.deps import declarar, olvidar
from app.tareas.avisos import Informe, _empresas

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")

URL_APP = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def conexion():
    engine = create_engine(URL_APP)
    try:
        c = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    try:
        yield c
    finally:
        c.close()
        engine.dispose()


class TestElAlcanceDelContexto:
    """Lo que se pierde en el commit, medido."""

    def test_set_local_se_pierde_al_confirmar(self, conexion) -> None:
        """La causa del bug, fijada para que nadie la "simplifique" de vuelta."""
        db = Session(bind=conexion)
        try:
            declarar(db, EMPRESA_A)
            assert db.execute(
                text("SELECT current_setting('ambienta.tenant_id', true)")
            ).scalar() == str(EMPRESA_A)

            db.commit()

            assert not db.execute(
                text("SELECT current_setting('ambienta.tenant_id', true)")
            ).scalar(), "si esto empieza a sobrevivir al commit, `toda_la_sesion` sobra"
        finally:
            db.rollback()
            db.close()

    def test_toda_la_sesion_sobrevive_al_confirmar(self, conexion) -> None:
        db = Session(bind=conexion)
        try:
            declarar(db, EMPRESA_A, toda_la_sesion=True)
            db.commit()
            assert db.execute(
                text("SELECT current_setting('ambienta.tenant_id', true)")
            ).scalar() == str(EMPRESA_A), (
                "sin esto el despachador atiende un aviso por empresa y calla el resto"
            )
        finally:
            olvidar(db)
            db.rollback()
            db.close()

    def test_olvidar_deja_la_conexion_limpia(self, conexion) -> None:
        """Un ajuste de sesion sobrevive a la conexion cuando vuelve al pool.

        Sin `olvidar()`, la siguiente consulta que no declare contexto —el
        catalogo global, un health check— hereda la empresa de la ultima tarea.
        """
        db = Session(bind=conexion)
        try:
            declarar(db, EMPRESA_A, toda_la_sesion=True)
            db.commit()
            olvidar(db)
            db.commit()
            assert not db.execute(
                text("SELECT current_setting('ambienta.tenant_id', true)")
            ).scalar()
        finally:
            db.rollback()
            db.close()


class TestLaTarea:
    def test_despacha_MAS_DE_UNO_por_empresa(self, conexion) -> None:
        """La prueba que caza el bug del contexto perdido.

        Con **un** aviso pasaria igual con el error presente. Hacen falta dos.
        """
        from app.services import despacho

        db = Session(bind=conexion)
        creados: list[uuid.UUID] = []
        try:
            declarar(db, EMPRESA_A, toda_la_sesion=True)

            uid = db.execute(
                text(
                    "SELECT id FROM users WHERE deleted_at IS NULL AND status = 'active' "
                    "AND email IS NOT NULL LIMIT 1"
                )
            ).scalar()
            if uid is None:
                pytest.skip("El seed no tiene un usuario activo con correo")

            for i in range(3):
                nid = db.execute(
                    text(
                        "INSERT INTO notifications "
                        "(tenant_id, recipient_user_id, channel, subject, body, status, "
                        " scheduled_at, dedupe_key) "
                        "VALUES (:t, :u, 'in_app', :s, 'x', 'queued', now() - interval '1 minute', :k) "
                        "RETURNING id"
                    ),
                    {
                        "t": str(EMPRESA_A),
                        "u": uid,
                        "s": f"cron {i}",
                        "k": f"cron-prueba-{uuid.uuid4()}",
                    },
                ).scalar_one()
                creados.append(nid)
            db.commit()

            despacho.despachar(db, transporte=None, limite=50)

            entregados = db.execute(
                text(
                    "SELECT count(*) FROM notifications "
                    "WHERE id = ANY(:ids) AND status = 'delivered'"
                ),
                {"ids": creados},
            ).scalar()
            assert entregados == 3, (
                f"se entregaron {entregados} de 3. Si es 1, el contexto de RLS se "
                "perdio en el primer commit y el resto quedo invisible."
            )
        finally:
            if creados:
                db.rollback()
                declarar(db, EMPRESA_A, toda_la_sesion=True)
                db.execute(
                    text("DELETE FROM notifications WHERE id = ANY(:ids)"),
                    {"ids": creados},
                )
                db.commit()
            olvidar(db)
            db.close()

    def test_correr_entrega_TODAS_las_de_una_empresa(self, conexion) -> None:
        """La tarea completa, no solo el despachador.

        La prueba de arriba declara el contexto ella misma, asi que pasaria
        igual si `avisos.py` volviera a `declarar(db, tid)` sin
        `toda_la_sesion`. Esta corre `correr()` de verdad, que es donde vive esa
        decision. Comprobado revirtiendola: esta falla con 1 de 3 y la otra no.
        """
        from app.db import SessionLocal
        from app.tareas.avisos import correr

        try:
            with SessionLocal() as prueba:
                prueba.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover - host sin DATABASE_URL
            pytest.skip(
                "`SessionLocal` apunta al hostname de Docker. En CI y dentro del "
                f"contenedor funciona; aca no: {type(exc).__name__}"
            )

        db = Session(bind=conexion)
        creados: list[uuid.UUID] = []
        try:
            declarar(db, EMPRESA_A, toda_la_sesion=True)
            uid = db.execute(
                text(
                    "SELECT id FROM users WHERE deleted_at IS NULL AND status = 'active' "
                    "AND email IS NOT NULL LIMIT 1"
                )
            ).scalar()
            if uid is None:
                pytest.skip("El seed no tiene un usuario activo con correo")

            for i in range(3):
                creados.append(
                    db.execute(
                        text(
                            "INSERT INTO notifications "
                            "(tenant_id, recipient_user_id, channel, subject, body, "
                            " status, scheduled_at, dedupe_key) "
                            "VALUES (:t, :u, 'in_app', :s, 'x', 'queued', "
                            "        now() - interval '1 minute', :k) RETURNING id"
                        ),
                        {
                            "t": str(EMPRESA_A),
                            "u": uid,
                            "s": f"tarea {i}",
                            "k": f"tarea-prueba-{uuid.uuid4()}",
                        },
                    ).scalar_one()
                )
            db.commit()

            correr(transporte=None)

            entregados = db.execute(
                text(
                    "SELECT count(*) FROM notifications "
                    "WHERE id = ANY(:ids) AND status = 'delivered'"
                ),
                {"ids": creados},
            ).scalar()
            assert entregados == 3, (
                f"la tarea entrego {entregados} de 3. Con 1, el contexto de RLS se "
                "perdio en el primer commit."
            )
        finally:
            if creados:
                db.rollback()
                declarar(db, EMPRESA_A, toda_la_sesion=True)
                db.execute(
                    text("DELETE FROM notifications WHERE id = ANY(:ids)"),
                    {"ids": creados},
                )
                db.commit()
            olvidar(db)
            db.close()

    def test_lista_las_empresas_sin_declarar_contexto(self, conexion) -> None:
        """`tenants` no lleva `tenant_id`: se lee sin empresa declarada.

        Es el unico paso de la tarea que necesita ver todo, y por eso es el
        unico que no declara nada.
        """
        db = Session(bind=conexion)
        try:
            empresas = _empresas(db)
            assert len(empresas) >= 1
            assert EMPRESA_A in empresas
        finally:
            db.close()


class TestElInforme:
    def test_una_obligacion_sin_destinatario_hace_fallar_la_tarea(self) -> None:
        """Nadie va a notarlo solo: no hay error, simplemente no se avisa.

        Si el cron sale con 0 igual, esa obligacion queda sin cobertura para
        siempre y nadie revisa la salida de una tarea que nunca falla.
        """
        assert Informe(sin_destinatario=["OBL-001"]).hay_que_mirarlo()

    def test_un_aviso_rendido_hace_fallar_la_tarea(self) -> None:
        assert Informe(rendidos=1).hay_que_mirarlo()

    def test_una_cola_acumulada_hace_fallar_la_tarea(self) -> None:
        assert Informe(atrasados=12).hay_que_mirarlo()

    def test_una_corrida_normal_sale_con_cero(self) -> None:
        assert not Informe(empresas=2, creados=5, entregados=5).hay_que_mirarlo()

    def test_los_repetidos_NO_son_un_problema(self) -> None:
        """El cron corrio de nuevo y no duplico. Es lo esperado, no un fallo."""
        assert not Informe(empresas=1, repetidos=17).hay_que_mirarlo()

    def test_sin_proveedor_tampoco_hace_fallar(self) -> None:
        """Falta configuracion de correo, no fallo nada.

        Se vera en el resumen. Hacer fallar el cron por esto llenaria el log de
        alertas todos los dias hasta que alguien configure Resend, y una alerta
        que suena siempre deja de mirarse.
        """
        assert not Informe(empresas=1, sin_proveedor=8).hay_que_mirarlo()

    def test_el_resumen_menciona_lo_que_hay_que_mirar(self) -> None:
        texto = Informe(
            empresas=2, creados=3, sin_destinatario=["OBL-9"], atrasados=4
        ).resumen()
        assert "OBL-9" in texto
        assert "ATENCION" in texto
