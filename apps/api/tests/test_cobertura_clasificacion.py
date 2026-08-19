"""Cuanta normativa falta clasificar (7.2).

Este conteo existe para que un vacio deje de ser invisible: hoy `norm_sectors`
esta vacia, asi que el sistema funciona entero y no propone ninguna norma, y la
unica senal es un `sector_sin_clasificar` que se lee como un error tecnico.

Lo que hay que proteger es que el numero **no se vea mejor de lo que esta**. Un
conteo que se olvida de los sectores en cero, o que da por clasificada una norma
borrada, dice "vamos bien" cuando no hay nada hecho — y nadie va a ir a revisar
un tablero que se ve verde.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.cobertura_clasificacion import calcular

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
TENANT = uuid.UUID("a0000000-0000-0000-0000-000000000001")


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
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(TENANT)}
    )
    try:
        yield sesion
    finally:
        # Rollback siempre: estas pruebas clasifican normas, que es catalogo
        # global — dejarlas escritas afectaria a todas las empresas.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _norma(db: Session) -> uuid.UUID:
    nid = db.execute(
        text("SELECT id FROM legal_norms WHERE deleted_at IS NULL LIMIT 1")
    ).scalar()
    if nid is None:
        pytest.skip("Sin normas en el catalogo")
    return nid


def _sector(db: Session, codigo: str = "C") -> int:
    sid = db.execute(
        text("SELECT id FROM sectors WHERE code = :c"), {"c": codigo}
    ).scalar()
    if sid is None:
        pytest.skip(f"Sin el sector CIIU {codigo} sembrado")
    return sid


def _clasificar(db: Session, norm_id, sector_id: int, nivel: str) -> None:
    db.execute(
        text(
            "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale) "
            "VALUES (:n, :s, :l, 'prueba de cobertura') "
            "ON CONFLICT (norm_id, sector_id) DO UPDATE SET applicability_level = :l"
        ),
        {"n": norm_id, "s": sector_id, "l": nivel},
    )


class TestElNumeroNoSeVeMejorDeLoQueEsta:
    def test_una_norma_sin_ninguna_clasificacion_cuenta_como_pendiente(
        self, db: Session
    ) -> None:
        db.execute(text("DELETE FROM norm_sectors"))

        c = calcular(db)

        assert c.normas_totales > 0
        assert c.normas_sin_clasificar == c.normas_totales

    def test_una_sola_clasificacion_ya_saca_la_norma_de_pendientes(
        self, db: Session
    ) -> None:
        """Una norma revisada esta revisada.

        Exigir que cubra los 21 sectores CIIU inflaria el pendiente hasta
        volverlo inutil: casi ninguna ley aplica a todos.
        """
        db.execute(text("DELETE FROM norm_sectors"))
        antes = calcular(db).normas_sin_clasificar

        _clasificar(db, _norma(db), _sector(db), "directa")

        assert calcular(db).normas_sin_clasificar == antes - 1

    def test_los_sectores_en_cero_aparecen_igual(self, db: Session) -> None:
        """Son los que senalan donde falta trabajo.

        Omitirlos deja una lista corta y verde que no menciona los sectores
        donde una empresa entraria y no recibiria nada.
        """
        db.execute(text("DELETE FROM norm_sectors"))

        c = calcular(db)

        assert len(c.por_sector) > 1
        assert all(s.total == 0 for s in c.por_sector)
        assert c.sectores_sin_normativa == len(c.por_sector)

    def test_una_norma_borrada_no_cuenta_como_clasificada(self, db: Session) -> None:
        """Su fila en `norm_sectors` sigue ahi: la tabla no lleva borrado logico.

        Contarla daria un pendiente mas bajo que el real por una norma que ya
        no existe.
        """
        db.execute(text("DELETE FROM norm_sectors"))
        norm_id = _norma(db)
        _clasificar(db, norm_id, _sector(db), "directa")
        assert calcular(db).por_sector

        db.execute(
            text("UPDATE legal_norms SET deleted_at = now() WHERE id = :n"),
            {"n": norm_id},
        )
        c = calcular(db)

        assert all(s.total == 0 for s in c.por_sector)


class TestDirectasYRecomendadas:
    def test_directa_es_obligatoria_y_va_aparte(self, db: Session) -> None:
        db.execute(text("DELETE FROM norm_sectors"))
        sid = _sector(db)
        _clasificar(db, _norma(db), sid, "directa")

        s = next(x for x in calcular(db).por_sector if x.sector_id == sid)

        assert (s.directas, s.recomendadas) == (1, 0)

    @pytest.mark.parametrize("nivel", ["indirecta", "referencial"])
    def test_los_otros_dos_niveles_son_recomendados(
        self, db: Session, nivel: str
    ) -> None:
        """`indirecta` y `referencial` se proponen; no obligan.

        Meterlos en `directas` convertiria una sugerencia en una obligacion en
        la matriz de la empresa, que es justo lo que la separacion evita.
        """
        db.execute(text("DELETE FROM norm_sectors"))
        sid = _sector(db)
        _clasificar(db, _norma(db), sid, nivel)

        s = next(x for x in calcular(db).por_sector if x.sector_id == sid)

        assert (s.directas, s.recomendadas) == (0, 1)

    def test_total_suma_las_dos(self, db: Session) -> None:
        db.execute(text("DELETE FROM norm_sectors"))
        sid = _sector(db)
        normas = db.execute(
            text("SELECT id FROM legal_norms WHERE deleted_at IS NULL LIMIT 2")
        ).scalars().all()
        if len(normas) < 2:
            pytest.skip("Se necesitan dos normas")
        _clasificar(db, normas[0], sid, "directa")
        _clasificar(db, normas[1], sid, "referencial")

        s = next(x for x in calcular(db).por_sector if x.sector_id == sid)

        assert (s.directas, s.recomendadas, s.total) == (1, 1, 2)

    def test_un_sector_no_se_lleva_las_normas_de_otro(self, db: Session) -> None:
        db.execute(text("DELETE FROM norm_sectors"))
        manufactura, mineria = _sector(db, "C"), _sector(db, "B")
        _clasificar(db, _norma(db), manufactura, "directa")

        por_sector = {s.sector_id: s for s in calcular(db).por_sector}

        assert por_sector[manufactura].total == 1
        assert por_sector[mineria].total == 0


class TestElEndpoint:
    def test_arma_la_respuesta_completa(self, db: Session) -> None:
        """La forma de la respuesta, que las pruebas del servicio no cubren."""
        from app.routers.catalog import cobertura_de_la_clasificacion

        db.execute(text("DELETE FROM norm_sectors"))
        _clasificar(db, _norma(db), _sector(db), "directa")

        cuerpo = cobertura_de_la_clasificacion(db=db).model_dump()

        assert cuerpo["normas_totales"] > 0
        assert cuerpo["normas_sin_clasificar"] == cuerpo["normas_totales"] - 1
        assert len(cuerpo["por_sector"]) > 1
        assert {"sector_id", "codigo", "nombre", "directas", "recomendadas", "total"} <= set(
            cuerpo["por_sector"][0]
        )
