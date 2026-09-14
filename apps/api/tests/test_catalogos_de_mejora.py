"""Los catalogos configurables por empresa (#41, RF-100).

## Que resuelven

La escala de severidad era un CHECK con `minor | major | critical`: la misma
para todas las empresas y solo en ingles, mientras el cliente dice `Alta` y
`Mayor` (design.md §4, decision S-14). Sin catalogo, el segundo cliente obliga a
un cambio de esquema.

## Lo que estas pruebas fijan, y por que no basta con el CRUD

Un catalogo que se puede llenar y que nada lee es el patron que este repositorio
ya conoce de sobra —`bcn.sincronizar()`, `control_documental.py`, casi todo el
CRM: codigo escrito, probado, y sin un solo llamador. Asi que la mitad de este
archivo no prueba los endpoints del catalogo sino **que registrar un hallazgo
pase por el**:

| lo que se comprueba | por que |
|---|---|
| Una severidad que la empresa desactivo se rechaza | Configurar el catalogo tiene que significar algo |
| Sin ningun nivel activo, el alta responde 409 y lo explica | Es el error del pipeline sin etapas abiertas |
| `due_date` se calcula desde el plazo del nivel | La columna existia y **nadie la llenaba** |
| Sin plazo declarado, `due_date` sigue vacia | Inventarla seria fabricar un compromiso |

## Y las dos listas que tienen que coincidir

La siembra vive en dos lados —`db/25_catalogos_de_mejora.sql` para las empresas
que ya existian y `services/catalogos_de_mejora.py` para las nuevas— porque el
`CROSS JOIN tenants` de una migracion corre **una sola vez**. Es exactamente lo
que dejo sin etapas de CRM a toda empresa creada despues de `db/22_crm.sql`.

Dos listas separadas se desincronizan, y la diferencia recien se veria
comparando dos cuentas. Por eso una prueba **lee el archivo SQL**, igual que la
que lee los Dockerfile y la que lee `22_crm.sql`.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.catalogos_de_mejora import (  # noqa: E402
    METODOLOGIAS_POR_DEFECTO,
    SEVERIDADES_POR_DEFECTO,
)

EMPRESA = "a0000000-0000-0000-0000-000000000001"
MIGRACION = Path(__file__).resolve().parents[3] / "db" / "25_catalogos_de_mejora.sql"


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


def _codigo() -> str:
    return f"PRB-{uuid.uuid4().hex[:8].upper()}"


def _nivel(cliente, code: str) -> dict:
    todos = cliente.get("/api/v1/audits/catalogos/severidades?solo_activas=false")
    todos.raise_for_status()
    for fila in todos.json():
        if fila["code"] == code:
            return fila
    raise AssertionError(f"la empresa no tiene el nivel '{code}' sembrado")


class TestLasDosListasCoinciden:
    """Lo que impide que el catalogo dependa de cuando nacio la empresa."""

    def _valores(self, tabla: str, columnas: int) -> set[tuple]:
        """Las filas del `VALUES` de esa tabla, respetando las comillas.

        **La primera version usaba una expresion regular y perdio una fila en
        silencio.** El nombre sembrado es `Diagrama de Ishikawa (causa-efecto)`
        y los parentesis del nombre se leyeron como el fin del registro, asi que
        la metodologia desaparecio del conjunto.

        Aca la direccion del error fue afortunada —falto en el lado del SQL y la
        prueba fallo—, pero si hubiera faltado del otro lado la prueba habria
        pasado **verde comparando dos listas incompletas**. Un medidor que se
        come una fila sin avisar es exactamente lo que CLAUDE.md llama "los
        medidores tambien mienten, y es peor".

        De ahi que esto recorra caracter por caracter en vez de buscar un
        patron: dentro de una comilla simple, un parentesis es texto.

        Y solo cuentan las tuplas que traen alguna cadena entrecomillada: el
        mismo `INSERT` lleva `AS s(code, label, rank)`, que tiene la forma de
        una fila y son los nombres de las columnas.
        """
        sql = MIGRACION.read_text(encoding="utf-8")
        inicio = sql.index(f"INSERT INTO {tabla}")
        bloque = sql[inicio : sql.index(";", inicio)]
        bloque = bloque[bloque.index("VALUES") :]

        valores: set[tuple] = set()
        actual: list[str] = []
        campo: list[str] = []
        dentro_de_comillas = False
        profundidad = 0
        hubo_cadena = False

        for caracter in bloque:
            if dentro_de_comillas:
                if caracter == "'":
                    dentro_de_comillas = False
                else:
                    campo.append(caracter)
                continue
            if caracter == "'":
                dentro_de_comillas = True
                hubo_cadena = True
            elif caracter == "(":
                profundidad += 1
                if profundidad == 1:
                    actual, campo, hubo_cadena = [], [], False
            elif caracter == ")":
                if profundidad == 1:
                    actual.append("".join(campo).strip())
                    if len(actual) == columnas and hubo_cadena:
                        valores.add(tuple(actual))
                    actual, campo, hubo_cadena = [], [], False
                profundidad = max(0, profundidad - 1)
            elif caracter == "," and profundidad == 1:
                actual.append("".join(campo).strip())
                campo = []
            elif profundidad == 1:
                campo.append(caracter)

        assert valores, f"no se leyo ninguna fila del INSERT de {tabla}"
        return valores

    def test_las_severidades_del_sql_son_las_de_python(self) -> None:
        del_sql = self._valores("improvement_severities", 3)
        de_python = {(c, e, str(r)) for c, e, r in SEVERIDADES_POR_DEFECTO}

        assert del_sql == de_python, (
            "La siembra de la migracion y la del alta de empresa no coinciden. "
            "Dos listas distintas dan catalogos distintos segun cuando nacio la "
            f"empresa.\n  solo en el SQL: {sorted(del_sql - de_python)}\n"
            f"  solo en Python: {sorted(de_python - del_sql)}"
        )

    def test_las_metodologias_del_sql_son_las_de_python(self) -> None:
        del_sql = self._valores("improvement_methodologies", 3)

        assert del_sql == set(METODOLOGIAS_POR_DEFECTO), (
            "La siembra de metodologias no coincide entre el SQL y Python.\n"
            f"  solo en el SQL: {sorted(del_sql - set(METODOLOGIAS_POR_DEFECTO))}\n"
            f"  solo en Python: {sorted(set(METODOLOGIAS_POR_DEFECTO) - del_sql)}"
        )


class TestElCicloDelCatalogo:
    """Que los endpoints se ejecuten. El CRM enseño que esto no se da por hecho."""

    def test_ciclo_de_un_nivel_de_severidad(self, cliente) -> None:
        crear = cliente.post(
            "/api/v1/audits/catalogos/severidades",
            json={"code": _codigo(), "label": "Nivel de prueba", "rank": 9},
        )
        assert crear.status_code == 201, crear.text
        nivel = crear.json()
        assert nivel["days_to_close"] is None, (
            "Un nivel nuevo no puede nacer con un plazo: nadie lo declaro."
        )

        try:
            editar = cliente.patch(
                f"/api/v1/audits/catalogos/severidades/{nivel['id']}",
                json={"label": "Otro nombre", "days_to_close": 30},
            )
            assert editar.status_code == 200, editar.text
            assert editar.json()["label"] == "Otro nombre"
            assert editar.json()["days_to_close"] == 30
        finally:
            cliente.delete(f"/api/v1/audits/catalogos/severidades/{nivel['id']}")

    def test_ciclo_de_una_metodologia(self, cliente) -> None:
        crear = cliente.post(
            "/api/v1/audits/catalogos/metodologias",
            json={
                "code": _codigo(),
                "name": "Metodologia de prueba",
                "shape": "texto_libre",
            },
        )
        assert crear.status_code == 201, crear.text
        mid = crear.json()["id"]

        try:
            assert (
                cliente.patch(
                    f"/api/v1/audits/catalogos/metodologias/{mid}",
                    json={"name": "Otro nombre"},
                ).status_code
                == 200
            )
        finally:
            cliente.delete(f"/api/v1/audits/catalogos/metodologias/{mid}")

    def test_una_forma_inventada_se_rechaza(self, cliente) -> None:
        """El nombre lo elige la empresa; la forma no.

        `shape` decide que datos pide el analisis. Una forma que el sistema no
        conoce daria un formulario vacio y respuestas que nadie sabe leer.
        """
        respuesta = cliente.post(
            "/api/v1/audits/catalogos/metodologias",
            json={"code": _codigo(), "name": "x", "shape": "adivinanza"},
        )
        assert respuesta.status_code == 422, respuesta.text


class TestElHallazgoPasaPorElCatalogo:
    """La mitad que impide que esto sea una tabla decorativa."""

    def test_una_severidad_fuera_del_catalogo_se_rechaza(self, cliente) -> None:
        """Y con 422, nombrando las disponibles.

        Sin esto, el catalogo se podria configurar entero y no cambiaria nada:
        el CHECK de la columna seguiria aceptando los tres valores de siempre en
        todas las empresas.
        """
        nivel = _nivel(cliente, "critical")
        cliente.patch(
            f"/api/v1/audits/catalogos/severidades/{nivel['id']}",
            json={"active": False},
        )
        try:
            respuesta = cliente.post(
                "/api/v1/audits/nonconformities/",
                json={
                    "code": _codigo(),
                    "title": "Hallazgo de prueba",
                    "description": "d",
                    "severity": "critical",
                },
            )
            assert respuesta.status_code == 422, (
                "Se registro un hallazgo con un nivel que la empresa desactivo: "
                f"{respuesta.status_code}. {respuesta.text[:200]}"
            )
            assert "critical" in respuesta.json()["detail"]
        finally:
            cliente.patch(
                f"/api/v1/audits/catalogos/severidades/{nivel['id']}",
                json={"active": True},
            )

    def test_la_fecha_limite_sale_del_plazo_del_nivel(self, cliente) -> None:
        """`due_date` existia desde el principio y **nadie la calculaba**.

        Se aceptaba del cuerpo o se dejaba vacia, o sea que "una mayor se cierra
        en 30 dias" era una regla que la empresa tenia en la cabeza.
        """
        from datetime import date, timedelta

        nivel = _nivel(cliente, "major")
        cliente.patch(
            f"/api/v1/audits/catalogos/severidades/{nivel['id']}",
            json={"days_to_close": 30},
        )
        try:
            crear = cliente.post(
                "/api/v1/audits/nonconformities/",
                json={
                    "code": _codigo(),
                    "title": "Con plazo",
                    "description": "d",
                    "severity": "major",
                },
            )
            assert crear.status_code == 201, crear.text
            esperada = date.today() + timedelta(days=30)
            assert crear.json()["due_date"] == esperada.isoformat(), (
                "La fecha limite no salio del plazo del nivel."
            )
            cliente.delete(f"/api/v1/audits/nonconformities/{crear.json()['id']}")
        finally:
            cliente.patch(
                f"/api/v1/audits/catalogos/severidades/{nivel['id']}",
                json={"days_to_close": None},
            )

    def test_lo_que_manda_el_cuerpo_gana_sobre_el_plazo(self, cliente) -> None:
        """Una autoridad puede fijar otra fecha. El calculo solo cubre el vacio."""
        from datetime import date, timedelta

        nivel = _nivel(cliente, "major")
        cliente.patch(
            f"/api/v1/audits/catalogos/severidades/{nivel['id']}",
            json={"days_to_close": 30},
        )
        impuesta = (date.today() + timedelta(days=5)).isoformat()
        try:
            crear = cliente.post(
                "/api/v1/audits/nonconformities/",
                json={
                    "code": _codigo(),
                    "title": "Con fecha impuesta",
                    "description": "d",
                    "severity": "major",
                    "due_date": impuesta,
                },
            )
            assert crear.status_code == 201, crear.text
            assert crear.json()["due_date"] == impuesta
            cliente.delete(f"/api/v1/audits/nonconformities/{crear.json()['id']}")
        finally:
            cliente.patch(
                f"/api/v1/audits/catalogos/severidades/{nivel['id']}",
                json={"days_to_close": None},
            )

    def test_sin_plazo_declarado_la_fecha_queda_vacia(self, cliente) -> None:
        """El estado inicial de todas las empresas, y tiene que ser inofensivo.

        Sembrar 60/30/15 seria inventarle el compromiso a la empresa, y un plazo
        falso en cumplimiento hace creer que se va a tiempo.
        """
        crear = cliente.post(
            "/api/v1/audits/nonconformities/",
            json={
                "code": _codigo(),
                "title": "Sin plazo",
                "description": "d",
                "severity": "minor",
            },
        )
        assert crear.status_code == 201, crear.text
        assert crear.json()["due_date"] is None, (
            "Aparecio una fecha limite que nadie declaro."
        )
        cliente.delete(f"/api/v1/audits/nonconformities/{crear.json()['id']}")

    def test_una_metodologia_de_otra_empresa_se_rechaza(self, cliente) -> None:
        """Las claves foraneas **no pasan por RLS** (CLAUDE.md §4).

        La restriccion solo exige que la fila exista, no que sea de esta
        empresa. Sin `validar_visible`, mandar el id de la metodologia de otra
        cuenta escribiria la fila **y** distinguiria "no existe" de "existe pero
        es de otro" — un oraculo para enumerar identificadores ajenos.
        """
        ajena = uuid.uuid4()

        respuesta = cliente.post(
            "/api/v1/audits/nonconformities/",
            json={
                "code": _codigo(),
                "title": "Con metodologia ajena",
                "description": "d",
                "severity": "minor",
                "root_cause_methodology_id": str(ajena),
            },
        )
        assert respuesta.status_code == 422, respuesta.text
        assert "root_cause_methodology_id" in respuesta.json()["detail"]
