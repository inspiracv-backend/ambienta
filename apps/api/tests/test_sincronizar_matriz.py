"""Sincronizar la matriz: agrega, nunca borra (RF-19, RF-29).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

La promesa de este servicio es que **correrlo no destruye trabajo**. Es facil
de romper sin notarlo —basta un `DELETE` "para dejar la matriz limpia"— y el
dano solo se ve cuando alguien busca la evaluacion de un periodo pasado y ya no
esta. Por eso el viaje completo esta cubierto: generar, evaluar, regenerar, y
comprobar que la evaluacion sigue ahi.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.sincronizar_matriz import MOTIVO_YA_NO_APLICA, sincronizar

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
        # Rollback siempre: estas pruebas clasifican normas y generan matrices.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _sector_manufactura(db: Session) -> int:
    sid = db.execute(text("SELECT id FROM sectors WHERE code = 'C'")).scalar()
    if sid is None:
        pytest.skip("Sin el sector CIIU C sembrado")
    return sid


def _norma_con_articulos(db: Session):
    """Una norma que tenga version vigente y articulado. Sin eso no hay que sembrar."""
    fila = db.execute(
        text(
            "SELECT v.norm_id FROM legal_norm_versions v "
            "JOIN legal_articles a ON a.norm_version_id = v.id "
            "WHERE v.is_current AND v.deleted_at IS NULL AND a.deleted_at IS NULL "
            "GROUP BY v.norm_id LIMIT 1"
        )
    ).scalar()
    if fila is None:
        pytest.skip("Sin normas con articulado vigente")
    return fila


#: Ano que no usa el seed. `uq_matrices_periodo` es UNIQUE sobre
#: (tenant, ano, planta, version) con NULLS NOT DISTINCT, asi que una matriz de
#: prueba en 2026 choca con la sembrada — y el fallo se lee como un error del
#: servicio cuando en realidad es del arnes.
ANO_DE_PRUEBA = 2099


def _matriz_vacia(db: Session) -> uuid.UUID:
    mid = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO tenant_legal_matrices (id, tenant_id, name, period_year) "
            "VALUES (:i, :t, 'Matriz de prueba', :a)"
        ),
        {"i": mid, "t": TENANT, "a": ANO_DE_PRUEBA},
    )
    return mid


def _preparar(db: Session, nivel: str = "directa"):
    """Empresa con sector, una norma clasificada, y una matriz vacia."""
    sid = _sector_manufactura(db)
    norm_id = _norma_con_articulos(db)
    db.execute(
        text("UPDATE tenants SET sector_id = :s WHERE id = :t"), {"s": sid, "t": TENANT}
    )
    db.execute(text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sid})
    db.execute(
        text(
            "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale) "
            "VALUES (:n, :s, :l, 'prueba de sincronizacion')"
        ),
        {"n": norm_id, "s": sid, "l": nivel},
    )
    return _matriz_vacia(db), norm_id, sid


def _evaluaciones(db: Session, matrix_id) -> int:
    return db.execute(
        text(
            "SELECT count(*) FROM article_compliance ac "
            "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
            "WHERE mn.matrix_id = :m"
        ),
        {"m": matrix_id},
    ).scalar_one()


class TestGeneracion:
    def test_crea_la_norma_y_sus_articulos_sin_evaluar(self, db: Session) -> None:
        matrix_id, _, _ = _preparar(db)

        r = sincronizar(db, matrix_id, TENANT)

        assert r.normas_agregadas == 1
        assert r.articulos_agregados > 0
        pendientes = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'pending'"
            ),
            {"m": matrix_id},
        ).scalar_one()
        assert pendientes == r.articulos_agregados

    def test_ninguno_entra_como_incumplido(self, db: Session) -> None:
        """No haber evaluado no es incumplir.

        Con `non_compliant` por defecto, el porcentaje de la empresa caeria a
        cero el dia que se le carga la matriz — y seria mentira.
        """
        matrix_id, _, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)

        incumplidos = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'non_compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()
        assert incumplidos == 0

    def test_registra_que_la_incluyo_el_calculo(self, db: Session) -> None:
        matrix_id, _, sid = _preparar(db)
        sincronizar(db, matrix_id, TENANT)

        origen, sector = db.execute(
            text(
                "SELECT inclusion_source, sector_id FROM matrix_norms WHERE matrix_id = :m"
            ),
            {"m": matrix_id},
        ).first()
        assert origen == "automatic"
        assert sector == sid

    def test_las_recomendadas_tambien_entran(self, db: Session) -> None:
        """Obligatoria y recomendada es una distincion para la pantalla.

        Las dos van a la matriz: la diferencia es como se presentan, no si se
        evaluan.
        """
        matrix_id, _, _ = _preparar(db, nivel="referencial")

        r = sincronizar(db, matrix_id, TENANT)

        assert r.normas_agregadas == 1


class TestIdempotencia:
    def test_correrlo_dos_veces_no_duplica(self, db: Session) -> None:
        matrix_id, _, _ = _preparar(db)
        primera = sincronizar(db, matrix_id, TENANT)

        segunda = sincronizar(db, matrix_id, TENANT)

        assert segunda.normas_agregadas == 0
        assert segunda.normas_ya_estaban == 1
        assert segunda.articulos_agregados == 0
        assert _evaluaciones(db, matrix_id) == primera.articulos_agregados

    def test_la_evaluacion_sobrevive_al_recalculo(self, db: Session) -> None:
        """El viaje completo, y la razon de ser de todo el servicio.

        Generar, evaluar, regenerar: lo evaluado sigue evaluado. Si esto falla,
        cada recalculo le borra el trabajo a quien evaluo.
        """
        matrix_id, _, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        db.execute(
            text(
                "UPDATE article_compliance SET compliance_status = 'compliant' "
                "WHERE matrix_norm_id IN "
                "(SELECT id FROM matrix_norms WHERE matrix_id = :m)"
            ),
            {"m": matrix_id},
        )
        evaluados_antes = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()

        sincronizar(db, matrix_id, TENANT)

        evaluados_despues = db.execute(
            text(
                "SELECT count(*) FROM article_compliance ac "
                "JOIN matrix_norms mn ON mn.id = ac.matrix_norm_id "
                "WHERE mn.matrix_id = :m AND ac.compliance_status = 'compliant'"
            ),
            {"m": matrix_id},
        ).scalar_one()
        assert evaluados_despues == evaluados_antes > 0


class TestNuncaBorra:
    def test_lo_que_deja_de_aplicar_se_marca_y_se_conserva(self, db: Session) -> None:
        """Borrarla eliminaria la evidencia de que en su momento se evaluo."""
        matrix_id, norm_id, sid = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        db.execute(text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sid})
        # Se deja otra clasificada para que el calculo no devuelva vacio: sin
        # normativa el servicio no toca nada, y no se probaria el marcado.
        otra = db.execute(
            text(
                "SELECT v.norm_id FROM legal_norm_versions v "
                "JOIN legal_articles a ON a.norm_version_id = v.id "
                "WHERE v.is_current AND v.norm_id <> :n GROUP BY v.norm_id LIMIT 1"
            ),
            {"n": norm_id},
        ).scalar()
        if otra is None:
            pytest.skip("Se necesita una segunda norma con articulado")
        db.execute(
            text(
                "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale) "
                "VALUES (:n, :s, 'directa', 'la que queda')"
            ),
            {"n": otra, "s": sid},
        )

        r = sincronizar(db, matrix_id, TENANT)

        assert r.normas_marcadas_no_aplicables == 1
        estado, motivo = db.execute(
            text(
                "SELECT applicability, applicability_reason FROM matrix_norms "
                "WHERE matrix_id = :m AND norm_id = :n"
            ),
            {"m": matrix_id, "n": norm_id},
        ).first()
        assert estado == "not_applicable"
        assert motivo == MOTIVO_YA_NO_APLICA

    def test_un_recalculo_no_quita_lo_agregado_a_mano(self, db: Session) -> None:
        """Que el calculo no la encuentre no significa que no aplique.

        Puede venir de un contrato o de la RCA de la empresa.
        """
        matrix_id, norm_id, sid = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        db.execute(
            text(
                "UPDATE matrix_norms SET inclusion_source = 'manual' "
                "WHERE matrix_id = :m AND norm_id = :n"
            ),
            {"m": matrix_id, "n": norm_id},
        )
        db.execute(text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sid})
        otra = db.execute(
            text(
                "SELECT v.norm_id FROM legal_norm_versions v "
                "JOIN legal_articles a ON a.norm_version_id = v.id "
                "WHERE v.is_current AND v.norm_id <> :n GROUP BY v.norm_id LIMIT 1"
            ),
            {"n": norm_id},
        ).scalar()
        if otra is None:
            pytest.skip("Se necesita una segunda norma con articulado")
        db.execute(
            text(
                "INSERT INTO norm_sectors (norm_id, sector_id, applicability_level, rationale) "
                "VALUES (:n, :s, 'directa', 'la que queda')"
            ),
            {"n": otra, "s": sid},
        )

        sincronizar(db, matrix_id, TENANT)

        estado = db.execute(
            text(
                "SELECT applicability FROM matrix_norms WHERE matrix_id = :m AND norm_id = :n"
            ),
            {"m": matrix_id, "n": norm_id},
        ).scalar()
        assert estado == "applicable", "una norma manual no se marca por un recalculo"


class TestSinNormativa:
    def test_sector_sin_clasificar_no_toca_nada(self, db: Session) -> None:
        """El caso peligroso: 0 normas que NO significa "sin obligaciones".

        Si se marcaran como no aplicables las que ya estan, un sector sin
        clasificar vaciaria la matriz de una empresa que si tiene obligaciones.
        """
        matrix_id, _, sid = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        antes = _evaluaciones(db, matrix_id)
        db.execute(text("DELETE FROM norm_sectors WHERE sector_id = :s"), {"s": sid})

        r = sincronizar(db, matrix_id, TENANT)

        assert r.sin_calcular == "sector_sin_clasificar"
        assert r.normas_marcadas_no_aplicables == 0
        assert _evaluaciones(db, matrix_id) == antes

    def test_empresa_sin_perfil_no_toca_nada(self, db: Session) -> None:
        matrix_id, _, _ = _preparar(db)
        sincronizar(db, matrix_id, TENANT)
        antes = _evaluaciones(db, matrix_id)
        db.execute(text("UPDATE tenants SET sector_id = NULL WHERE id = :t"), {"t": TENANT})

        r = sincronizar(db, matrix_id, TENANT)

        assert r.sin_calcular == "sin_perfil"
        assert _evaluaciones(db, matrix_id) == antes
