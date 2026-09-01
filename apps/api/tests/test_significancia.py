"""Significancia de aspectos ambientales — ISO 14001 §6.1.2 (#44, #49).

## Lo que habia antes

`services/iso14001.py` tenia cuatro defectos en treinta lineas, y **ninguno se
notaba porque nada lo llamaba** — el patron de `bcn.sincronizar()` y
`control_documental.py` por tercera vez:

| Defecto | Realidad |
|---|---|
| Leia `detection_score` | La columna no existe: `AttributeError` |
| Validaba `1..5` | El CHECK admite `1..10` |
| Escribia `'significant'` | El CHECK no lo admitia hasta `db/21` |
| Nunca escribia `total_score` | La columna existe para eso |

## Lo que estas pruebas protegen

1. **Que un aspecto sin evaluar quede `pending` y no `not_significant`.** La
   version anterior hacia `(score or 0)`, asi que lo que nadie miro salia como
   "no importa". En este modulo eso significa **no ponerle controles**.
2. **Que un requisito legal lo vuelva significativo por si solo**, aunque la
   magnitud sea baja.
3. **Que se guarde `total_score`**, que es lo que permite revisar el juicio sin
   recalcularlo.
4. **Que `/aspects/significant-untreated` sea alcanzable por HTTP.** Se declara
   antes que `/aspects/{aspect_id}` porque FastAPI resuelve por orden: al
   reves, responde 422 intentando leer el texto como UUID. Ya paso, y se midio.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.iso14001 import EnvironmentalAspect, RiskOpportunity
from app.models.organization import Facility
from app.services import iso14001 as svc

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
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA_A)}
    )
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


def _aspecto(db: Session, nombre: str = "Prueba") -> EnvironmentalAspect:
    fila = EnvironmentalAspect(
        tenant_id=EMPRESA_A,
        facility_id=_planta(db),
        activity=nombre,
        aspect=f"Aspecto de {nombre}",
        impact_type="Emision",
    )
    db.add(fila)
    db.flush()
    return fila


class TestSinPuntajesNoHayJuicio:
    def test_un_aspecto_sin_evaluar_queda_PENDIENTE(self, db: Session) -> None:
        """Y no "no significativo", que es lo que hacia el `or 0` de antes.

        La diferencia importa: un aspecto marcado no significativo **no recibe
        controles**. Decir eso de algo que nadie miro es el mismo error del
        `0 %` en las plantas sin evaluar del tablero, con peores consecuencias.
        """
        total, significancia, motivos = svc.calcular_significancia(None, None, None)

        assert significancia == "pending"
        assert total is None
        assert motivos and "sin juzgar" in motivos[0]

    @pytest.mark.parametrize(
        "frecuencia,severidad,legal",
        [(None, 5, 5), (5, None, 5), (5, 5, None)],
    )
    def test_con_UN_criterio_suelto_tampoco(
        self, db: Session, frecuencia, severidad, legal
    ) -> None:
        """Aceptar la evaluacion a medias la decidiria con los que faltan."""
        assert svc.calcular_significancia(frecuencia, severidad, legal)[1] == "pending"


class TestLosCriterios:
    def test_magnitud_alta_es_significativo(self, db: Session) -> None:
        total, significancia, motivos = svc.calcular_significancia(6, 6, 1)
        assert total == 36
        assert significancia == "significant"
        assert any("umbral" in m for m in motivos)

    def test_magnitud_baja_sin_ley_no_lo_es(self, db: Session) -> None:
        """La otra mitad: sin esto, la regla marcaria todo significativo."""
        total, significancia, _ = svc.calcular_significancia(2, 2, 1)
        assert total == 4
        assert significancia == "not_significant"

    def test_un_REQUISITO_LEGAL_lo_vuelve_significativo_solo(
        self, db: Session
    ) -> None:
        """Aunque ocurra poco y contamine poco.

        Es la regla conservadora y es practica corriente en 14001: el
        incumplimiento legal no depende de la frecuencia ni de la severidad.
        """
        total, significancia, motivos = svc.calcular_significancia(1, 1, 9)

        assert total == 1, "el total sigue siendo la magnitud"
        assert significancia == "significant"
        assert any("legal" in m for m in motivos)

    def test_justo_EN_el_umbral_cuenta(self, db: Session) -> None:
        """El borde se fija: `>=`, no `>`."""
        assert svc.calcular_significancia(5, 5, 1)[1] == "significant"

    def test_justo_por_DEBAJO_no(self, db: Session) -> None:
        """24 contra un umbral de 25. El par 24/25 fija el borde exacto:
        con `>` en vez de `>=`, la de arriba falla; con `>=` mal puesto en
        otro lado, esta."""
        total, significancia, _ = svc.calcular_significancia(4, 6, 1)
        assert total == 24
        assert significancia == "not_significant"

    @pytest.mark.parametrize("valor", [0, 11, -1, 100])
    def test_un_puntaje_fuera_de_1_a_10_se_rechaza(self, db: Session, valor) -> None:
        """El rango es el del CHECK de la tabla, no otro.

        La version anterior validaba `1..5` mientras la base admite `1..10`:
        media escala era inalcanzable desde la API.
        """
        with pytest.raises(svc.PuntajeFueraDeRango):
            svc.calcular_significancia(valor, 5, 5)

    def test_el_10_SI_se_acepta(self, db: Session) -> None:
        """Y esto es lo que impide "arreglar" el rango volviendo a 1..5."""
        assert svc.calcular_significancia(10, 10, 10)[0] == 100


class TestLoQueSeGuarda:
    def test_se_guardan_los_tres_puntajes_y_el_total(self, db: Session) -> None:
        """`total_score` permite revisar el juicio sin recalcularlo.

        Sin guardarlo, cambiar el umbral reescribiria la historia en silencio.
        """
        aspecto = _aspecto(db)
        svc.evaluar_aspecto(db, aspecto, 6, 6, 2)

        assert aspecto.frequency_score == 6
        assert aspecto.severity_score == 6
        assert aspecto.legal_score == 2
        assert aspecto.total_score == 36
        assert aspecto.significance == "significant"

    def test_la_base_ACEPTA_el_valor_que_se_escribe(self, db: Session) -> None:
        """La prueba que `db/21` hizo posible.

        Antes de esa migracion el CHECK de `significance` admitia
        `compliant | partial | non_compliant | pending` —los estados de
        cumplimiento, copiados— asi que escribir `significant` reventaba.
        """
        aspecto = _aspecto(db)
        svc.evaluar_aspecto(db, aspecto, 6, 6, 2)
        db.flush()

        guardado = db.execute(
            text("SELECT significance, total_score FROM environmental_aspects WHERE id = :i"),
            {"i": str(aspecto.id)},
        ).first()
        assert guardado[0] == "significant"
        assert guardado[1] == 36

    def test_reevaluar_a_la_baja_lo_devuelve_a_no_significativo(
        self, db: Session
    ) -> None:
        """Un juicio se puede corregir; si no, el primero seria definitivo."""
        aspecto = _aspecto(db)
        svc.evaluar_aspecto(db, aspecto, 8, 8, 1)
        assert aspecto.significance == "significant"

        svc.evaluar_aspecto(db, aspecto, 2, 2, 1)

        assert aspecto.significance == "not_significant"
        assert aspecto.total_score == 4


class TestLaTrazabilidadHaciaRiesgos:
    """§6.1.4: de los aspectos significativos salen riesgos (#49)."""

    def test_un_significativo_sin_riesgo_aparece_en_la_lista(
        self, db: Session
    ) -> None:
        """El hallazgo mas comun de una auditoria de 14001."""
        aspecto = _aspecto(db, "Sin tratar")
        svc.evaluar_aspecto(db, aspecto, 8, 8, 1)

        pendientes = svc.significativos_sin_riesgo(db, EMPRESA_A)

        assert aspecto.id in [a.id for a in pendientes]

    def test_al_enlazarlo_a_un_riesgo_DESAPARECE_de_la_lista(
        self, db: Session
    ) -> None:
        """Y esto es lo que impide que la lista sea "todos los significativos"."""
        aspecto = _aspecto(db, "Ya tratado")
        svc.evaluar_aspecto(db, aspecto, 8, 8, 1)
        assert aspecto.id in [a.id for a in svc.significativos_sin_riesgo(db, EMPRESA_A)]

        db.add(
            RiskOpportunity(
                tenant_id=EMPRESA_A,
                environmental_aspect_id=aspecto.id,
                code=f"R-{uuid.uuid4().hex[:6]}",
                entry_type="risk",
                description="Tratamiento del aspecto",
                origin="environmental_aspect",
            )
        )
        db.flush()

        assert aspecto.id not in [
            a.id for a in svc.significativos_sin_riesgo(db, EMPRESA_A)
        ]

    def test_un_aspecto_NO_significativo_no_aparece(self, db: Session) -> None:
        """La lista es de lo que hay que tratar, no de todo lo que existe."""
        aspecto = _aspecto(db, "Menor")
        svc.evaluar_aspecto(db, aspecto, 2, 2, 1)

        assert aspecto.id not in [
            a.id for a in svc.significativos_sin_riesgo(db, EMPRESA_A)
        ]

    def test_uno_sin_EVALUAR_tampoco_aparece(self, db: Session) -> None:
        """Todavia no se sabe si hay que tratarlo: falta evaluarlo."""
        aspecto = _aspecto(db, "Sin evaluar")

        assert aspecto.significance == "pending"
        assert aspecto.id not in [
            a.id for a in svc.significativos_sin_riesgo(db, EMPRESA_A)
        ]
