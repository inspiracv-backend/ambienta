"""Cada ruta declara que permiso exige, o por que no exige ninguno (RF-08).

Spec: `openspec/changes/sistema-actores-roles-rbac/specs/rbac/spec.md`.

## Por que existe esta prueba

La guarda se aplica **una vez**, como dependencia de cada router, y el permiso
concreto se deriva de la ruta. Eso evita el olvido —no hay que acordarse de
poner `Depends(...)` en 150 endpoints— pero traslada el riesgo a otro lado: si
aparece una raiz de ruta que el mapa no conoce, `permiso_requerido` devuelve
`None` y **el endpoint queda sin proteger, en silencio**.

Esta prueba es lo que convierte ese silencio en un fallo de CI.
"""
from __future__ import annotations

import pytest

from app.permisos_de_rutas import (
    FAMILIA_POR_RAIZ,
    FAMILIA_POR_SUBRUTA,
    PERMISO_POR_ACCION,
    SIN_GUARDA_DE_PERMISO,
    permiso_requerido,
)


@pytest.fixture(scope="module")
def rutas():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from test_alcance_por_endpoint import _rutas

    return [
        (camino, metodo)
        for camino, ruta in _rutas()
        for metodo in ruta.methods
        if metodo in ("GET", "POST", "PATCH", "PUT", "DELETE")
    ]


def test_ninguna_raiz_de_ruta_quedo_sin_declarar(rutas) -> None:
    """Una raiz desconocida deja sus endpoints sin guarda, sin avisar."""
    conocidas = set(FAMILIA_POR_RAIZ) | set(SIN_GUARDA_DE_PERMISO)
    desconocidas = set()
    for camino, _ in rutas:
        if not camino.startswith("/api/v1/"):
            continue
        raiz = camino[len("/api/v1/") :].split("/")[0]
        if raiz and raiz not in conocidas:
            desconocidas.add(raiz)

    assert not desconocidas, (
        f"Raices sin declarar: {sorted(desconocidas)}. Sus endpoints quedan SIN "
        "guarda de permisos. Agregalas a FAMILIA_POR_RAIZ, o a "
        "SIN_GUARDA_DE_PERMISO explicando por que no llevan."
    )


def test_toda_escritura_de_negocio_exige_un_permiso(rutas) -> None:
    """El caso que importa: que no haya escrituras abiertas."""
    sin_permiso = [
        f"{metodo} {camino}"
        for camino, metodo in rutas
        if metodo in ("POST", "PATCH", "PUT", "DELETE")
        and camino.startswith("/api/v1/")
        and camino[len("/api/v1/") :].split("/")[0] not in SIN_GUARDA_DE_PERMISO
        and permiso_requerido(camino, metodo) is None
    ]

    assert not sin_permiso, f"Escrituras sin permiso exigido: {sin_permiso}"


def test_ninguna_exencion_se_quedo_sin_motivo() -> None:
    """Una exencion sin explicar es indistinguible de un olvido."""
    vacias = [r for r, motivo in SIN_GUARDA_DE_PERMISO.items() if not motivo.strip()]
    assert not vacias, f"Exenciones sin explicar: {vacias}"


def test_las_exenciones_declaradas_siguen_existiendo(rutas) -> None:
    """Una exencion sobre una raiz que ya no existe es ruido que confunde."""
    raices = {
        camino[len("/api/v1/") :].split("/")[0]
        for camino, _ in rutas
        if camino.startswith("/api/v1/")
    }
    fantasmas = [r for r in SIN_GUARDA_DE_PERMISO if r not in raices]
    assert not fantasmas, f"Exenciones que sobran: {fantasmas}"


class TestDerivacion:
    def test_leer_pide_read_y_escribir_pide_write(self) -> None:
        assert permiso_requerido("/api/v1/obligations/", "GET") == "obligation.read"
        assert permiso_requerido("/api/v1/obligations/", "POST") == "obligation.write"
        assert permiso_requerido("/api/v1/obligations/{id}", "DELETE") == "obligation.write"

    def test_las_acciones_tienen_permiso_propio(self) -> None:
        """Enviar una declaracion no es "editar una obligacion".

        El analisis pidio separar firmar de editar: quien registra la evidencia
        no deberia ser quien decide que basta.
        """
        assert (
            permiso_requerido("/api/v1/obligations/{id}/fulfill", "POST")
            == "obligation.submit"
        )
        assert (
            permiso_requerido("/api/v1/audits/nonconformities/{id}/close", "POST")
            == "nonconformity.close"
        )
        assert (
            permiso_requerido("/api/v1/compliance/article-compliance/{id}/evaluate", "POST")
            == "legal_matrix.article.evaluate"
        )

    def test_una_subruta_puede_tener_familia_propia(self) -> None:
        """Cerrar una no conformidad y planificar una auditoria son distintas."""
        assert permiso_requerido("/api/v1/audits/", "POST") == "audit.write"
        assert (
            permiso_requerido("/api/v1/audits/nonconformities/", "POST")
            == "nonconformity.write"
        )

    def test_administrar_permisos_no_se_divide_en_leer_y_escribir(self) -> None:
        """Es una sola capacidad: quien puede verlos puede cambiarlos."""
        assert permiso_requerido("/api/v1/users/{id}/permissions", "GET") == "role.manage"
        assert (
            permiso_requerido("/api/v1/users/{id}/permissions/{c}", "PUT") == "role.manage"
        )

    def test_las_rutas_exentas_no_exigen_nada(self) -> None:
        for camino in (
            "/api/v1/catalog/norms",
            "/api/v1/webhooks/clerk",
            "/api/v1/dashboard/metrics",
            "/health",
        ):
            assert permiso_requerido(camino, "GET") is None, camino

    def test_una_raiz_desconocida_devuelve_none(self) -> None:
        """Se documenta el riesgo que la prueba de arriba cubre.

        Devolver `None` es lo correcto —no se puede inventar un permiso— pero
        significa **sin guarda**. Por eso existe
        `test_ninguna_raiz_de_ruta_quedo_sin_declarar`.
        """
        assert permiso_requerido("/api/v1/inventado/", "POST") is None


