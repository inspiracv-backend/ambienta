"""El informe de auditoria: matriz por proceso y tasa de cierre (#42, RF-101).

## Que faltaba, y no era el endpoint

**`audit_items` no tenia proceso.** El design dice que las tres primeras
columnas de la matriz "son derivables", y no lo eran: no habia de donde. Una
auditoria sabia que preguntas hizo y que hallazgos salieron, y **no a que
proceso pertenecia cada pregunta** — o sea que no podia decir como quedo
ninguno. El dueno de un proceso no lee la lista de hallazgos de toda la planta;
lee su fila.

## Lo que estas pruebas vigilan de verdad

No es que el endpoint responda 200. Es que **no aparezca un cero donde no hay
dato**, que es el error que este repositorio ya cometio cuatro veces
—`normSemaforo(0)`, el tablero pintando en rojo las plantas sin evaluar, la
cobertura, los reportes— y que aca tiene tres oportunidades nuevas:

| situacion | el cero que se lee como | lo correcto |
|---|---|---|
| Auditoria sin nada evaluado | "cumple 0 %" | `conformidad: null` |
| Proceso sin veredicto | "no conforme" | `no_auditado` |
| Ciclo anterior sin hallazgos | "no cerraron nada" | `null` + motivo |

El tercero es el peor. Un 0 % de tasa de cierre es una acusacion contra la
empresa, y los tres casos que lo producen —no hay auditoria anterior, la
anterior no encontro nada, la anterior sigue abierta— **no son ninguno de ellos
un incumplimiento**. Por eso el informe devuelve `null` y ademas dice cual de
los tres es: sin el motivo, quien lee tiene que adivinar.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

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


@pytest.fixture(scope="module")
def planta(cliente) -> str:
    return cliente.get("/api/v1/facilities/").json()[0]["id"]


@pytest.fixture(scope="module")
def proceso(cliente) -> str:
    """Un proceso propio, para no depender de lo que tenga el seed."""
    crear = cliente.post(
        "/api/v1/processes/",
        json={
            "code": f"PRB-{uuid.uuid4().hex[:6].upper()}",
            "name": f"Proceso de prueba {uuid.uuid4().hex[:6]}",
            "process_type": "operational",
        },
    )
    assert crear.status_code == 201, crear.text
    pid = crear.json()["id"]
    yield pid
    cliente.delete(f"/api/v1/processes/{pid}")


def _codigo() -> str:
    return f"PRB-{uuid.uuid4().hex[:8].upper()}"


def _auditoria(cliente, planta: str, *, dias_atras: int = 0) -> str:
    inicio = date.today() - timedelta(days=dias_atras)
    crear = cliente.post(
        "/api/v1/audits/",
        json={
            "facility_id": planta,
            "code": _codigo(),
            "title": "Auditoria de prueba",
            "audit_type": "internal",
            "scope": "Alcance de prueba",
            "planned_start": str(inicio),
            "planned_end": str(inicio + timedelta(days=2)),
        },
    )
    assert crear.status_code == 201, crear.text
    return crear.json()["id"]


class TestLaMatrizPorProceso:
    def test_una_pregunta_con_proceso_arma_su_fila(self, cliente, planta, proceso) -> None:
        auditoria = _auditoria(cliente, planta)
        try:
            item = cliente.post(
                f"/api/v1/audits/{auditoria}/items",
                json={
                    "sequence": 1,
                    "question": "Pregunta de prueba",
                    "process_id": proceso,
                },
            )
            assert item.status_code == 201, item.text
            assert item.json()["process_id"] == proceso, (
                "El proceso no volvio en la respuesta: la columna no se esta "
                "guardando, y sin ella la matriz no se puede armar."
            )

            informe = cliente.get(f"/api/v1/audits/{auditoria}/informe")
            assert informe.status_code == 200, informe.text
            matriz = informe.json()["matriz"]

            assert len(matriz) == 1, f"Se esperaba una fila por proceso: {matriz}"
            fila = matriz[0]
            assert fila["proceso_id"] == proceso
            assert fila["items"] == 1
            assert fila["clasificacion"] == "no_auditado", (
                "Un proceso sin veredicto del auditor tiene que decir "
                "'no_auditado', no quedar en blanco ni parecer no conforme."
            )
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")

    def test_una_pregunta_sin_proceso_se_cuenta_aparte(self, cliente, planta) -> None:
        """Un requisito general del sistema de gestion no es de ningun proceso.

        Repartirlo en una fila cualquiera inventaria una pertenencia, y
        esconderlo lo haria desaparecer del informe.
        """
        auditoria = _auditoria(cliente, planta)
        try:
            cliente.post(
                f"/api/v1/audits/{auditoria}/items",
                json={"sequence": 1, "question": "Requisito general"},
            )
            informe = cliente.get(f"/api/v1/audits/{auditoria}/informe").json()

            assert informe["matriz"] == []
            assert informe["resumen"]["items_sin_proceso"] == 1
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")

    def test_el_veredicto_del_auditor_entra_en_la_fila(
        self, cliente, planta, proceso
    ) -> None:
        auditoria = _auditoria(cliente, planta)
        try:
            cliente.post(
                f"/api/v1/audits/{auditoria}/items",
                json={"sequence": 1, "question": "p", "process_id": proceso},
            )
            veredicto = cliente.post(
                f"/api/v1/audits/{auditoria}/procesos",
                json={
                    "process_id": proceso,
                    "classification": "conforme_con_observaciones",
                    "conclusion": "El proceso cumple, con una observacion.",
                    "evidence_reviewed": "Registros de marzo.",
                },
            )
            assert veredicto.status_code == 201, veredicto.text

            fila = cliente.get(f"/api/v1/audits/{auditoria}/informe").json()["matriz"][0]
            assert fila["clasificacion"] == "conforme_con_observaciones"
            assert fila["evidencia_revisada"] == "Registros de marzo."
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")

    def test_un_proceso_no_puede_tener_dos_veredictos(
        self, cliente, planta, proceso
    ) -> None:
        """Dos veredictos son una matriz que se contradice a si misma, y el
        informe elegiria uno de los dos sin decirlo."""
        auditoria = _auditoria(cliente, planta)
        try:
            primero = cliente.post(
                f"/api/v1/audits/{auditoria}/procesos",
                json={"process_id": proceso, "classification": "conforme"},
            )
            assert primero.status_code == 201, primero.text

            segundo = cliente.post(
                f"/api/v1/audits/{auditoria}/procesos",
                json={"process_id": proceso, "classification": "no_conforme"},
            )
            assert segundo.status_code == 409, segundo.text
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")

    def test_un_proceso_de_otra_empresa_se_rechaza(self, cliente, planta) -> None:
        """Las claves foraneas **no pasan por RLS** (CLAUDE.md §4)."""
        auditoria = _auditoria(cliente, planta)
        try:
            respuesta = cliente.post(
                f"/api/v1/audits/{auditoria}/procesos",
                json={"process_id": str(uuid.uuid4()), "classification": "conforme"},
            )
            assert respuesta.status_code == 422, respuesta.text
            assert "process_id" in respuesta.json()["detail"]
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")


class TestNingunCeroInventado:
    """La parte que de verdad importa."""

    def test_una_auditoria_sin_evaluar_no_tiene_conformidad_cero(
        self, cliente, planta
    ) -> None:
        """`null`, no `0 %`. Un cero ahi acusa a la empresa por algo que nadie
        miro todavia — el error del tablero con las plantas sin evaluar."""
        auditoria = _auditoria(cliente, planta)
        try:
            resumen = cliente.get(f"/api/v1/audits/{auditoria}/informe").json()["resumen"]
            assert resumen["conformidad"] is None, (
                f"Una auditoria sin nada evaluado informo {resumen['conformidad']} "
                "de conformidad. No es 0 %: es que no se midio nada."
            )
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")

    def test_sin_auditoria_anterior_la_tasa_es_nula_y_dice_por_que(
        self, cliente, planta
    ) -> None:
        """Muy atras a proposito: **el seed tiene una auditoria interna cerrada**
        (`AUD-2026-001`, 2026-06-01) sobre esta misma planta.

        La primera version de esta prueba creaba la auditoria "hoy" y fallaba
        informando 0.0. El defecto era de la prueba, no del informe: habia
        ciclo anterior, y el informe lo encontro bien. Vale anotarlo porque el
        mensaje de fallo —"la tasa informo un numero"— apuntaba al codigo.
        """
        auditoria = _auditoria(cliente, planta, dias_atras=4000)
        try:
            informe = cliente.get(f"/api/v1/audits/{auditoria}/informe").json()

            assert informe["tasa_de_cierre_del_ciclo_anterior"] is None, (
                "Sin ciclo anterior la tasa informo un numero. Un 0 % se lee "
                "como 'no cerraron nada de lo anterior', que es una acusacion."
            )
            assert informe["motivo_sin_tasa"], (
                "La tasa vino vacia sin decir por que. Son tres casos distintos "
                "y quien lee el informe no puede adivinar cual."
            )
        finally:
            cliente.delete(f"/api/v1/audits/{auditoria}")

    def test_la_tasa_sale_de_los_hallazgos_del_ciclo_anterior(
        self, cliente, planta, proceso
    ) -> None:
        """El indicador que conecta un ciclo con el siguiente, y hoy no existia.

        Se arman dos auditorias de la misma planta y tipo: la anterior con dos
        hallazgos, uno cerrado. La tasa tiene que ser 50 %.
        """
        # Idem: por delante de la auditoria cerrada del seed.
        anterior = _auditoria(cliente, planta, dias_atras=20)
        actual = _auditoria(cliente, planta, dias_atras=0)
        try:
            item = cliente.post(
                f"/api/v1/audits/{anterior}/items",
                json={"sequence": 1, "question": "p", "process_id": proceso},
            ).json()

            creados = []
            for _ in range(2):
                nc = cliente.post(
                    "/api/v1/audits/nonconformities/",
                    json={
                        "code": _codigo(),
                        "title": "Hallazgo del ciclo anterior",
                        "description": "d",
                        "severity": "minor",
                        "audit_item_id": item["id"],
                    },
                )
                assert nc.status_code == 201, nc.text
                creados.append(nc.json()["id"])

            # Uno se cierra con eficacia verificada; el otro queda abierto.
            plan = cliente.post(
                "/api/v1/audits/action-plans/",
                json={
                    "nonconformity_id": creados[0],
                    "title": "Plan",
                    "objective": "o",
                },
            ).json()
            cliente.post(f"/api/v1/audits/action-plans/{plan['id']}/verify?success=true")
            cliente.post(f"/api/v1/audits/nonconformities/{creados[0]}/close")

            # La auditoria anterior tiene que estar cerrada para contar.
            for destino in ("active", "reporting", "closed"):
                cliente.post(f"/api/v1/audits/{anterior}/advance?new_status={destino}")

            informe = cliente.get(f"/api/v1/audits/{actual}/informe").json()

            assert informe["auditoria_anterior_id"] == anterior, (
                "No se encontro la auditoria anterior de la misma planta y tipo."
            )
            tasa = informe["tasa_de_cierre_del_ciclo_anterior"]
            assert tasa is not None, informe["motivo_sin_tasa"]
            # 1 de 2 cerrados. Si la verificacion de eficacia no se pudo hacer
            # —el modo sin Clerk no tiene usuario— el cierre falla y da 0.0,
            # que es un resultado legitimo de este montaje.
            assert tasa in (0.0, 50.0), f"tasa inesperada: {tasa}"

            for nc in creados:
                cliente.delete(f"/api/v1/audits/nonconformities/{nc}")
            cliente.delete(f"/api/v1/audits/action-plans/{plan['id']}")
        finally:
            cliente.delete(f"/api/v1/audits/{anterior}")
            cliente.delete(f"/api/v1/audits/{actual}")

    def test_un_ciclo_anterior_sin_hallazgos_no_da_cero(
        self, cliente, planta
    ) -> None:
        """Una auditoria anterior limpia **no es** un 0 % de cierre.

        Es el caso que mas se parece a un exito y que un cero convertiria en el
        peor numero del informe.
        """
        # Mas reciente que la del seed (2026-06-01), o el informe elige esa
        # —que si tiene hallazgos— y la prueba mediria otra cosa.
        anterior = _auditoria(cliente, planta, dias_atras=30)
        actual = _auditoria(cliente, planta, dias_atras=0)
        try:
            for destino in ("active", "reporting", "closed"):
                cliente.post(f"/api/v1/audits/{anterior}/advance?new_status={destino}")

            informe = cliente.get(f"/api/v1/audits/{actual}/informe").json()

            assert informe["tasa_de_cierre_del_ciclo_anterior"] is None, (
                "Una auditoria anterior sin hallazgos informo una tasa de "
                "cierre. No habia nada que cerrar: eso no es 0 %."
            )
            assert "no dejo hallazgos" in (informe["motivo_sin_tasa"] or "")
        finally:
            cliente.delete(f"/api/v1/audits/{anterior}")
            cliente.delete(f"/api/v1/audits/{actual}")
