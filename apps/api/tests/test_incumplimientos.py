"""La vista de lo que se esta incumpliendo (#126, epica #23).

## El agujero que aparecio al construirla

`#126` pide "acceso a evidencias", asi que lo primero fue mirar donde vivia la
evidencia. **No vivia en ningun lado.** Sonda antes de tocar nada:

    POST /compliance/article-compliance/{id}/evaluate?evidence_url=...
    -> 200 OK, y el enlace no quedaba guardado

El viaje estaba conectado por los dos extremos y roto en el medio: el dialogo
pide "Evidencia (Google Drive / OneDrive)", el store la manda como
`evidence_url`, `evaluate_article()` hacia `art.evidence_url = evidence_url`
— y **esa columna no existia**. SQLAlchemy deja asignar atributos sueltos a una
instancia y no los persiste, asi que nada fallaba.

Para quien usa el sistema: pega el enlace, ve "guardado", recarga, y no esta.
Es la peor forma de perder un dato porque nadie se entera hasta que hace falta,
y hace falta justo cuando llega una fiscalizacion.

## Que fijan estas pruebas

Las consultas se **compilan** contra el dialecto de Postgres en vez de
ejecutarse, igual que en `test_dashboard.py`. Eso caza que una columna deje de
existir —el fallo que este modulo acaba de tener— sin depender de que haya una
base levantada.

Lo que se afirma sobre el comportamiento va con filas falsas: **sin evidencia
primero** y los conteos aparte, que es lo que hace util la pantalla.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.services import incumplimientos as svc

TENANT = uuid4()
AHORA = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


class SesionQueCompila:
    """Compila cada sentencia en vez de ejecutarla.

    Las dos consultas del servicio se distinguen por la tabla que aparece en el
    SQL. Devolver la misma lista a las dos haria pasar pruebas que no ejercitan
    nada — o reventar al desempaquetar, que es lo que ya paso en
    `test_dashboard.py` con los dos `GROUP BY`.
    """

    def __init__(self, articulos=None, declaraciones=None):
        self.sql: list[str] = []
        self._articulos = articulos or []
        self._declaraciones = declaraciones or []

    def execute(self, stmt):
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        self.sql.append(sql)
        res = MagicMock()
        res.all.return_value = (
            self._articulos if "article_compliance" in sql else self._declaraciones
        )
        return res


def _articulo(numero="4", evidencia=None, planta="Planta Calama"):
    """Una fila del SELECT de articulos, en el orden en que el servicio la lee."""
    return (
        uuid4(),              # article_compliance_id
        "NORMA DE EMISION",   # norm_title
        numero,               # norm_number
        f"Articulo {numero}", # article_number
        "Limites maximos",    # article_heading
        planta,               # facility_name
        evidencia,            # evidence_url
        "Medicion trimestral",# compliance_method
        None,                 # responsible_user_id
        AHORA,                # assessed_at
        "high",               # risk_level
    )


def _declaracion(codigo="OBL-1", dias_vencida=10, estado="open"):
    return (
        uuid4(),
        codigo,
        "Declaracion SIDREP",
        AHORA - timedelta(days=dias_vencida),
        estado,
        None,
        None,
        "Planta Calama",
    )


class TestLasConsultasSiguenSiendoValidas:
    def test_todas_compilan_contra_postgres(self) -> None:
        """La comprobacion que habria cazado la columna inexistente.

        `evidence_url` no existia en `article_compliance` y el codigo la
        escribia igual. Compilando, una columna fantasma revienta aca en vez de
        al abrir la pantalla.
        """
        db = SesionQueCompila()

        svc.listar(db, TENANT, AHORA)

        assert len(db.sql) == 2, "se esperaban dos consultas"
        assert all("SELECT" in s for s in db.sql)

    def test_la_consulta_de_articulos_SELECCIONA_la_evidencia(self) -> None:
        """Sin esta columna la pantalla no puede enlazar a nada — que es #126.

        **Se mira la proyeccion, no el SQL entero.** La primera version de esta
        prueba buscaba `evidence_url` en toda la sentencia y pasaba con la
        columna quitada del `SELECT`: el `ORDER BY ... evidence_url IS NULL`
        la seguia nombrando. La mutacion la delato.
        """
        db = SesionQueCompila()

        svc.listar(db, TENANT, AHORA)

        articulos = next(s for s in db.sql if "article_compliance" in s)
        proyeccion = articulos.split(chr(10) + "FROM")[0]
        assert "evidence_url" in proyeccion

    def test_los_articulos_sin_planta_no_se_pierden(self) -> None:
        """`facility_id` es nullable: un articulo evaluado a nivel de empresa no
        cuelga de ninguna planta.

        Con un `JOIN` normal esos incumplimientos **desaparecerian de la lista
        sin dejar rastro**, que es la peor forma de perder una fila: la pantalla
        se ve bien y falta algo.
        """
        db = SesionQueCompila()

        svc.listar(db, TENANT, AHORA)

        articulos = next(s for s in db.sql if "article_compliance" in s)
        assert "LEFT OUTER JOIN facilities" in articulos


class TestLaEvidenciaEsElEje:
    def test_lo_que_no_tiene_evidencia_va_primero(self) -> None:
        """Un incumplimiento documentado tiene algo que mostrar; uno sin nada
        deja a la empresa muda ante una fiscalizacion."""
        db = SesionQueCompila()

        svc.listar(db, TENANT, AHORA)

        articulos = next(s for s in db.sql if "article_compliance" in s)
        assert "evidence_url IS NULL DESC" in articulos

    def test_cuenta_aparte_los_que_no_la_tienen(self) -> None:
        """La pantalla no deberia recorrer la lista para saber cuantos son."""
        db = SesionQueCompila(
            articulos=[
                _articulo("4", evidencia=None),
                _articulo("5", evidencia="https://drive.google.com/x"),
                _articulo("6", evidencia=None),
            ]
        )

        r = svc.listar(db, TENANT, AHORA)

        assert r["articles_without_evidence"] == 2

    def test_una_cadena_vacia_cuenta_como_sin_evidencia(self) -> None:
        """Un campo enviado vacio no es una evidencia. Contarlo como tal daria
        por documentado algo que no lo esta."""
        db = SesionQueCompila(articulos=[_articulo("4", evidencia="")])

        assert svc.listar(db, TENANT, AHORA)["articles_without_evidence"] == 1


class TestLasDosListasVanSeparadas:
    def test_articulos_y_declaraciones_no_se_mezclan(self) -> None:
        """Se atienden distinto: uno con un plan de accion, la otra
        presentandola. En una sola lista la urgencia de una tapa la de la otra.
        """
        db = SesionQueCompila(
            articulos=[_articulo("4")],
            declaraciones=[_declaracion()],
        )

        r = svc.listar(db, TENANT, AHORA)

        assert len(r["articles"]) == 1
        assert len(r["declarations"]) == 1

    def test_dice_cuantos_dias_lleva_vencida(self) -> None:
        db = SesionQueCompila(declaraciones=[_declaracion(dias_vencida=17)])

        assert svc.listar(db, TENANT, AHORA)["declarations"][0]["days_overdue"] == 17

    def test_una_declaracion_aceptada_no_es_incumplimiento(self) -> None:
        """Aunque su fecha ya haya pasado: se presento y la aceptaron."""
        db = SesionQueCompila()

        svc.listar(db, TENANT, AHORA)

        declaraciones = next(s for s in db.sql if "obligations" in s)
        assert "NOT IN" in declaraciones.upper()

    def test_el_vencimiento_se_mide_por_fecha_y_no_solo_por_estado(self) -> None:
        """`status = 'overdue'` solo existe si alguien lo escribio, y **hoy nada
        lo hace automaticamente**. Confiar en el estado dejaria fuera todas las
        declaraciones abiertas con la fecha pasada — o sea, casi todas.
        """
        db = SesionQueCompila()

        svc.listar(db, TENANT, AHORA)

        declaraciones = next(s for s in db.sql if "obligations" in s)
        assert "due_at <" in declaraciones


class TestElTopeSeDeclara:
    def test_una_lista_completa_no_se_marca_truncada(self) -> None:
        db = SesionQueCompila(articulos=[_articulo("4")])

        assert svc.listar(db, TENANT, AHORA)["articles_truncated"] is False

    def test_pasado_el_tope_se_corta_Y_SE_DICE(self) -> None:
        """**Truncar en silencio se lee como "esto es todo lo que hay".**

        Sobre incumplimientos esa es justo la lectura que no puede darse: la
        empresa creeria que tiene 200 problemas cuando tiene 400.
        """
        db = SesionQueCompila(articulos=[_articulo(str(i)) for i in range(svc.TOPE + 5)])

        r = svc.listar(db, TENANT, AHORA)

        assert len(r["articles"]) == svc.TOPE
        assert r["articles_truncated"] is True

    def test_el_conteo_sin_evidencia_es_sobre_lo_devuelto(self) -> None:
        """Y no sobre el total sin cortar: seria un numero que no corresponde a
        ninguna lista que la persona pueda ver."""
        db = SesionQueCompila(
            articulos=[_articulo(str(i), evidencia=None) for i in range(svc.TOPE + 5)]
        )

        r = svc.listar(db, TENANT, AHORA)

        assert r["articles_without_evidence"] == svc.TOPE
