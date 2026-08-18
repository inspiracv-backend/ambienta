"""Clasificacion de normas por sector: lo que alimenta el filtro (RF-19).

Spec: `openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md`.

Dos propiedades que el spec exige y que son faciles de perder:

1. **Sin fundamento no se clasifica.** Una clasificacion sin explicacion es
   indistinguible de un error de carga cuando alguien la revisa un ano despues,
   y esta se propaga a **todas** las empresas del sector.
2. **Solo la plataforma clasifica.** `norm_sectors` no lleva `tenant_id`: si un
   usuario de una empresa pudiera escribir ahi, le cambiaria la normativa a sus
   competidores.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.catalog import NormSectorWrite


class TestFundamentoObligatorio:
    """El `rationale` no es decorativo: es lo que hace corregible un error."""

    def test_sin_fundamento_no_valida(self) -> None:
        with pytest.raises(Exception):
            NormSectorWrite(applicability_level="directa")

    def test_un_fundamento_de_una_palabra_no_alcanza(self) -> None:
        """El minimo existe para que no se escriba "si" y se siga de largo."""
        with pytest.raises(Exception):
            NormSectorWrite(applicability_level="directa", rationale="si")

    def test_con_fundamento_real_valida(self) -> None:
        w = NormSectorWrite(
            applicability_level="directa",
            rationale="Regula emisiones de fuentes fijas, presentes en toda planta manufacturera.",
        )
        assert w.applicability_level == "directa"

    def test_el_nivel_por_defecto_es_directa(self) -> None:
        """Lo mas conservador: si nadie lo dice, la norma se debe cumplir.

        El defecto opuesto —recomendada— haria que una norma mal clasificada
        desapareciera de las obligaciones sin que nadie lo note.
        """
        w = NormSectorWrite(rationale="Aplica a toda instalacion con caldera.")
        assert w.applicability_level == "directa"


class TestContrato:
    """La forma de los endpoints, sin depender de la base."""

    @pytest.fixture(scope="class")
    def esquema(self) -> dict:
        app.openapi_schema = None
        return app.openapi()

    def test_leer_la_clasificacion_no_exige_admin_global(self, esquema: dict) -> None:
        """Saber que normas aplican a un sector es informacion de trabajo."""
        op = esquema["paths"]["/api/v1/catalog/norms/{norm_id}/sectors"]["get"]
        assert "403" not in op.get("responses", {})

    def test_escribir_la_clasificacion_es_idempotente(self, esquema: dict) -> None:
        """Es PUT y no POST: declarar dos veces lo mismo deja el mismo estado."""
        ruta = esquema["paths"]["/api/v1/catalog/norms/{norm_id}/sectors/{sector_id}"]
        assert "put" in ruta
        assert "post" not in ruta

    def test_los_tres_endpoints_estan_documentados(self, esquema: dict) -> None:
        """Sin explicacion, /docs no sirve para integrar."""
        rutas = [
            ("/api/v1/catalog/norms/{norm_id}/sectors", "get"),
            ("/api/v1/catalog/norms/{norm_id}/sectors/{sector_id}", "put"),
            ("/api/v1/catalog/norms/{norm_id}/sectors/{sector_id}", "delete"),
        ]
        for ruta, metodo in rutas:
            op = esquema["paths"][ruta][metodo]
            assert op.get("description", "").strip(), f"{metodo.upper()} {ruta} sin describir"


class TestNivelInvalido:
    """El CHECK vive en la base; la API lo repite para dar un 422 util."""

    def test_un_nivel_inventado_no_esta_entre_los_validos(self) -> None:
        from app.routers.catalog import NIVELES_DE_APLICABILIDAD

        assert "inventado" not in NIVELES_DE_APLICABILIDAD
        assert NIVELES_DE_APLICABILIDAD == {"directa", "indirecta", "referencial"}

    def test_los_niveles_de_la_api_son_los_mismos_que_los_de_la_base(self) -> None:
        """Si se separan, la API acepta algo que la base rechaza con un 500.

        Se lee el CHECK del esquema en vez de repetir la lista a mano: copiarla
        seria exactamente la duplicacion que este test existe para impedir.
        """
        import pathlib
        import re

        raiz = pathlib.Path(__file__).resolve().parents[3]
        esquema_sql = (raiz / "db" / "01_schema.sql").read_text(encoding="utf-8")
        m = re.search(
            r"applicability_level[\s\S]{0,200}?CHECK \(applicability_level IN \(([^)]+)\)",
            esquema_sql,
        )
        assert m, "No se encontro el CHECK de applicability_level en el esquema"
        en_la_base = {v.strip().strip("'") for v in m.group(1).split(",")}

        from app.routers.catalog import NIVELES_DE_APLICABILIDAD

        assert NIVELES_DE_APLICABILIDAD == en_la_base


def test_el_cliente_de_pruebas_monta_la_app() -> None:
    """Guarda de humo: si la app no monta, los demas tests mienten."""
    with TestClient(app) as cliente:
        assert cliente.get("/health").status_code == 200
