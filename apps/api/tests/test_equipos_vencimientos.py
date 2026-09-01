"""Equipos regulados: quien puede operarlos hoy y que hay que renovar (#47, #48).

## Las dos preguntas, que no son la misma

- **#48 — ¿alguien puede operar este equipo hoy?** Si la respuesta es no, la
  empresa esta operando fuera de norma **ahora mismo**: es un incumplimiento y
  va a `/incumplimientos`, junto a los articulos y las declaraciones vencidas.
- **#47 — ¿que vence pronto?** Todavia no hay incumplimiento; hay tiempo para
  renovar. Es una alerta, no un hallazgo.

Mezclarlas haria que lo urgente y lo previsible se leyeran igual.

## Tres decisiones que estas pruebas fijan

1. **Una certificacion sin fecha de vencimiento cuenta como vigente.** No es lo
   mismo "vencio" que "nadie anoto cuando vence": acusar a la empresa de operar
   con una certificacion vencida por un campo que falta seria una afirmacion
   falsa, y el arreglo de las dos cosas es distinto.
2. **Solo cuentan los equipos en operacion.** Uno detenido o dado de baja no
   necesita operador habilitado, y contarlo llenaria la lista de incumplimientos
   con maquinas que nadie usa — la forma mas rapida de que se deje de mirar.
3. **Lo ya vencido va en la lista de "por vencer".** Una lista que lo deja
   fuera es la unica que alguien mira, y esconde justo lo urgente.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.iso14001 import EquipmentOperator, RegulatedEquipment
from app.models.organization import Department, Facility, User
from app.services import iso14001 as svc

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
HOY = date(2026, 6, 15)


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    s = Session(bind=conexion)
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA_A)}
    )
    # Los equipos del seed harian que las afirmaciones dependieran de lo que
    # sembro alguien mas. Se apartan; la transaccion se deshace igual.
    s.execute(
        text("UPDATE regulated_equipment SET status = 'stopped' WHERE tenant_id = :t"),
        {"t": str(EMPRESA_A)},
    )
    s.expire_all()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


def _planta(db: Session) -> uuid.UUID:
    fila = db.scalars(
        select(Facility).where(
            Facility.tenant_id == EMPRESA_A, Facility.deleted_at.is_(None)
        )
    ).first()
    if fila is None:
        pytest.skip("El seed no dejo plantas en esta empresa")
    return fila.id


def _persona(db: Session) -> uuid.UUID:
    depto = db.scalars(
        select(Department).where(
            Department.tenant_id == EMPRESA_A, Department.deleted_at.is_(None)
        )
    ).first()
    if depto is None:
        pytest.skip("El seed no dejo departamentos")
    fila = User(
        tenant_id=EMPRESA_A,
        department_id=depto.id,
        email=f"{uuid.uuid4().hex[:12]}@prueba.cl",
        full_name="Operadora de prueba",
        user_type="internal",
        status="active",
    )
    db.add(fila)
    db.flush()
    return fila.id


def _equipo(
    db: Session, nombre: str = "Caldera 1", *, status: str = "operational",
    inscripcion: date | None = None,
) -> RegulatedEquipment:
    fila = RegulatedEquipment(
        tenant_id=EMPRESA_A,
        facility_id=_planta(db),
        name=nombre,
        equipment_type="caldera",
        status=status,
        registration_expires_at=inscripcion,
    )
    db.add(fila)
    db.flush()
    return fila


def _operador(
    db: Session, equipo: RegulatedEquipment, vence: date | None
) -> EquipmentOperator:
    fila = EquipmentOperator(
        tenant_id=EMPRESA_A,
        equipment_id=equipo.id,
        user_id=_persona(db),
        certification_number=f"C-{uuid.uuid4().hex[:6]}",
        certification_expires_at=vence,
    )
    db.add(fila)
    db.flush()
    return fila


def _motivos(db: Session) -> dict[uuid.UUID, str]:
    return {
        h["equipment_id"]: h["motivo"]
        for h in svc.equipos_sin_operador_habilitado(db, EMPRESA_A, HOY)
    }


class TestQuienPuedeOperarHoy:
    def test_un_equipo_SIN_operadores_es_incumplimiento(self, db: Session) -> None:
        equipo = _equipo(db, "Sin nadie")

        assert _motivos(db).get(equipo.id) == "sin_operador"

    def test_con_la_certificacion_VENCIDA_tambien(self, db: Session) -> None:
        """Y con otro motivo, porque se arregla distinto.

        Sin operador se asigna a alguien; con la certificacion vencida se
        renueva. Un solo motivo obligaria a abrir cada equipo para saber cual.
        """
        equipo = _equipo(db, "Certificacion vieja")
        _operador(db, equipo, HOY - timedelta(days=1))

        assert _motivos(db).get(equipo.id) == "certificacion_vencida"

    def test_con_la_certificacion_VIGENTE_no_lo_es(self, db: Session) -> None:
        """La otra mitad: sin esto, la regla marcaria todos los equipos."""
        equipo = _equipo(db, "Todo en regla")
        _operador(db, equipo, HOY + timedelta(days=1))

        assert equipo.id not in _motivos(db)

    def test_venciendo_HOY_todavia_habilita(self, db: Session) -> None:
        """El borde: `>= hoy`. Una certificacion vence al terminar su ultimo
        dia, no al empezarlo — declarar incumplimiento esa manana seria acusar
        a la empresa de algo que todavia no pasa."""
        equipo = _equipo(db, "Vence hoy")
        _operador(db, equipo, HOY)

        assert equipo.id not in _motivos(db)

    def test_basta_UNO_habilitado_entre_varios(self, db: Session) -> None:
        """Con un operador vigente el equipo se puede operar, aunque a otros
        se les haya vencido. Exigir que todos esten al dia inventaria un
        incumplimiento donde no lo hay."""
        equipo = _equipo(db, "Uno al dia")
        _operador(db, equipo, HOY - timedelta(days=30))
        _operador(db, equipo, HOY + timedelta(days=30))

        assert equipo.id not in _motivos(db)

    def test_una_certificacion_SIN_FECHA_cuenta_como_vigente(
        self, db: Session
    ) -> None:
        """No es lo mismo "vencio" que "nadie anoto cuando vence".

        Tratar el campo vacio como vencido acusaria a la empresa de operar
        fuera de norma por un dato que falta, y el arreglo de las dos cosas es
        distinto: una se renueva, la otra se completa.
        """
        equipo = _equipo(db, "Sin fecha")
        _operador(db, equipo, None)

        assert equipo.id not in _motivos(db)

    def test_un_operador_BORRADO_no_habilita(self, db: Session) -> None:
        """Alguien retirado no puede seguir habilitando el equipo.

        Y el motivo que corresponde es **`sin_operador`**, no
        `certificacion_vencida`: la certificacion estaba vigente: lo que dejo
        de existir es la asignacion. El motivo tiene que describir lo que hay
        que arreglar, y aca hay que asignar a alguien, no renovar nada.
        """
        equipo = _equipo(db, "Operadora retirada")
        operador = _operador(db, equipo, HOY + timedelta(days=30))
        assert equipo.id not in _motivos(db), "la prueba no parte de un estado valido"

        db.execute(
            text("UPDATE equipment_operators SET deleted_at = now() WHERE user_id = :u"),
            {"u": str(operador.user_id)},
        )
        db.expire_all()

        assert _motivos(db).get(equipo.id) == "sin_operador"


class TestSoloLosEquiposEnOperacion:
    @pytest.mark.parametrize("estado", ["stopped", "decommissioned"])
    def test_uno_detenido_o_de_baja_no_es_incumplimiento(
        self, db: Session, estado: str
    ) -> None:
        """Nadie lo esta usando: no necesita operador habilitado de turno.

        Contarlos llenaria la lista de incumplimientos con maquinas apagadas,
        que es la forma mas rapida de que se deje de mirar.
        """
        equipo = _equipo(db, f"Apagado {estado}", status=estado)

        assert equipo.id not in _motivos(db)


class TestLoQueVence:
    def test_una_inscripcion_dentro_de_la_ventana_aparece(self, db: Session) -> None:
        equipo = _equipo(db, "Por renovar", inscripcion=HOY + timedelta(days=10))

        datos = svc.vencimientos_proximos(db, EMPRESA_A, dias=30, hoy=HOY)

        fila = next(e for e in datos["equipos"] if e["equipment_id"] == equipo.id)
        assert fila["dias_restantes"] == 10

    def test_una_MUY_lejana_no_aparece(self, db: Session) -> None:
        """Y esto es lo que impide que la ventana sea decorativa."""
        equipo = _equipo(db, "Lejana", inscripcion=HOY + timedelta(days=200))

        datos = svc.vencimientos_proximos(db, EMPRESA_A, dias=30, hoy=HOY)

        assert equipo.id not in [e["equipment_id"] for e in datos["equipos"]]

    def test_lo_YA_VENCIDO_viene_incluido_con_dias_negativos(
        self, db: Session
    ) -> None:
        """Una lista de "por vencer" que deja fuera lo vencido es la unica
        lista que alguien mira, y esconde justamente lo urgente."""
        equipo = _equipo(db, "Vencida hace rato", inscripcion=HOY - timedelta(days=45))

        datos = svc.vencimientos_proximos(db, EMPRESA_A, dias=30, hoy=HOY)

        fila = next(e for e in datos["equipos"] if e["equipment_id"] == equipo.id)
        assert fila["dias_restantes"] == -45

    def test_las_certificaciones_de_operadores_tambien(self, db: Session) -> None:
        equipo = _equipo(db, "Con operadora")
        operador = _operador(db, equipo, HOY + timedelta(days=5))

        datos = svc.vencimientos_proximos(db, EMPRESA_A, dias=30, hoy=HOY)

        fila = next(o for o in datos["operadores"] if o["user_id"] == operador.user_id)
        assert fila["dias_restantes"] == 5

    def test_un_equipo_DETENIDO_no_entra_en_los_vencimientos(
        self, db: Session
    ) -> None:
        """No necesita inscripcion vigente mientras no se use."""
        equipo = _equipo(
            db, "Detenido", status="stopped", inscripcion=HOY + timedelta(days=5)
        )

        datos = svc.vencimientos_proximos(db, EMPRESA_A, dias=30, hoy=HOY)

        assert equipo.id not in [e["equipment_id"] for e in datos["equipos"]]

    def test_sin_fecha_de_inscripcion_no_aparece(self, db: Session) -> None:
        """No hay nada que renovar, y listarlo como "vence en None" seria ruido."""
        equipo = _equipo(db, "Sin inscripcion", inscripcion=None)

        datos = svc.vencimientos_proximos(db, EMPRESA_A, dias=30, hoy=HOY)

        assert equipo.id not in [e["equipment_id"] for e in datos["equipos"]]

    def test_la_respuesta_dice_con_que_dia_se_calculo(self, db: Session) -> None:
        """Sin esto la pantalla tiene que suponerlo, y suponer mal desplaza
        todos los `dias_restantes` sin que nada lo advierta."""
        datos = svc.vencimientos_proximos(db, EMPRESA_A, dias=30, hoy=HOY)

        assert datos["hoy"] == HOY
        assert datos["dias"] == 30
