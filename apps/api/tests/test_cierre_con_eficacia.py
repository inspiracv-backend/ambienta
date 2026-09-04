"""Un registro de mejora no se cierra sin verificar que la accion funciono.

El spec de `gestion-mejoras` lo dice sin ambiguedad:

> El sistema SHALL exigir una verificacion de eficacia **afirmativa** antes de
> permitir el cierre de un registro.
>
> - Intento de cierre sin verificar -> el sistema lo impide
> - **Sin responder no es lo mismo que responder que no**

Sale de ISO 14001 §10.2.1 d): la organizacion tiene que revisar la eficacia de
la accion correctiva tomada. Cerrar sin eso es un hallazgo contra el propio
sistema de gestion — y lo levanta el auditor que viene a revisar como se
gestionan los hallazgos.

## Lo que se midio antes de escribir esto (4-sep, contra la base real)

| Situacion | Antes | Debe |
|---|---|---|
| Sin ningun plan de accion | **cierra** | no cierra |
| Con un plan cancelado | no cierra | **cierra** |
| Con un plan completado sin verificar | no cierra | no cierra |
| Con un plan verificado | cierra | cierra |

Las dos filas equivocadas van en direcciones opuestas y las dos son malas. La
primera es la grave: **una no conformidad sin un solo plan de accion se cerraba
sin que nadie verificara nada**, que es exactamente el caso que el requisito
existe para impedir.

La segunda es la molesta: un plan **cancelado** —o sea, trabajo que se decidio
no hacer— bloqueaba el cierre para siempre. Venia de que el servicio excluia
`["closed", "verified"]`, y **`closed` no es un estado que la base admita**: el
CHECK de `action_plans.status` son `draft, approved, in_progress, completed,
verified, cancelled`. Un valor escrito contra un esquema imaginado, que es la
trampa que CLAUDE.md documenta.

Y las dos se combinaban en algo peor: con planes no se podia cerrar porque no se
podia verificar —`verify` respondia 500 siempre, ver
`test_verificacion_de_eficacia.py`— y sin planes se cerraba sin verificar nada.
El modulo no servia en ninguna de las dos direcciones.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.audit import ActionPlan, Nonconformity
from app.routers.audits import close_nc

EMPRESA = uuid.UUID("a0000000-0000-0000-0000-000000000001")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        con = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(
            f"Sin base de datos disponible ({exc}). Esto NO comprueba el cierre: "
            "hace falta `docker compose up -d`."
        )
    trans = con.begin()
    s = Session(bind=con, join_transaction_mode="create_savepoint")
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA)}
    )
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        con.close()


def _registro(db: Session, titulo: str = "Registro de prueba") -> Nonconformity:
    nc = Nonconformity(
        tenant_id=EMPRESA,
        code=f"PRB-{uuid.uuid4().hex[:8].upper()}",
        title=titulo,
        description="creado por una prueba",
        severity="major",
        status="open",
    )
    db.add(nc)
    db.flush()
    return nc


def _plan(db: Session, nc: Nonconformity, estado: str) -> ActionPlan:
    plan = ActionPlan(
        tenant_id=EMPRESA,
        nonconformity_id=nc.id,
        title="Plan de prueba",
        objective="que deje de pasar",
        status=estado,
    )
    db.add(plan)
    db.flush()
    return plan


class TestNoSeCierraSinVerificar:
    def test_SIN_ningun_plan_de_accion_no_se_puede_cerrar(self, db) -> None:
        """**La afirmacion central**, y lo que antes se podia hacer.

        Un registro sin un solo plan de accion se cerraba con `closed_at`
        escrito y sin que nadie hubiera verificado nada. Para el sistema quedaba
        igual que uno tratado y verificado.
        """
        nc = _registro(db, "Sin ningun plan")

        with pytest.raises(HTTPException) as exc:
            close_nc(nc.id, closure_notes="cierro sin verificar", db=db)

        assert exc.value.status_code == 409
        assert "eficacia" in str(exc.value.detail).lower()

    def test_un_plan_COMPLETADO_no_alcanza(self, db) -> None:
        """Completar la accion y verificar que funciono son cosas distintas.

        §10.2.1 pide las dos. Confundirlas es cerrar cuando el trabajo se hizo,
        sin preguntarse si sirvio.
        """
        nc = _registro(db)
        _plan(db, nc, "completed")

        with pytest.raises(HTTPException) as exc:
            close_nc(nc.id, closure_notes="", db=db)

        assert exc.value.status_code == 409

    def test_un_plan_EN_CURSO_tampoco(self, db) -> None:
        nc = _registro(db)
        _plan(db, nc, "in_progress")

        with pytest.raises(HTTPException):
            close_nc(nc.id, closure_notes="", db=db)

    def test_el_mensaje_dice_QUE_falta_y_no_solo_que_no(self, db) -> None:
        """Un 409 mudo obliga a adivinar cual de las dos cosas falta: que el
        plan termine, o que alguien verifique que sirvio."""
        nc = _registro(db)
        _plan(db, nc, "in_progress")

        with pytest.raises(HTTPException) as exc:
            close_nc(nc.id, closure_notes="", db=db)

        detalle = str(exc.value.detail).lower()
        assert "verific" in detalle


class TestConVerificacionAfirmativaSiSeCierra:
    def test_un_plan_verificado_permite_cerrar(self, db) -> None:
        """La otra mitad: exigir verificacion no puede volverse impedir el cierre."""
        nc = _registro(db)
        _plan(db, nc, "verified")

        resultado = close_nc(nc.id, closure_notes="quedo resuelto", db=db)

        assert resultado.status == "closed"
        assert resultado.closed_at is not None
        assert resultado.closure_notes == "quedo resuelto"

    def test_basta_uno_verificado_si_los_demas_estan_cerrados_o_cancelados(
        self, db
    ) -> None:
        nc = _registro(db)
        _plan(db, nc, "verified")
        _plan(db, nc, "cancelled")

        assert close_nc(nc.id, closure_notes="", db=db).status == "closed"

    def test_un_plan_pendiente_junto_a_uno_verificado_sigue_bloqueando(
        self, db
    ) -> None:
        """Verificar uno no da por terminados los otros."""
        nc = _registro(db)
        _plan(db, nc, "verified")
        _plan(db, nc, "in_progress")

        with pytest.raises(HTTPException):
            close_nc(nc.id, closure_notes="", db=db)


class TestUnPlanCanceladoNoBloquea:
    """Cancelar es decidir que ese trabajo no se hace. No es trabajo pendiente.

    Antes bloqueaba el cierre **para siempre**, y no habia forma de salir: el
    unico estado que dejaba pasar era `verified`, y un plan cancelado no se
    puede verificar.
    """

    def test_un_plan_cancelado_no_cuenta_como_pendiente(self, db) -> None:
        nc = _registro(db)
        _plan(db, nc, "verified")
        _plan(db, nc, "cancelled")
        _plan(db, nc, "cancelled")

        assert close_nc(nc.id, closure_notes="", db=db).status == "closed"

    def test_pero_solo_cancelados_no_alcanza_para_cerrar(self, db) -> None:
        """Cancelar todos los planes no es haber verificado la eficacia: es no
        haber hecho nada. Sin esto, cancelar seria la via rapida para cerrar."""
        nc = _registro(db)
        _plan(db, nc, "cancelled")

        with pytest.raises(HTTPException) as exc:
            close_nc(nc.id, closure_notes="", db=db)

        assert exc.value.status_code == 409


class TestLosEstadosQueSeMiranExistenEnLaBase:
    """El servicio filtraba por `closed`, que el CHECK de la base no admite.

    Los estados validos son `draft, approved, in_progress, completed, verified,
    cancelled`. Un filtro sobre un valor que no existe no falla: simplemente no
    coincide nunca, y nadie se entera. Es la misma familia que el codigo que
    leia `compliance_answer` e `is_active`.
    """

    def test_todo_estado_que_el_servicio_nombra_existe_en_el_CHECK(self, db) -> None:
        from app.services import audits as svc

        admitidos = set(
            db.execute(
                text(
                    "SELECT unnest(enum_o_check) FROM ("
                    "  SELECT regexp_matches("
                    "    pg_get_constraintdef(oid),"
                    "    '''([a-z_]+)''::character varying', 'g'"
                    "  ) AS enum_o_check"
                    "  FROM pg_constraint"
                    "  WHERE conrelid = 'action_plans'::regclass"
                    "    AND conname = 'action_plans_status_check'"
                    ") s"
                )
            ).scalars()
        )

        assert admitidos, "no se pudo leer el CHECK de action_plans.status"
        desconocidos = set(svc.ESTADOS_QUE_NO_BLOQUEAN) - admitidos
        assert desconocidos == set(), (
            f"El servicio nombra estados que la base no admite: {desconocidos}. "
            f"Admitidos: {sorted(admitidos)}"
        )

    def test_y_el_estado_que_cierra_esta_entre_ellos(self, db) -> None:
        from app.services import audits as svc

        assert svc.ESTADO_VERIFICADO in svc.ESTADOS_QUE_NO_BLOQUEAN
