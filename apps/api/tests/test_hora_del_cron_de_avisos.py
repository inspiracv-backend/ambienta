"""La hora a la que corre el cron no puede cambiar a quien se le avisa.

## Que estaba roto

`generar()` buscaba las obligaciones dentro de una banda de **+-12 h** alrededor
de `ahora + N dias`. Un plazo legal vence a las **23:59** del dia, y el cron esta
configurado a las **07:00** (`HORA_AVISOS` en `docker-compose.prod.yml`). Entre
los dos hay 17 horas: fuera de la banda.

Medido el 4-sep, con una obligacion que vence a las 23:59:

| hora del cron | avisos, en cualquiera de las cuatro ventanas |
|---|---|
| **07:00 — la configurada** | **0** |
| 12:00, 18:00, 23:00 | 2 |

O sea que el sistema, tal como estaba para desplegarse, **no habria avisado
nunca**, y no habria fallado nada: la corrida informa "0 avisos nuevos", que es
exactamente lo que informa un dia en que de verdad no vence nada.

Doce horas parecen una precaucion razonable y cubren medio dia. El medio que
quedaba afuera era el de la mañana, que es cuando uno quiere que salga el aviso.

## Por que estas pruebas barren la hora

Una sola prueba a mediodia pasa con el codigo roto. Lo que hay que fijar no es
que el generador funcione, sino que **funcione igual a cualquier hora**, porque
la hora es configuracion y se cambia sin mirar esto.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from sqlalchemy import text  # noqa: E402

from app.services.avisos_de_vencimiento import (  # noqa: E402
    VENTANAS_POR_DEFECTO,
    generar,
    huso_de,
)

EMPRESA = "a0000000-0000-0000-0000-000000000001"
#: **`ZoneInfo` y no un desfase fijo.** Chile cambia de hora a comienzos de
#: septiembre: escrito como `-03` fijo, esta prueba fallaba sola durante los
#: dias del cambio y el error se leia como un defecto del generador. Es el
#: mismo motivo por el que el generador consulta el huso en vez de suponerlo.
CHILE = ZoneInfo("America/Santiago")

#: Incluye la hora a la que esta configurado el cron y las tres esquinas del
#: dia. La primera es la que fallaba.
HORAS = (7, 0, 12, 23)


@pytest.fixture
def sesion():
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible ({exc}). Hace falta docker compose.")

    from app.db import SessionLocal
    from app.deps import declarar

    db = SessionLocal()
    declarar(db, EMPRESA)
    try:
        yield db
    finally:
        # Nada de esto se confirma: la prueba mueve fechas de las obligaciones
        # sembradas y dejarlas movidas cambiaria lo que ve la demostracion.
        db.rollback()
        db.close()


def _obligacion_que_vence(db, *, dentro_de_dias: int, a_las: int, minuto: int) -> None:
    """Deja UNA obligacion venciendo ese dia a esa hora, y ninguna otra."""
    vence = (datetime.now(CHILE) + timedelta(days=dentro_de_dias)).replace(
        hour=a_las, minute=minuto, second=0, microsecond=0
    )
    db.execute(
        text(
            "UPDATE obligations SET due_at = :lejos "
            "WHERE tenant_id = :t AND deleted_at IS NULL"
        ),
        {"lejos": datetime.now(CHILE) + timedelta(days=900), "t": EMPRESA},
    )
    db.execute(
        text(
            "UPDATE obligations SET due_at = :v, status = 'open' "
            "WHERE code = 'OBL-REP-NFU-2026'"
        ),
        {"v": vence},
    )
    db.execute(text("DELETE FROM notifications WHERE tenant_id = :t"), {"t": EMPRESA})
    db.flush()


@pytest.mark.parametrize("hora_del_cron", HORAS)
@pytest.mark.parametrize("dias", VENTANAS_POR_DEFECTO)
def test_un_vencimiento_a_fin_del_dia_avisa_corra_a_la_hora_que_corra(
    sesion, hora_del_cron: int, dias: int
) -> None:
    """23:59 es la hora a la que vence un plazo legal, no un caso raro."""
    _obligacion_que_vence(sesion, dentro_de_dias=dias, a_las=23, minuto=59)
    ahora = datetime.now(CHILE).replace(
        hour=hora_del_cron, minute=0, second=0, microsecond=0
    )

    resultado = generar(sesion, EMPRESA, ahora=ahora, ventanas=(dias,))

    assert resultado.creados > 0, (
        f"Con el cron a las {hora_del_cron:02d}:00 y la obligacion venciendo en "
        f"{dias} dias a las 23:59, no se creo ningun aviso. La hora a la que "
        "corre el cron no puede decidir si alguien se entera de que vence algo."
    )


@pytest.mark.parametrize("hora_del_vencimiento", (0, 9, 23))
def test_tampoco_importa_a_que_hora_del_dia_vence(
    sesion, hora_del_vencimiento: int
) -> None:
    """La otra mitad: el cron a su hora fija y el vencimiento moviendose."""
    _obligacion_que_vence(sesion, dentro_de_dias=7, a_las=hora_del_vencimiento, minuto=0)
    ahora = datetime.now(CHILE).replace(hour=7, minute=0, second=0, microsecond=0)

    resultado = generar(sesion, EMPRESA, ahora=ahora, ventanas=(7,))

    assert resultado.creados > 0, (
        f"Un vencimiento a las {hora_del_vencimiento:02d}:00 no genero aviso con "
        "el cron a las 07:00."
    )


def test_un_vencimiento_no_cae_en_dos_ventanas(sesion) -> None:
    """Lo que protege de 'arreglarlo' ensanchando el margen.

    Con una banda de 24 h, el mismo vencimiento entraria en la ventana de 7 y en
    la de 8 —o en la de 1 y la de 2— y la persona recibiria dos correos por lo
    mismo. La deduplicacion no los frena: la clave lleva los dias.
    """
    _obligacion_que_vence(sesion, dentro_de_dias=7, a_las=23, minuto=59)
    ahora = datetime.now(CHILE).replace(hour=7, minute=0, second=0, microsecond=0)

    de_siete = generar(sesion, EMPRESA, ahora=ahora, ventanas=(7,))
    assert de_siete.creados > 0

    sesion.execute(text("DELETE FROM notifications WHERE tenant_id = :t"), {"t": EMPRESA})
    sesion.flush()

    for vecina in (6, 8):
        vecino = generar(sesion, EMPRESA, ahora=ahora, ventanas=(vecina,))
        assert vecino.creados == 0, (
            f"Un vencimiento a 7 dias tambien entro en la ventana de {vecina}. "
            "Cada vencimiento tiene que caer en una sola."
        )


def test_el_huso_sale_del_pais_de_la_empresa(sesion) -> None:
    """No es una constante disfrazada: `countries` tiene cinco husos.

    Es el huso el que decide en que dia del calendario cae un vencimiento de fin
    de dia, asi que tomarlo del servidor —o fijarlo en Chile para todos— daria
    avisos corridos un dia para una empresa de otro pais.
    """
    assert huso_de(sesion, EMPRESA) == "America/Santiago"

    distintos = sesion.execute(
        text("SELECT count(DISTINCT default_timezone) FROM countries")
    ).scalar_one()
    assert distintos > 1, (
        "Si todos los paises compartieran huso, esta funcion sobraria. Tienen "
        f"{distintos} distintos."
    )
