"""La rotacion mensual del registro de actividades.

**Esta tarea borra datos.** Lo que hay que proteger no es que archive —eso se ve
enseguida— sino que **nunca borre algo que no quedo guardado**. Un fallo ahi es
silencioso y definitivo: la tabla queda prolija, el archivo no existe, y nadie
se entera hasta la auditoria en la que hacia falta.

Por eso las pruebas atacan el orden de las operaciones y los limites del rango,
que son los dos lugares donde se pierde informacion sin ruido.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.tareas.rotar_auditoria import mes_anterior, rotar

#: Se conecta con el **dueno** de la base, no con `ambienta_app`: la aplicacion
#: no puede borrar de `audit_log` a proposito, y esta tarea si.
URL = os.getenv(
    "DATABASE_ADMIN_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
)
TENANT = uuid.UUID("a0000000-0000-0000-0000-000000000001")
OTRA = uuid.UUID("a0000000-0000-0000-0000-000000000002")


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    try:
        yield sesion
    finally:
        # Rollback siempre: estas pruebas escriben y borran del registro real.
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _evento(db: Session, tenant_id: uuid.UUID, cuando: str) -> int:
    return db.execute(
        text(
            "INSERT INTO audit_log (tenant_id, occurred_at, action, entity_type) "
            "VALUES (:t, :c, 'update', 'tenant') RETURNING id"
        ),
        {"t": tenant_id, "c": cuando},
    ).scalar_one()


def _quedan(db: Session, ids: list[int]) -> int:
    return db.execute(
        text("SELECT count(*) FROM audit_log WHERE id = ANY(:i)"), {"i": ids}
    ).scalar_one()


class TestArchivaYPurga:
    def test_escribe_un_archivo_por_empresa(self, db: Session, tmp_path) -> None:
        """El negocio lo pidio "por cliente", y ademas es lo correcto: el
        registro de una empresa no puede viajar mezclado con el de otra."""
        _evento(db, TENANT, "2099-03-05")
        _evento(db, OTRA, "2099-03-06")

        r = rotar(db, desde=date(2099, 3, 1), hasta=date(2099, 4, 1), destino=tmp_path)

        assert len(r.por_empresa) == 2
        archivos = sorted(p.name for p in tmp_path.glob("*.json"))
        assert len(archivos) == 2
        # Cada archivo lleva el id de su empresa en el nombre: entregarlo no
        # exige abrirlo para saber de quien es.
        assert all(str(TENANT) in a or str(OTRA) in a for a in archivos)

    def test_el_archivo_contiene_las_filas_y_se_puede_releer(
        self, db: Session, tmp_path
    ) -> None:
        """"Para cuando se pueda subir de nuevo": las columnas van con el mismo
        nombre que en la tabla, asi que reinsertarlo no exige transformar."""
        eid = _evento(db, TENANT, "2099-03-05")

        rotar(db, desde=date(2099, 3, 1), hasta=date(2099, 4, 1), destino=tmp_path)

        datos = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
        assert datos["filas"] == 1
        assert datos["tenant_id"] == str(TENANT)
        registro = datos["registros"][0]
        assert registro["id"] == eid
        assert {"tenant_id", "occurred_at", "action", "entity_type"} <= set(registro)

    def test_borra_lo_que_archivo(self, db: Session, tmp_path) -> None:
        ids = [_evento(db, TENANT, "2099-03-05"), _evento(db, TENANT, "2099-03-20")]

        r = rotar(db, desde=date(2099, 3, 1), hasta=date(2099, 4, 1), destino=tmp_path)

        assert r.filas_archivadas == 2
        assert r.filas_borradas == 2
        assert r.cuadra
        assert _quedan(db, ids) == 0

    def test_en_seco_archiva_y_no_borra(self, db: Session, tmp_path) -> None:
        """Sirve para comprobar que el archivo sale bien **antes** de confiar en
        la parte destructiva. Sin esto, la primera corrida real es la prueba."""
        ids = [_evento(db, TENANT, "2099-03-05")]

        r = rotar(
            db,
            desde=date(2099, 3, 1),
            hasta=date(2099, 4, 1),
            destino=tmp_path,
            borrar=False,
        )

        assert r.filas_archivadas == 1
        assert r.filas_borradas == 0
        assert _quedan(db, ids) == 1
        assert list(tmp_path.glob("*.json"))


class TestLosLimitesDelRango:
    def test_no_toca_lo_de_otros_meses(self, db: Session, tmp_path) -> None:
        antes = _evento(db, TENANT, "2099-02-28")
        dentro = _evento(db, TENANT, "2099-03-15")
        despues = _evento(db, TENANT, "2099-04-01")

        r = rotar(db, desde=date(2099, 3, 1), hasta=date(2099, 4, 1), destino=tmp_path)

        assert r.filas_archivadas == 1
        assert _quedan(db, [dentro]) == 0
        assert _quedan(db, [antes, despues]) == 2

    def test_el_ultimo_dia_del_mes_entra_completo(self, db: Session, tmp_path) -> None:
        """**El error de rango que no se ve.**

        Con `hasta` inclusivo, lo que ocurrio el 31 despues de medianoche queda
        afuera: no se archiva y no se borra, asi que sobrevive suelto y nadie lo
        nota hasta que busca un evento y no esta donde deberia.
        """
        tarde = _evento(db, TENANT, "2099-03-31 23:59:00")

        r = rotar(db, desde=date(2099, 3, 1), hasta=date(2099, 4, 1), destino=tmp_path)

        assert r.filas_archivadas == 1
        assert _quedan(db, [tarde]) == 0

    def test_la_primera_hora_del_mes_siguiente_no_entra(
        self, db: Session, tmp_path
    ) -> None:
        temprano = _evento(db, TENANT, "2099-04-01 00:01:00")

        r = rotar(db, desde=date(2099, 3, 1), hasta=date(2099, 4, 1), destino=tmp_path)

        assert r.filas_archivadas == 0
        assert _quedan(db, [temprano]) == 1

    def test_un_mes_sin_eventos_no_escribe_nada(self, db: Session, tmp_path) -> None:
        r = rotar(db, desde=date(2099, 6, 1), hasta=date(2099, 7, 1), destino=tmp_path)

        assert r.filas_archivadas == 0
        assert r.por_empresa == []
        assert list(tmp_path.glob("*.json")) == []


class TestQueMesSeRota:
    def test_siempre_el_mes_cerrado_anterior(self) -> None:
        """**Nunca el mes en curso.**

        Correr la tarea el 15 y llevarse lo que va del mes deja el registro
        partido en dos lugares para un periodo que todavia no termino.
        """
        assert mes_anterior(date(2026, 8, 20)) == (date(2026, 7, 1), date(2026, 8, 1))

    def test_en_enero_retrocede_de_ano(self) -> None:
        assert mes_anterior(date(2026, 1, 5)) == (date(2025, 12, 1), date(2026, 1, 1))

    def test_el_primero_del_mes_rota_el_anterior_completo(self) -> None:
        """Es el dia en que corre el cron, asi que este caso es el real."""
        assert mes_anterior(date(2026, 9, 1)) == (date(2026, 8, 1), date(2026, 9, 1))


class TestNuncaBorraLoQueNoQuedoGuardado:
    """La propiedad que hace segura toda la tarea.

    Que `write_text` no lance **no prueba que el contenido este en disco**: un
    disco lleno puede truncar sin error. Por eso el archivo se relee antes de
    borrar nada.

    Sin esta prueba la comprobacion se puede quitar y toda la suite sigue en
    verde — se verifico rompiendola a proposito, y pasaba.
    """

    def test_si_el_archivo_quedo_incompleto_no_borra_nada(
        self, db: Session, tmp_path, monkeypatch
    ) -> None:
        ids = [_evento(db, TENANT, "2099-03-05"), _evento(db, TENANT, "2099-03-06")]

        # Simula el disco que trunca: escribe un JSON valido pero con menos
        # filas de las exportadas. Es el fallo silencioso, no el ruidoso.
        from pathlib import Path as _Path

        original = _Path.write_text

        def truncado(self, contenido, **kw):
            datos = json.loads(contenido)
            datos["filas"] = 0
            datos["registros"] = []
            return original(self, json.dumps(datos), **kw)

        monkeypatch.setattr(_Path, "write_text", truncado)

        with pytest.raises(RuntimeError) as exc:
            rotar(
                db, desde=date(2099, 3, 1), hasta=date(2099, 4, 1), destino=tmp_path
            )

        # El mensaje tiene que decir que NO se borro, o quien lo lea va a asumir
        # lo peor y buscar el respaldo que no existe.
        assert "No se borra nada" in str(exc.value)
        assert _quedan(db, ids) == 2

    def test_el_resultado_cuadra_o_no_se_confirma(self, db: Session, tmp_path) -> None:
        """`filas_borradas` tiene que igualar a `filas_archivadas`.

        Se devuelven los dos numeros y no un "ok" justamente para que la promesa
        sea verificable desde afuera.
        """
        _evento(db, TENANT, "2099-03-05")
        _evento(db, OTRA, "2099-03-07")

        r = rotar(db, desde=date(2099, 3, 1), hasta=date(2099, 4, 1), destino=tmp_path)

        assert r.cuadra
        assert r.filas_archivadas == r.filas_borradas == 2
