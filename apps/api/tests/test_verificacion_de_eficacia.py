"""Verificar la eficacia de un plan de accion, y quien lo hizo.

## El defecto que esto cierra

`POST /audits/action-plans/{id}/verify` **respondia 500 en el 100 % de los
casos**. El router le pasaba al servicio el `tenant_id` donde este espera el id
de quien verifica:

    obj = verify_action_plan(db, plan_id, tenant_id, success)
                                          ^^^^^^^^^ el servicio lo escribe
                                                    en `verified_by`

Y `action_plans.verified_by` tiene clave foranea contra `users`, asi que el
`UPDATE` violaba `fk_ap_verifiedby`. Medido el 4-sep contra la base real:

    IntegrityError: insert or update on table "action_plans" violates foreign
    key constraint "fk_ap_verifiedby"
    DETAIL: Key is not present in table "users".

Nadie se entero por dos razones que se combinan: `audits.py` tiene **30
operaciones y no tenia una sola prueba que llamara a sus endpoints**, y
verificar la eficacia es el ultimo paso de un ciclo largo — el que se ejecuta
semanas despues de abrir el hallazgo.

Y era peor de lo que parece por separado: sin este endpoint no se puede dejar un
plan en `verified`, y **sin un plan verificado no se puede cerrar el registro**
(ver `test_cierre_con_eficacia.py`). Con planes no se podia cerrar porque no se
podia verificar; sin planes se cerraba sin verificar nada. El modulo no servia
en ninguna de las dos direcciones.

## Por que el verificador no se toma del primer administrador

Mismo criterio que aprobar un documento. Ante una auditoria la pregunta no es si
se verifico, es **quien** — y escribir a alguien que no lo hizo es peor que no
escribir nada. Sin sesion identificada responde 409.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.audit import ActionPlan, Nonconformity
from app.models.organization import User
from app.routers.audits import verify_plan

EMPRESA = uuid.UUID("a0000000-0000-0000-0000-000000000001")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


class SesionDe:
    """Lo que `get_current_user` entrega: el `sub` del token de Clerk."""

    def __init__(self, clerk_id: str | None) -> None:
        self.user_id = clerk_id
        self.tenant_id = str(EMPRESA)


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        con = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(
            f"Sin base de datos disponible ({exc}). Esto NO comprueba la "
            "verificacion de eficacia: hace falta `docker compose up -d`."
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


@pytest.fixture
def persona(db: Session) -> User:
    """Alguien de la empresa, con `clerk_id`, que pueda firmar la verificacion."""
    fila = db.scalars(
        select(User).where(User.tenant_id == EMPRESA, User.deleted_at.is_(None))
    ).first()
    assert fila is not None, "el seed tiene usuarios en esta empresa"
    fila.clerk_id = f"user_prueba_{uuid.uuid4().hex[:12]}"
    db.flush()
    return fila


@pytest.fixture
def plan(db: Session) -> ActionPlan:
    nc = Nonconformity(
        tenant_id=EMPRESA,
        code=f"PRB-{uuid.uuid4().hex[:8].upper()}",
        title="Registro de prueba",
        description="creado por una prueba",
        severity="major",
        status="open",
    )
    db.add(nc)
    db.flush()
    ap = ActionPlan(
        tenant_id=EMPRESA,
        nonconformity_id=nc.id,
        title="Plan de prueba",
        objective="que deje de pasar",
        status="in_progress",
    )
    db.add(ap)
    db.flush()
    return ap


class TestVerificarFunciona:
    def test_verificar_con_exito_deja_el_plan_verificado(self, db, plan, persona) -> None:
        """**Antes esto reventaba con una violacion de clave foranea.**"""
        resultado = verify_plan(
            plan.id, success=True, db=db, usuario=SesionDe(persona.clerk_id)
        )

        assert resultado.status == "verified"
        assert resultado.verified_at is not None

    def test_queda_escrito_QUIEN_verifico_y_es_una_persona(
        self, db, plan, persona
    ) -> None:
        """La regresion exacta: antes se escribia el `tenant_id` de la empresa.

        No es un detalle de tipos. `verified_by` es lo que un auditor lee para
        saber quien firmo, y una empresa no firma nada.
        """
        resultado = verify_plan(
            plan.id, success=True, db=db, usuario=SesionDe(persona.clerk_id)
        )

        assert resultado.verified_by == persona.id
        assert resultado.verified_by != EMPRESA

    def test_verificar_que_NO_funciono_devuelve_el_plan_al_trabajo(
        self, db, plan, persona
    ) -> None:
        """El spec: «la verificacion concluye que la accion no funciono ->
        el registro vuelve a la etapa de accion correctiva»."""
        resultado = verify_plan(
            plan.id, success=False, db=db, usuario=SesionDe(persona.clerk_id)
        )

        assert resultado.status == "in_progress"

    def test_una_verificacion_negativa_no_deja_firma_de_verificado(
        self, db, plan, persona
    ) -> None:
        """«Sin responder no es lo mismo que responder que no», y responder que
        no tampoco es haber verificado con exito: no puede quedar `verified_at`
        escrito, o el cierre lo tomaria como afirmativa."""
        resultado = verify_plan(
            plan.id, success=False, db=db, usuario=SesionDe(persona.clerk_id)
        )

        assert resultado.verified_at is None


class TestSinSesionIdentificadaNoSeFirma:
    def test_sin_usuario_responde_409_y_no_inventa_un_verificador(
        self, db, plan
    ) -> None:
        with pytest.raises(HTTPException) as exc:
            verify_plan(plan.id, success=True, db=db, usuario=SesionDe(None))

        assert exc.value.status_code == 409
        assert "identificada" in str(exc.value.detail)

    def test_un_clerk_id_que_no_esta_en_la_empresa_tampoco(self, db, plan) -> None:
        """Sesion valida de Clerk cuya persona no existe en esta base. Es el
        caso real de alguien recien dado de alta por SSO."""
        with pytest.raises(HTTPException) as exc:
            verify_plan(
                plan.id, success=True, db=db, usuario=SesionDe("user_no_existe_aca")
            )

        assert exc.value.status_code == 409

    def test_y_el_plan_no_se_toca(self, db, plan) -> None:
        """Negarse tiene que dejar todo como estaba."""
        antes = plan.status

        with pytest.raises(HTTPException):
            verify_plan(plan.id, success=True, db=db, usuario=SesionDe(None))

        db.refresh(plan)
        assert plan.status == antes
        assert plan.verified_by is None


class TestElCicloCompleto:
    def test_verificar_y_despues_cerrar(self, db, plan, persona) -> None:
        """Las dos mitades juntas, que es lo que ninguna prueba hacia.

        Sin el arreglo de `verify` este recorrido es imposible: el registro no
        se puede cerrar porque su unico plan no puede llegar a `verified`.
        """
        from app.routers.audits import close_nc

        verify_plan(plan.id, success=True, db=db, usuario=SesionDe(persona.clerk_id))
        cerrado = close_nc(plan.nonconformity_id, closure_notes="listo", db=db)

        assert cerrado.status == "closed"
        assert cerrado.closed_at is not None


class TestUnaVerificacionNegativaBorraLaFirmaAnterior:
    """Un plan que se verifico, se reabrio y volvio a fallar no puede conservar
    la firma que decia que funcionaba.

    No lo aprovecha el cierre —mira `status`, no la fecha— pero es lo que se ve
    en la ficha y lo que se exporta a un auditor: una firma afirmativa sobre un
    trabajo que se reabrio porque no sirvio.
    """

    def test_la_firma_no_sobrevive_a_una_verificacion_negativa(
        self, db, plan, persona
    ) -> None:
        verify_plan(plan.id, success=True, db=db, usuario=SesionDe(persona.clerk_id))
        db.refresh(plan)
        assert plan.verified_at is not None  # linea base: quedo firmado

        resultado = verify_plan(
            plan.id, success=False, db=db, usuario=SesionDe(persona.clerk_id)
        )

        assert resultado.status == "in_progress"
        assert resultado.verified_at is None
        assert resultado.verified_by is None

    def test_y_entonces_ya_no_se_puede_cerrar(self, db, plan, persona) -> None:
        """La consecuencia que importa: reabrir de verdad reabre."""
        from app.routers.audits import close_nc

        verify_plan(plan.id, success=True, db=db, usuario=SesionDe(persona.clerk_id))
        verify_plan(plan.id, success=False, db=db, usuario=SesionDe(persona.clerk_id))

        with pytest.raises(HTTPException) as exc:
            close_nc(plan.nonconformity_id, closure_notes="", db=db)

        assert exc.value.status_code == 409
