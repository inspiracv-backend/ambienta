"""La semilla que hace **revisables** los tres paneles de la 14001 (#50).

## Por que hacia falta

La semilla ya dejaba el modulo con datos, pero los tres paneles salian siempre
en el mismo estado, asi que QA no podia revisarlos:

| panel | lo que se veia | lo que faltaba |
|---|---|---|
| Significativos sin tratar (#49) | los 3 aspectos, ninguno enlazado | un aspecto **si** tratado |
| Sin operador habilitado (#48) | siempre vacio | los dos motivos |
| Por vencer (#47) | ya funcionaba | — |

**Un panel que solo se sabe ver vacio no esta revisado.** El estado vacio y el
estado con datos se dibujan por caminos distintos, y en este proyecto el error
siempre estuvo en el vacio — `normSemaforo(0)`, el tablero con las plantas sin
evaluar, la cobertura, los reportes.

## Lo que estas pruebas afirman, y lo que no

Afirman que **despues de sembrar, los tres paneles tienen algo que mostrar y su
contrario**. No afirman que la semilla sea correcta como dato de negocio: son
filas de ejemplo, marcadas con `[QA]` justamente para que nadie las confunda.

Y no se inventan puntajes ni significancias. Eso lo sigue decidiendo
`evaluar_aspecto()` con la regla real; lo que la semilla agrega es un enlace
entre cosas que ya existian y dos equipos de ejemplo.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.tareas.sembrar_demo import EQUIPOS_DE_QA  # noqa: E402

EMPRESA = "a0000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def cliente():
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible ({exc}). Hace falta docker compose.")

    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as c:
        c.headers["X-Tenant-Id"] = EMPRESA
        yield c


def _sembrado(cliente) -> bool:
    """Si la semilla de QA corrio en esta base.

    Se pregunta en vez de correrla: `sembrar_demo` escribe de verdad y hacerlo
    desde una prueba dejaria filas segun el orden en que se ejecuten. La suite
    **no siembra**; comprueba lo que la semilla dejo, y se salta si no corrio.
    """
    r = cliente.get("/api/v1/iso14001/equipment?limit=500")
    if r.status_code != 200:
        return False
    return any(str(e.get("name", "")).startswith("[QA]") for e in r.json())


class TestLosTresPanelesSonRevisables:
    def test_hay_significativos_sin_tratar_Y_alguno_tratado(self, cliente) -> None:
        """Los dos lados del vinculo §6.1.2 → §6.1.4.

        Con los tres significativos sin enlazar, el panel se ve igual que si el
        vinculo no existiera: no se puede distinguir "nadie lo trato" de "el
        sistema no sabe enlazarlos".
        """
        if not _sembrado(cliente):
            pytest.skip("La semilla de QA no corrio: `python -m app.tareas.sembrar_demo`")

        sin_tratar = cliente.get("/api/v1/iso14001/aspects/significant-untreated")
        assert sin_tratar.status_code == 200, sin_tratar.text

        riesgos = cliente.get("/api/v1/iso14001/risks?limit=500")
        enlazados = [
            r for r in riesgos.json() if r.get("environmental_aspect_id") is not None
        ]

        assert sin_tratar.json(), (
            "Ningun aspecto significativo quedo sin tratar: el panel se ve "
            "vacio y QA no puede revisar como se dibuja con filas."
        )
        assert enlazados, (
            "Ningun riesgo apunta a un aspecto: no se puede revisar el caso "
            "contrario, que es el que demuestra que el vinculo funciona."
        )

    def test_el_panel_de_incumplimiento_muestra_sus_dos_motivos(self, cliente) -> None:
        """`sin_operador` y `certificacion_vencida` se arreglan distinto.

        Uno se resuelve asignando a alguien; el otro renovando una
        certificacion que caduco — ahi **si hay gente asignada**. Con un solo
        caso sembrado la pantalla no puede enseñar la diferencia.
        """
        if not _sembrado(cliente):
            pytest.skip("La semilla de QA no corrio: `python -m app.tareas.sembrar_demo`")

        r = cliente.get("/api/v1/iso14001/equipment/sin-operador")
        assert r.status_code == 200, r.text
        motivos = {f["motivo"] for f in r.json()}

        assert motivos == {"sin_operador", "certificacion_vencida"}, (
            f"El panel solo puede mostrar {sorted(motivos)}. Los dos motivos "
            "tienen que ser revisables: se ven distinto y se arreglan distinto."
        )

        con_vencida = next(
            f for f in r.json() if f["motivo"] == "certificacion_vencida"
        )
        assert con_vencida["operadores_asignados"] > 0, (
            "Un equipo con la certificacion vencida tiene gente asignada — esa "
            "es toda la diferencia con `sin_operador`, y es lo que hace que el "
            "caso se parezca a estar en regla sin estarlo."
        )

    def test_hay_algo_por_vencer_y_algo_ya_vencido(self, cliente) -> None:
        """Lo vencido va en la **misma** lista, con dias negativos.

        Una lista de "por vencer" que deja fuera lo que ya vencio esconde justo
        lo urgente, y es la unica que alguien mira.
        """
        if not _sembrado(cliente):
            pytest.skip("La semilla de QA no corrio: `python -m app.tareas.sembrar_demo`")

        d = cliente.get("/api/v1/iso14001/equipment/expiring").json()
        todos = d["equipos"] + d["operadores"]

        assert todos, "Nada por vencer: el panel no se puede revisar con filas."
        assert any(x["dias_restantes"] < 0 for x in todos), (
            "Nada aparece ya vencido. El caso de dias negativos se dibuja "
            "distinto —en rojo y primero— y sin un ejemplo no se revisa."
        )


class TestLaSemillaNoDuplica:
    def test_los_equipos_de_qa_estan_una_sola_vez(self, cliente) -> None:
        """`sembrar_demo` se corre varias veces: al preparar una demostracion,
        al reanclar los vencimientos, al reparar una base a medias.

        Se reconoce por el nombre y no lleva una tabla aparte, asi que esta
        prueba es lo unico que impide que la tercera corrida deje seis
        equipos de ejemplo en la lista.
        """
        if not _sembrado(cliente):
            pytest.skip("La semilla de QA no corrio: `python -m app.tareas.sembrar_demo`")

        equipos = cliente.get("/api/v1/iso14001/equipment?limit=500").json()
        for nombre, _tipo, _motivo in EQUIPOS_DE_QA:
            cuantos = sum(1 for e in equipos if e["name"] == nombre)
            assert cuantos == 1, f"«{nombre}» aparece {cuantos} veces, no una."

    def test_los_de_qa_se_distinguen_de_los_reales(self, cliente) -> None:
        """El prefijo `[QA]` no es decoracion.

        Quien mira la demostracion tiene que poder decir en un vistazo cual es
        dato de ejemplo. Un equipo inventado sin marcar, en un modulo que se
        exporta a un auditor, se lee como un equipo de la empresa.
        """
        if not _sembrado(cliente):
            pytest.skip("La semilla de QA no corrio: `python -m app.tareas.sembrar_demo`")

        for nombre, _tipo, _motivo in EQUIPOS_DE_QA:
            assert nombre.startswith("[QA]"), nombre
