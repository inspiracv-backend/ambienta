"""Metricas del Dashboard, sin base de datos levantada.

La pieza central es `test_todas_las_consultas_compilan`: recorre el servicio
con una sesion falsa que compila cada sentencia contra el dialecto de Postgres
en vez de ejecutarla. Eso detecta que una columna dejo de existir, que es
exactamente el fallo que tuvo este modulo al escribirse — se uso
`compliance_answer` cuando la columna real es `compliance_status`, y sin este
test habria salido recien al abrir el Dashboard.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services import dashboard as svc

TENANT = uuid4()


class SesionQueCompila:
    """Compila cada sentencia en vez de ejecutarla.

    No hereda de Session a proposito: solo necesita responder a `execute` y
    `scalars`, que es todo lo que el servicio usa.

    El servicio lee de cuatro formas distintas y este doble las distingue,
    porque confundirlas hace pasar tests que en realidad no ejercitan nada:

    - `execute(...).one()` da los contadores agregados
    - `execute(...).all()` da las filas de un GROUP BY
    - `execute(...).scalars()` da las obligaciones del DISTINCT ON
    - `scalars(...)` da las plantas
    """

    def __init__(self, obligaciones=None, facilities=None, agrupadas=None):
        self.sql: list[str] = []
        self._obligaciones = obligaciones or []
        self._facilities = facilities or []
        self._agrupadas = agrupadas or []

    def _compilar(self, stmt) -> None:
        self.sql.append(str(stmt.compile(dialect=postgresql.dialect())))

    def execute(self, stmt):
        self._compilar(stmt)
        res = MagicMock()
        res.one.return_value = (0, 0, 0)
        res.all.return_value = self._agrupadas
        res.scalars.return_value.all.return_value = self._obligaciones
        return res

    def scalars(self, stmt):
        self._compilar(stmt)
        res = MagicMock()
        res.all.return_value = self._facilities
        return res


def _obligacion(dias: int, titulo: str, facility_id=None):
    o = MagicMock()
    o.id = uuid4()
    o.code = f"OBL-{titulo}"
    o.title = titulo
    o.due_at = datetime.now(timezone.utc) + timedelta(days=dias)
    o.status = "open"
    o.facility_id = facility_id
    return o


# --- Regresion de columnas ---------------------------------------------------


def test_todas_las_consultas_compilan():
    """Si una columna del modelo cambia de nombre, esto falla aca y no en produccion."""
    db = SesionQueCompila()

    svc.get_dashboard_metrics(db, TENANT)

    assert len(db.sql) == 6, "el dashboard deberia resolverse en 6 consultas"


def test_no_hay_n_mas_uno_por_planta():
    """Cinco plantas no deben costar mas consultas que una.

    El design pide agregacion en la base; si alguien vuelve a un bucle por
    planta, el numero de consultas deja de ser constante y esto lo delata.
    """
    plantas = [MagicMock(id=uuid4(), name=f"Planta {i}") for i in range(5)]
    db = SesionQueCompila(facilities=plantas)

    svc.get_dashboard_metrics(db, TENANT)

    assert len(db.sql) == 6


def test_los_contadores_van_en_una_sola_consulta():
    db = SesionQueCompila()

    svc.get_dashboard_metrics(db, TENANT)

    contadores = db.sql[0]
    assert contadores.count("FROM obligations") == 1
    # Tres agregados con FILTER: total, por vencer y vencidas.
    assert contadores.count("FILTER (WHERE") == 2  # el total no lleva filtro


def test_el_filtro_por_planta_llega_al_sql():
    fid = uuid4()
    db = SesionQueCompila()

    svc.get_dashboard_metrics(db, TENANT, facility_id=fid)

    assert "obligations.facility_id" in db.sql[0]


# --- Forma de la respuesta ---------------------------------------------------


def test_forma_de_la_respuesta():
    db = SesionQueCompila()

    res = svc.get_dashboard_metrics(db, TENANT)

    assert set(res) == {
        "tenant_id",
        "generated_at",
        "global",
        "critical_deadline",
        "upcoming_deadlines",
        "facilities",
    }
    assert set(res["global"]) == {
        "compliance_percentage",
        "articles_evaluated",
        "articles_non_compliant",
        "total_obligations",
        "nc_open",
        "obligations_upcoming",
        "obligations_overdue",
    }


def test_sin_datos_devuelve_ceros_no_nulos():
    """Un tenant recien creado muestra 0, no null ni error."""
    db = SesionQueCompila()

    g = svc.get_dashboard_metrics(db, TENANT)["global"]

    assert g["compliance_percentage"] == 0.0
    assert g["nc_open"] == 0
    assert g["total_obligations"] == 0


def test_sin_obligaciones_no_hay_vencimiento_critico():
    db = SesionQueCompila()

    assert svc.get_dashboard_metrics(db, TENANT)["critical_deadline"] is None


# --- Eleccion del vencimiento critico ---------------------------------------


def test_el_critico_es_el_mas_proximo_entre_todas_las_plantas():
    p1, p2 = uuid4(), uuid4()
    db = SesionQueCompila(
        obligaciones=[
            _obligacion(30, "Lejana", p1),
            _obligacion(3, "Urgente", p2),
            _obligacion(12, "Media", None),
        ]
    )

    critico = svc.get_dashboard_metrics(db, TENANT)["critical_deadline"]

    assert critico["title"] == "Urgente"
    assert critico["days_remaining"] == 3


def test_una_obligacion_vencida_da_dias_negativos():
    """Vencida hace una semana debe leerse como negativo, no como 0 ni None."""
    db = SesionQueCompila(obligaciones=[_obligacion(-7, "Atrasada")])

    critico = svc.get_dashboard_metrics(db, TENANT)["critical_deadline"]

    assert critico["days_remaining"] < 0


# --- Estados que cuentan -----------------------------------------------------


def test_una_obligacion_aceptada_o_cerrada_no_cuenta_como_pendiente():
    assert "accepted" in svc.OBLIGACION_RESUELTA
    assert "closed" in svc.OBLIGACION_RESUELTA


@pytest.mark.parametrize("estado", ["draft", "open", "in_progress", "submitted", "rejected", "overdue"])
def test_el_resto_de_estados_sigue_pendiente(estado):
    """`in_progress` y `submitted` son los que el servicio viejo perdia."""
    assert estado not in svc.OBLIGACION_RESUELTA


def test_una_nc_cerrada_o_rechazada_no_cuenta_como_abierta():
    assert set(svc.NC_RESUELTA) == {"closed", "rejected"}


@pytest.mark.parametrize("estado", ["open", "analysis", "action_plan", "verification"])
def test_el_resto_de_estados_de_nc_sigue_abierto(estado):
    assert estado not in svc.NC_RESUELTA


def test_dias_restantes_redondea_hacia_arriba():
    """20 horas es "1 dia", no "0". Debe coincidir con el Math.ceil del front."""
    ahora = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)

    assert svc._dias_restantes(ahora + timedelta(hours=20), ahora) == 1
    assert svc._dias_restantes(ahora + timedelta(days=3), ahora) == 3
    assert svc._dias_restantes(ahora + timedelta(days=2, hours=23), ahora) == 3
    # Vencida hace 6 dias y medio: -6, no -7.
    assert svc._dias_restantes(ahora - timedelta(days=6, hours=12), ahora) == -6


def test_los_proximos_vienen_ordenados_y_topeados_en_cinco():
    """La lista de S-06 sale de las mismas filas que el critico, sin consulta extra."""
    db = SesionQueCompila(
        obligaciones=[_obligacion(d, f"Obl {d}", uuid4()) for d in (40, 5, 20, 60, 1, 90, 15)]
    )

    res = svc.get_dashboard_metrics(db, TENANT)

    assert len(db.sql) == 6, "no debe costar una consulta adicional"
    assert len(res["upcoming_deadlines"]) == 5
    fechas = [p["due_at"] for p in res["upcoming_deadlines"]]
    assert fechas == sorted(fechas)
    # El primero de la lista es el mismo que el critico.
    assert res["upcoming_deadlines"][0]["title"] == res["critical_deadline"]["title"]


def test_una_obligacion_sin_fecha_no_entra_en_la_lista():
    sin_fecha = _obligacion(10, "Sin fecha")
    sin_fecha.due_at = None
    db = SesionQueCompila(obligaciones=[sin_fecha])

    res = svc.get_dashboard_metrics(db, TENANT)

    assert res["upcoming_deadlines"] == []
