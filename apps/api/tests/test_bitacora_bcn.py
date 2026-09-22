"""La bitacora de la sincronizacion con la BCN, y que un fallo no borre lo anterior.

Sin salir a internet: `bcn.buscar` y `bcn.sincronizar` se simulan. Lo que se
mide es la tarea (`app/tareas/sincronizar_bcn.py`), no la BCN.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services import bcn
from app.tareas import sincronizar_bcn as tarea

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible: {exc}")
    s = Session(bind=conexion)
    s.execute(text("CREATE TEMP TABLE marcas_de_termino (termino text)"))
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


@pytest.fixture
def bcn_simulada(monkeypatch):
    """Cada termino "encuentra" su norma, y guardar deja una marca por termino."""
    fallar_en: set[str] = set()

    def buscar(termino, limite=5):
        numero = dict(tarea.TERMINOS)[termino]
        return [SimpleNamespace(numero=numero, termino=termino)]

    def sincronizar(db, normas, con_texto=True):
        termino = normas[0].termino
        db.execute(text("INSERT INTO marcas_de_termino VALUES (:t)"), {"t": termino})
        if termino in fallar_en:
            raise RuntimeError("fallo simulado al guardar")
        return SimpleNamespace(
            nuevas=1, actualizadas=0, adoptadas=0, versiones_nuevas=2,
            articulos_nuevos=3, con_texto=1, con_version_nueva=[],
        )

    monkeypatch.setattr(bcn, "buscar", buscar)
    monkeypatch.setattr(bcn, "sincronizar", sincronizar)
    # Las relaciones entre normas tambien salen a la BCN: aca no traen nada.
    monkeypatch.setattr(bcn, "relaciones_de", lambda uri: [])
    return fallar_en


def _corridas(db):
    return db.execute(
        text("SELECT status, norms_created, versions_created, error_detail FROM norm_sync_runs "
             "WHERE started_at >= now() - interval '1 minute' ORDER BY id")
    ).all()


def test_una_corrida_completa_queda_en_la_bitacora(db, bcn_simulada) -> None:
    antes = len(_corridas(db))
    informe = tarea.sincronizar(db)

    corridas = _corridas(db)
    assert len(corridas) == antes + 1, "la corrida no quedo registrada"
    ultima = corridas[-1]
    assert ultima.status == "success"
    assert ultima.norms_created == informe.nuevas == len(tarea.TERMINOS)
    assert ultima.versions_created == 2 * len(tarea.TERMINOS)
    assert ultima.error_detail is None


def test_un_termino_que_falla_no_borra_los_anteriores(db, bcn_simulada) -> None:
    """El `db.rollback()` de antes deshacia la transaccion entera."""
    primero, segundo = tarea.TERMINOS[0][0], tarea.TERMINOS[1][0]
    bcn_simulada.add(segundo)

    tarea.sincronizar(db)

    marcas = {r[0] for r in db.execute(text("SELECT termino FROM marcas_de_termino"))}
    assert primero in marcas, "lo guardado por el termino anterior se perdio con el fallo"
    assert segundo not in marcas, "lo del termino que fallo no se deshizo"
    assert _corridas(db)[-1].status == "partial"


def test_en_seco_no_deja_corrida(db, bcn_simulada) -> None:
    antes = len(_corridas(db))
    tarea.sincronizar(db, en_seco=True)
    assert len(_corridas(db)) == antes


def test_estado_de() -> None:
    n = len(tarea.TERMINOS)
    assert tarea.estado_de(tarea.Informe(terminos=n)) == "success"
    assert tarea.estado_de(tarea.Informe(terminos=n, sin_su_norma=["x"])) == "partial"
    assert tarea.estado_de(tarea.Informe(terminos=n, errores=["x"] * n)) == "failed"