class TestCoherenciaConElCatalogo:
    def test_todo_permiso_derivado_existe_en_el_catalogo_sembrado(self) -> None:
        """Un permiso que no existe no lo tiene nadie: 403 permanente.

        Es el mismo error que ya se cometio una vez con `usuarios.permisos`.
        Aca se lee el seed en vez de repetir la lista: copiarla seria la
        duplicacion que esta prueba existe para impedir.
        """
        import pathlib
        import re

        raiz = pathlib.Path(__file__).resolve().parents[3]
        seed = (raiz / "db" / "03_seed_catalogos.sql").read_text(encoding="utf-8")
        sembrados = set(re.findall(r"'([a-z_]+(?:\.[a-z_]+)+)'", seed))
        if not sembrados:
            pytest.skip("No se pudieron leer los permisos del seed")

        derivados = set(PERMISO_POR_ACCION.values())
        for familia in list(FAMILIA_POR_RAIZ.values()) + list(FAMILIA_POR_SUBRUTA.values()):
            if "." in familia:
                derivados.add(familia)
            else:
                derivados.update({f"{familia}.read", f"{familia}.write"})

        inventados = derivados - sembrados
        assert not inventados, (
            f"Permisos derivados que no existen en el catalogo: {sorted(inventados)}. "
            "Nadie los tiene, asi que esas rutas dan 403 para siempre."
        )


class TestElRolDeServicioNoPuedeEscribir:
    """"Solo GETs" comprobado contra los permisos reales, no contra su nombre.

    Un rol llamado `servicio_lectura` que igual pueda escribir es una etiqueta,
    no una restriccion. Aca se cruza lo que exige cada ruta con lo que el rol
    concede.
    """

    @pytest.fixture(scope="class")
    def permisos_del_servicio(self):
        import os

        from sqlalchemy import create_engine, text

        url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
        )
        engine = create_engine(url)
        try:
            conexion = engine.connect()
        except Exception as exc:  # pragma: no cover - entorno sin base
            pytest.skip(f"Sin base de datos disponible: {exc}")
        try:
            conexion.execute(text("SET LOCAL ROLE ambienta_app"))
            conexion.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": "a0000000-0000-0000-0000-000000000001"},
            )
            filas = conexion.execute(
                text(
                    "SELECT p.code FROM role_permissions rp "
                    "JOIN roles r ON r.id = rp.role_id "
                    "JOIN permissions p ON p.id = rp.permission_id "
                    "WHERE r.code = 'servicio_lectura' AND rp.granted"
                )
            ).all()
        finally:
            conexion.close()
            engine.dispose()
        if not filas:
            pytest.skip("El rol servicio_lectura no existe en esta base")
        return {c for (c,) in filas}

    def test_no_alcanza_ninguna_escritura(self, rutas, permisos_del_servicio) -> None:
        alcanzables = [
            f"{metodo} {camino}"
            for camino, metodo in rutas
            if metodo in ("POST", "PATCH", "PUT", "DELETE")
            and (permiso_requerido(camino, metodo) or "") in permisos_del_servicio
        ]

        assert not alcanzables, (
            f"El rol de solo lectura alcanza estas escrituras: {alcanzables}"
        )

    def test_si_alcanza_las_lecturas_que_una_integracion_necesita(
        self, rutas, permisos_del_servicio
    ) -> None:
        """Que no pueda escribir no sirve si tampoco puede leer."""
        for camino in (
            "/api/v1/obligations/",
            "/api/v1/compliance/matrix-norms",
            "/api/v1/documents/",
        ):
            codigo = permiso_requerido(camino, "GET")
            assert codigo in permisos_del_servicio, f"{camino} pide {codigo}"
