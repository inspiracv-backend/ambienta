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
    - `execute(...).all()` da las filas de un GROUP BY — hay dos, con formas
      distintas, y se distinguen por la tabla que aparece en el SQL
    - `execute(...).scalars()` da las obligaciones del DISTINCT ON
    - `scalars(...)` da las plantas
    """

    def __init__(self, obligaciones=None, facilities=None, agrupadas=None, nc_por_planta=None):
        self.sql: list[str] = []
        self._obligaciones = obligaciones or []
        self._facilities = facilities or []
        self._agrupadas = agrupadas or []
        self._nc_por_planta = nc_por_planta or []

    def _compilar(self, stmt) -> str:
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        self.sql.append(sql)
        return sql

    def execute(self, stmt):
        sql = self._compilar(stmt)
        res = MagicMock()
        res.one.return_value = (0, 0, 0)
        # **Hay DOS `GROUP BY` distintos y devuelven formas distintas:**
        # cumplimiento por planta da 4 columnas y no conformidades abiertas da
        # 2. El doble devolvia la misma lista a los dos, asi que una tupla de 4
        # reventaba el segundo con "too many values to unpack" — un fallo que se
        # lee como un error del servicio y es del doble.
        res.all.return_value = (
            self._nc_por_planta if "nonconformities" in sql else self._agrupadas
        )
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


def _planta(nombre: str):
    """Una planta falsa **con su nombre puesto de verdad**.

    `MagicMock(name="X")` NO crea el atributo `name`: `name` es un parametro
    reservado del constructor que bautiza al propio mock. El atributo queda
    siendo otro `MagicMock`, asi que `f["name"] == "Planta Calama"` falla con un
    mensaje que no se parece en nada a la causa.

    Hay que asignarlo despues de construirlo.
    """
    m = MagicMock(id=uuid4())
    m.name = nombre
    return m


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


def test_sin_datos_no_revienta_y_no_acusa():
    """Un tenant recien creado no rompe el tablero **ni sale acusado**.

    ## Esta prueba decia lo contrario, y fijaba el error

    Se llamaba `test_sin_datos_devuelve_ceros_no_nulos` y afirmaba
    `compliance_percentage == 0.0` con el comentario *"muestra 0, no null ni
    error"*. La intencion —que no reviente ni devuelva algo que la pantalla no
    sepa pintar— era buena; el valor elegido para cumplirla, no.

    **Un cero se lee como "no cumple nada".** Medido en el seed: de las tres
    plantas de la empresa 1, dos no tienen una sola evaluacion, y el tablero
    las mostraba en rojo con "0 % de cumplimiento". Es la pantalla que el Admin
    Empresa mira para decidir donde poner recursos.

    ## Dos servicios decidieron distinto sobre el mismo numero

    `services/resumen_cumplimiento.py` ya devolvia `None` en este caso, y lo
    argumenta en su docstring: *"Cero significa 'no cumple nada'; `None`
    significa 'todavia no hay nada que medir'. Mostrar 0 % a una empresa recien
    creada seria una acusacion falsa"*.

    `services/dashboard.py` se escribio aparte y no heredo esa decision. Gana la
    que trae el razonamiento; lo que no puede sostenerse es que el mismo numero
    valga `0.0` en un endpoint y `None` en otro.

    Los conteos **si son cero de verdad**: cero no conformidades abiertas es un
    hecho medido, no una ausencia de datos.
    """
    db = SesionQueCompila()

    g = svc.get_dashboard_metrics(db, TENANT)["global"]

    assert g["compliance_percentage"] is None
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


# ── Que una planta sin evaluar no salga acusada (#125) ────────────────────
#
# **El desglose por planta no tenia ninguna prueba, y ahi estaba el dano real.**
# Medido en el seed antes de arreglarlo: de las tres plantas de la empresa 1,
# dos —Faena Antofagasta y Oficina Santiago— tienen cero evaluaciones de
# articulo, y el endpoint las devolvia con `compliance_percentage: 0.0`.
#
# Lo delato la mutacion: revertir el arreglo por planta **sobrevivia**, porque
# la unica prueba del caso miraba el agregado global.

def test_una_planta_sin_evaluaciones_no_dice_cero():
    """La planta no aparece en el GROUP BY, asi que manda el valor por defecto.

    Ese defecto era `0.0`. Una planta que nadie evaluo no es una planta que
    incumple: son estados distintos y el tablero ejecutivo los pintaba igual.
    """
    planta = _planta("Faena Antofagasta")
    db = SesionQueCompila(facilities=[planta], agrupadas=[])

    metricas = svc.get_dashboard_metrics(db, TENANT)["facilities"]

    assert metricas[0]["compliance_percentage"] is None


def test_una_planta_evaluada_y_sin_nada_cumplido_SI_dice_cero():
    """El otro lado: distinguir "sin datos" no puede tapar el incumplimiento.

    Aca hay cuatro articulos evaluados y ninguno cumplido — el cero es un cero
    medido y tiene que verse como tal.
    """
    planta = _planta("Planta Calama")
    # (facility_id, total, cumplen, incumplen)
    db = SesionQueCompila(facilities=[planta], agrupadas=[(planta.id, 4, 0, 4)])

    metricas = svc.get_dashboard_metrics(db, TENANT)["facilities"]

    assert metricas[0]["compliance_percentage"] == 0.0


def test_el_porcentaje_por_planta_se_calcula_sobre_sus_propios_articulos():
    """Y no sobre el total de la empresa: cada planta responde por lo suyo."""
    planta = _planta("Planta Calama")
    db = SesionQueCompila(facilities=[planta], agrupadas=[(planta.id, 5, 2, 1)])

    metricas = svc.get_dashboard_metrics(db, TENANT)["facilities"]

    assert metricas[0]["compliance_percentage"] == 40.0
    assert metricas[0]["non_compliant_count"] == 1


def test_dos_plantas_una_con_datos_y_otra_sin_ellos():
    """El caso exacto del seed, y el que hay que poder distinguir de un vistazo."""
    con_datos = _planta("Planta Calama")
    sin_datos = _planta("Oficina Santiago")
    db = SesionQueCompila(
        facilities=[con_datos, sin_datos],
        agrupadas=[(con_datos.id, 5, 2, 1)],
    )

    por_nombre = {
        f["name"]: f["compliance_percentage"]
        for f in svc.get_dashboard_metrics(db, TENANT)["facilities"]
    }

    assert por_nombre["Planta Calama"] == 40.0
    assert por_nombre["Oficina Santiago"] is None


def test_una_planta_con_TODO_no_aplicable_tampoco_dice_cero():
    """La planta si aparece en el GROUP BY, pero con denominador cero.

    Es un caso distinto del anterior y por eso necesita su propia prueba: aca
    **si hay evaluaciones**, solo que todas son `not_applicable`, que salen del
    denominador. La fila existe, `total` vale 0, y la division no se puede
    hacer.

    Lo delato una mutacion que sobrevivio: quitar el `if total else None` de
    `_cumplimiento_por_facility` no hacia fallar nada, porque las otras pruebas
    solo cubrian la planta que **no aparece** en el agrupado.

    Cero seria decir que la planta no cumple nada cuando lo que pasa es que no
    le aplica nada. Una minera cuya oficina administrativa tiene todos los
    articulos de emisiones marcados "no aplica" es exactamente este caso.
    """
    planta = _planta("Oficina Santiago")
    # (facility_id, total_aplicable, cumplen, incumplen) — todo no aplicable
    db = SesionQueCompila(facilities=[planta], agrupadas=[(planta.id, 0, 0, 0)])

    metricas = svc.get_dashboard_metrics(db, TENANT)["facilities"]

    assert metricas[0]["compliance_percentage"] is None
