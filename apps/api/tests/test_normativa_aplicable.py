"""El calculo de que normas le corresponden a una empresa (RF-19).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

La propiedad que mas importa no es "devuelve las normas del sector" sino
**distinguir tres situaciones que se ven iguales**:

- `sin_perfil`: la empresa no declaro su sector -> falta un dato de ella
- `sector_sin_clasificar`: nadie clasifico normas para ese sector -> falta
  trabajo nuestro
- `con_normativa`: hay resultado

Las tres podrian devolver una lista vacia. **Ninguna significa que la empresa no
tenga obligaciones**, y confundirlas le haria creer que esta en regla.

Necesitan base con el esquema cargado. Sin ella se saltan.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.normativa_aplicable import NIVELES_OBLIGATORIOS, calcular

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
TENANT = "a0000000-0000-0000-0000-000000000001"


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
        # Rollback siempre: estas pruebas cambian el sector de la empresa y
        # clasifican normas. Dejarlo cambiaria el resultado de las siguientes.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _sector(db: Session, code: str = "C") -> int:
    sid = db.execute(
        text("SELECT id FROM sectors WHERE code = :c"), {"c": code}
    ).scalar()
    if sid is None:
        pytest.skip(f"Sin el sector {code} sembrado")
    return sid


def _una_norma(db: Session) -> uuid.UUID:
    nid = db.execute(
        text("SELECT id FROM legal_norms WHERE deleted_at IS NULL LIMIT 1")
    ).scalar()
    if nid is None:
        pytest.skip("Sin normas en el catalogo")
    return nid


def _perfilar(db: Session, sector_id: int | None) -> None:
    db.execute(
        text("UPDATE tenants SET sector_id = :s WHERE id = :t"),
        {"s": sector_id, "t": TENANT},
    )


def _clasificar(db: Session, norm_id, sector_id: int, nivel: str) -> None:
    db.execute(
        text(
            "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale) "
            "VALUES (:n, :s, :l, 'prueba') "
            "ON CONFLICT (norm_id, sector_id) DO UPDATE SET applicability_level = :l"
        ),
        {"n": norm_id, "s": sector_id, "l": nivel},
    )


def _limpiar(db: Session, sector_id: int) -> None:
    db.execute(
        text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sector_id}
    )


class TestLosTresEstados:
    """Lo que distingue este calculo de devolver una lista pelada."""

    def test_sin_sector_declarado_dice_sin_perfil(self, db: Session) -> None:
        _perfilar(db, None)

        r = calcular(db, uuid.UUID(TENANT))

        assert r.estado == "sin_perfil"
        assert r.total == 0

    def test_sector_sin_normas_clasificadas_lo_dice(self, db: Session) -> None:
        """El caso peligroso: 0 normas que NO significa "sin obligaciones".

        Si esto devolviera solo una lista vacia, la pantalla mostraria lo mismo
        que para una empresa realmente en regla.
        """
        sid = _sector(db)
        _perfilar(db, sid)
        _limpiar(db, sid)

        r = calcular(db, uuid.UUID(TENANT))

        assert r.estado == "sector_sin_clasificar"
        assert r.total == 0
        assert r.sector_id == sid

    def test_con_normas_clasificadas_devuelve_resultado(self, db: Session) -> None:
        sid = _sector(db)
        _perfilar(db, sid)
        _limpiar(db, sid)
        _clasificar(db, _una_norma(db), sid, "directa")

        r = calcular(db, uuid.UUID(TENANT))

        assert r.estado == "con_normativa"
        assert r.total == 1

    def test_los_tres_estados_son_distinguibles(self, db: Session) -> None:
        """Ninguno se puede confundir con otro leyendo solo el total."""
        sid = _sector(db)

        _perfilar(db, None)
        sin_perfil = calcular(db, uuid.UUID(TENANT))

        _perfilar(db, sid)
        _limpiar(db, sid)
        sin_clasificar = calcular(db, uuid.UUID(TENANT))

        assert sin_perfil.total == sin_clasificar.total == 0
        assert sin_perfil.estado != sin_clasificar.estado


class TestObligatoriasYRecomendadas:
    def test_directa_es_obligatoria(self, db: Session) -> None:
        sid = _sector(db)
        _perfilar(db, sid)
        _limpiar(db, sid)
        _clasificar(db, _una_norma(db), sid, "directa")

        r = calcular(db, uuid.UUID(TENANT))

        assert len(r.obligatorias) == 1
        assert not r.recomendadas

    @pytest.mark.parametrize("nivel", ["indirecta", "referencial"])
    def test_indirecta_y_referencial_son_recomendadas(
        self, db: Session, nivel: str
    ) -> None:
        sid = _sector(db)
        _perfilar(db, sid)
        _limpiar(db, sid)
        _clasificar(db, _una_norma(db), sid, nivel)

        r = calcular(db, uuid.UUID(TENANT))

        assert len(r.recomendadas) == 1
        assert not r.obligatorias

    def test_solo_directa_obliga(self) -> None:
        """Si alguien agrega un nivel al conjunto, que sea a proposito.

        Ensanchar `NIVELES_OBLIGATORIOS` convertiria recomendaciones en
        incumplimientos y hundiria el porcentaje de todas las empresas del
        sector de golpe.
        """
        assert NIVELES_OBLIGATORIOS == frozenset({"directa"})


class TestTrazabilidad:
    def test_cada_norma_dice_por_que_entro(self, db: Session) -> None:
        """Es la respuesta a la primera pregunta de un fiscalizador."""
        sid = _sector(db)
        _perfilar(db, sid)
        _limpiar(db, sid)
        _clasificar(db, _una_norma(db), sid, "directa")

        norma = calcular(db, uuid.UUID(TENANT)).obligatorias[0]

        assert norma.sector_id == sid
        assert norma.applicability_level == "directa"
        assert norma.rationale


class TestNoEscribe:
    def test_calcular_no_toca_la_matriz(self, db: Session) -> None:
        """Calcular y aplicar son operaciones distintas a proposito.

        El negocio pidio un **check** antes de comprometer. Si calcular
        escribiera, ese check no existiria.
        """
        sid = _sector(db)
        _perfilar(db, sid)
        _limpiar(db, sid)
        _clasificar(db, _una_norma(db), sid, "directa")
        antes = db.execute(text("SELECT count(*) FROM matrix_norms")).scalar_one()

        calcular(db, uuid.UUID(TENANT))

        despues = db.execute(text("SELECT count(*) FROM matrix_norms")).scalar_one()
        assert despues == antes
