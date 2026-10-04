"""Avisos al responsable de cada etapa del registro de mejora (RF-99, #40).

Van contra la base real, dentro de una transaccion que se deshace: lo que impide
el duplicado es el indice unico de `db/17`, no un `if`, y eso no se comprueba
con una sesion simulada.

Las fechas se arman **por calendario** con `hoy_de`, nunca sumando horas: es la
leccion de `test_hora_del_cron_de_avisos.py`.
"""
from __future__ import annotations

import os
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.audit import ImprovementStageEntry, Nonconformity
from app.models.notifications import Notification
from app.services import avisos_de_etapas as avisos
from app.services import etapas_de_mejora as etapas
from app.services.husos import hoy_de

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
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
    s = Session(bind=conexion)
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA_A)})
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


def _persona(db: Session) -> uuid.UUID:
    uid = db.execute(
        text("SELECT id FROM users WHERE deleted_at IS NULL AND status = 'active' LIMIT 1")
    ).scalar()
    if uid is None:  # pragma: no cover
        pytest.skip("la empresa no tiene usuarios activos")
    return uid


def _registro(db: Session) -> Nonconformity:
    nc = Nonconformity(
        tenant_id=EMPRESA_A,
        code=f"PRB-{uuid.uuid4().hex[:8].upper()}",
        title="[QA] Registro para medir avisos de etapa",
        description="creado por una prueba",
        severity="major",
        status="open",
    )
    db.add(nc)
    db.flush()
    etapas.sembrar_ciclo(db, nc, tenant_id=EMPRESA_A)
    return nc


def _etapa(db: Session, nc: Nonconformity, kind: str) -> ImprovementStageEntry:
    return db.scalars(
        select(ImprovementStageEntry).where(
            ImprovementStageEntry.nonconformity_id == nc.id,
            ImprovementStageEntry.kind == kind,
        )
    ).one()


def _avisos(db: Session, etapa: ImprovementStageEntry) -> list[Notification]:
    return [
        n
        for n in db.scalars(select(Notification).where(Notification.tenant_id == EMPRESA_A)).all()
        if (n.context or {}).get("stage_id") == str(etapa.id)
    ]


class TestAsignacion:
    def test_el_responsable_recibe_el_aviso_en_los_dos_canales(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "correccion")
        e.responsable_user_id = _persona(db)
        db.flush()

        avisos.generar(db, EMPRESA_A)

        recibidos = _avisos(db, e)
        assert sorted(n.channel for n in recibidos) == ["email", "in_app"]
        assert all(n.recipient_user_id == e.responsable_user_id for n in recibidos)
        assert all(n.context["motivo"] == "asignacion" for n in recibidos)

    def test_correr_dos_veces_no_duplica(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "correccion")
        e.responsable_user_id = _persona(db)
        db.flush()

        avisos.generar(db, EMPRESA_A)
        segunda = avisos.generar(db, EMPRESA_A)

        assert len(_avisos(db, e)) == 2, "la segunda corrida escribio otra vez"
        # Y lo informa como repetido, no como silencio: es lo que distingue
        # "ya estaba" de "no se genero".
        assert segunda.omitidos_por_repetidos >= 2

    def test_si_cambia_el_responsable_le_llega_a_la_persona_nueva(self, db) -> None:
        """La unicidad es por destinatario: la clave ya existe tras el primer
        aviso, y aun asi la persona nueva tiene que recibir el suyo."""
        personas = list(
            db.execute(
                text("SELECT id FROM users WHERE deleted_at IS NULL AND status = 'active' LIMIT 2")
            ).scalars()
        )
        if len(personas) < 2:  # pragma: no cover
            pytest.skip("hacen falta dos usuarios activos")
        nc = _registro(db)
        e = _etapa(db, nc, "correccion")
        e.responsable_user_id = personas[0]
        db.flush()
        avisos.generar(db, EMPRESA_A)

        e.responsable_user_id = personas[1]
        db.flush()
        avisos.generar(db, EMPRESA_A)

        destinatarios = {n.recipient_user_id for n in _avisos(db, e)}
        assert destinatarios == set(personas)

    def test_sin_responsable_no_hay_aviso_de_asignacion(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "correccion")
        avisos.generar(db, EMPRESA_A)
        assert _avisos(db, e) == []


