"""El perfil normativo de la empresa: sector y tramo (RF-19).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

Lo que se protege aca es una distincion que se pierde facil: **una empresa sin
sector declarado no tiene perfil normativo**, y eso NO es lo mismo que tener un
perfil vacio. Si la pantalla no puede distinguirlas, le muestra a la empresa una
lista vacia de normas, que se lee como "no tenes obligaciones" — lo contrario de
lo que pasa.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.schemas.organization import TenantRead

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
TENANT = "a0000000-0000-0000-0000-000000000001"


def _tenant(**extra):
    base = dict(
        id=uuid.uuid4(),
        country_id=1,
        parent_tenant_id=None,
        tenant_type="company",
        rut_tax_id="76.111.222-3",
        legal_name="Empresa de prueba",
        trade_name=None,
        business_activity=None,
        sector_id=None,
        size_bracket=None,
        status="active",
        settings={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(extra)
    return TenantRead(**base)


class TestPerfilDeclarado:
    def test_sin_sector_no_tiene_perfil_normativo(self) -> None:
        assert _tenant().tiene_perfil_normativo is False

    def test_con_sector_tiene_perfil_normativo(self) -> None:
        assert _tenant(sector_id=3).tiene_perfil_normativo is True

    def test_el_giro_escrito_no_reemplaza_al_sector(self) -> None:
        """El escenario que el spec deja explicito.

        "Fabricacion de envases plasticos" y "envases plasticos" son la misma
        industria y dos cadenas distintas. Un texto libre no se cruza con nada,
        y por eso tener giro escrito no alcanza para calcular normativa.
        """
        con_giro = _tenant(business_activity="Fabricacion de envases plasticos")

        assert con_giro.business_activity is not None
        assert con_giro.tiene_perfil_normativo is False

    def test_el_tramo_solo_no_alcanza(self) -> None:
        """El sector es lo que cruza con la normativa; el tramo la acota."""
        assert _tenant(size_bracket="mediana").tiene_perfil_normativo is False


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


class TestEsquema:
    def test_el_sector_apunta_al_catalogo_ciiu_ya_sembrado(self, db: Session) -> None:
        """No se creo un catalogo nuevo: `sectors` ya existia y estaba sembrada.

        Duplicarlo habria sido el peor resultado posible de este cambio: dos
        listas de sectores que se desincronizan sin que nadie lo note.
        """
        manufacturera = db.execute(
            text("SELECT id, name FROM sectors WHERE code = 'C'")
        ).first()

        assert manufacturera is not None, "Falta la seccion CIIU C"
        assert "anufacturera" in manufacturera[1]

    def test_el_tramo_rechaza_un_valor_fuera_del_catalogo(self, db: Session) -> None:
        """El CHECK vive en la base, no en la aplicacion.

        Un tramo libre volveria a dejar entrar texto sin normalizar, que es
        exactamente el problema que este cambio corrige.
        """
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "UPDATE tenants SET size_bracket = 'enorme' WHERE id = :t"
                ),
                {"t": TENANT},
            )

    def test_el_tramo_acepta_los_cuatro_valores(self, db: Session) -> None:
        for tramo in ("micro", "pequena", "mediana", "grande"):
            db.execute(
                text("UPDATE tenants SET size_bracket = :s WHERE id = :t"),
                {"s": tramo, "t": TENANT},
            )
        # Sin excepcion: los cuatro pasan el CHECK.

    def test_el_origen_de_inclusion_solo_admite_automatico_o_manual(
        self, db: Session
    ) -> None:
        """Distinguirlos es lo que impide que un recalculo borre trabajo humano."""
        from sqlalchemy.exc import IntegrityError

        fila = db.execute(text("SELECT id FROM matrix_norms LIMIT 1")).scalar()
        if fila is None:
            pytest.skip("Sin normas en ninguna matriz")

        with pytest.raises(IntegrityError):
            db.execute(
                text("UPDATE matrix_norms SET inclusion_source = 'inventado' WHERE id = :i"),
                {"i": fila},
            )

    def test_no_se_duplicaron_columnas_que_ya_existian(self, db: Session) -> None:
        """La primera version de la migracion agregaba tres columnas repetidas.

        `selected_version_id` ya cubria la version evaluada, `created_by` el
        responsable, y `applicability` lo que deja de aplicar. Dos fuentes de
        verdad para el mismo dato es peor que no tenerlo: la segunda se
        desactualiza en silencio.
        """
        repetidas = db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'matrix_norms' AND column_name IN "
                "('evaluated_version_id','included_by','no_longer_applicable_at')"
            )
        ).all()

        assert not repetidas, f"Columnas duplicadas que hay que sacar: {repetidas}"