class TestFechaLimite:
    def test_por_vencer_dentro_de_la_ventana(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "accion_correctiva")
        e.responsable_user_id = _persona(db)
        e.due_date = hoy_de(db, EMPRESA_A) + timedelta(days=3)
        db.flush()

        avisos.generar(db, EMPRESA_A, ventanas=(7, 3, 1))

        motivos = sorted({n.context["motivo"] for n in _avisos(db, e)})
        assert motivos == ["asignacion", "por_vencer"]

    def test_fuera_de_la_ventana_solo_la_asignacion(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "accion_correctiva")
        e.responsable_user_id = _persona(db)
        e.due_date = hoy_de(db, EMPRESA_A) + timedelta(days=5)
        db.flush()

        avisos.generar(db, EMPRESA_A, ventanas=(7, 3, 1))

        assert {n.context["motivo"] for n in _avisos(db, e)} == {"asignacion"}

    def test_vencida_avisa_una_sola_vez(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "seguimiento")
        e.responsable_user_id = _persona(db)
        e.due_date = hoy_de(db, EMPRESA_A) - timedelta(days=2)
        db.flush()

        avisos.generar(db, EMPRESA_A)
        avisos.generar(db, EMPRESA_A)

        vencidas = [n for n in _avisos(db, e) if n.context["motivo"] == "vencida"]
        assert len(vencidas) == 2, "uno por canal, y la segunda corrida no repite"

    def test_sin_responsable_se_escala_a_los_administradores(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "correccion")
        e.due_date = hoy_de(db, EMPRESA_A) + timedelta(days=1)
        db.flush()
        admins = set(avisos._administradores(db, EMPRESA_A))
        if not admins:  # pragma: no cover
            pytest.skip("la empresa no tiene administradores activos")

        r = avisos.generar(db, EMPRESA_A, ventanas=(1,))

        recibidos = _avisos(db, e)
        assert {n.recipient_user_id for n in recibidos} == admins
        assert all("no tiene responsable" in n.body for n in recibidos)
        assert r.escalados >= 1

    def test_sin_fecha_limite_no_se_inventa_un_vencimiento(self, db) -> None:
        """Hoy los plazos de la escala estan en NULL a proposito."""
        nc = _registro(db)
        e = _etapa(db, nc, "correccion")
        assert e.due_date is None
        avisos.generar(db, EMPRESA_A)
        assert all(n.context["motivo"] == "asignacion" for n in _avisos(db, e))


class TestLoQueNoSeAvisa:
    def test_una_etapa_completada(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "correccion")
        e.responsable_user_id = _persona(db)
        e.due_date = hoy_de(db, EMPRESA_A) - timedelta(days=1)
        db.flush()
        db.execute(
            text(
                "UPDATE improvement_stage_entries SET fecha_ejecucion = current_date, "
                "completada_en = now() WHERE id = :i"
            ),
            {"i": e.id},
        )
        db.expire_all()

        avisos.generar(db, EMPRESA_A)

        assert _avisos(db, e) == []

    def test_la_etapa_de_un_registro_cerrado(self, db) -> None:
        nc = _registro(db)
        e = _etapa(db, nc, "correccion")
        e.responsable_user_id = _persona(db)
        e.due_date = hoy_de(db, EMPRESA_A) - timedelta(days=1)
        db.flush()
        db.execute(
            text("UPDATE nonconformities SET status = 'closed', closed_at = now() WHERE id = :i"),
            {"i": nc.id},
        )
        db.expire_all()

        avisos.generar(db, EMPRESA_A)

        assert _avisos(db, e) == []

    def test_la_etapa_de_registro_nunca(self, db) -> None:
        """Nace completada: no es trabajo de nadie."""
        nc = _registro(db)
        avisos.generar(db, EMPRESA_A)
        assert _avisos(db, _etapa(db, nc, "registro")) == []


class TestElCronLasIncluye:
    def test_la_tarea_de_avisos_llama_al_generador_de_etapas(self) -> None:
        """Un generador sin llamador es el patron de `bcn.sincronizar()`."""
        from pathlib import Path

        fuente = Path(__file__).parents[1].joinpath("app", "tareas", "avisos.py").read_text(encoding="utf-8")
        assert "avisos_de_etapas.generar(db, tenant_id)" in fuente
