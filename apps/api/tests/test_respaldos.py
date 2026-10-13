"""El respaldo de la base y de la auditoria archivada (RNF-19, RNF-20).

## Lo que estas pruebas protegen

**Un respaldo que nadie restauro no es un respaldo**, y hasta el 13-oct-2026 no
habia ninguno: el runbook lo declaraba deuda abierta. Lo que se puede equivocar
aca no es "no se escribio el archivo" —eso falla solo— sino las formas de
terminar con un archivo que parece un respaldo y no lo es:

1. **Un volcado sin datos.** `pg_dump` con el rol de la aplicacion se niega en
   voz alta (medido: `query would be affected by row-level security policy`),
   pero con `--enable-row-security` volcaria solo las filas visibles: cero filas
   de empresa, esquema completo, tamano creible. `TestNoSeVuelcaSinDatos`.
2. **Un archivo truncado**, por disco lleno o por un corte. Se ve igual de bien
   en `ls`. `TestSeVerificaRestaurando`.
3. **Una purga que deja cero respaldos.** El caso se da solo: nadie respalda por
   un mes, y la primera corrida siguiente borra todo lo que quedaba por viejo.
   `TestLaPurgaNuncaDejaCero`.

## Las que necesitan `pg_dump`

Las de volcado y restauracion **se saltan si no hay `pg_dump` de la misma
version mayor que el servidor**, que es el caso de una maquina Windows de
desarrollo. En CI corren: el runner trae el cliente 16 y el servicio es
`pgvector/pgvector:pg16`. Saltarlas en silencio seria peor, asi que el motivo
sale en el `reason`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from app.config import get_settings
from app.services import respaldos as svc

URL_ADMIN_POR_DEFECTO = "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta"


def _version_mayor_del_cliente() -> int | None:
    """La version mayor de `pg_dump`, o `None` si no esta instalado."""
    if not shutil.which("pg_dump"):
        return None
    try:
        salida = subprocess.run(
            ["pg_dump", "--version"], capture_output=True, text=True, timeout=20
        ).stdout
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return None
    m = re.search(r"(\d+)", salida)
    return int(m.group(1)) if m else None


def _version_mayor_del_servidor() -> int | None:
    try:
        import psycopg
    except ImportError:  # pragma: no cover
        return None
    url = os.getenv("DATABASE_ADMIN_URL", URL_ADMIN_POR_DEFECTO)
    url = re.sub(r"^postgresql\+\w+://", "postgresql://", url)
    try:
        with psycopg.connect(url, connect_timeout=5) as cx:
            return cx.info.server_version // 10000
    except Exception:  # noqa: BLE001 - sin base, se salta
        return None


_CLIENTE = _version_mayor_del_cliente()
_SERVIDOR = _version_mayor_del_servidor()

necesita_pg_dump = pytest.mark.skipif(
    _CLIENTE is None or _SERVIDOR is None or _CLIENTE != _SERVIDOR,
    reason=(
        f"pg_dump {_CLIENTE} y servidor {_SERVIDOR}: hace falta el cliente de la "
        "misma version mayor. En Windows normalmente no esta instalado; en CI si."
    ),
)


@pytest.fixture(autouse=True)
def _con_url_de_administracion(monkeypatch):
    """La URL del dueno, que es con la que se respalda. Ver el modulo."""
    monkeypatch.setenv(
        "DATABASE_ADMIN_URL", os.getenv("DATABASE_ADMIN_URL", URL_ADMIN_POR_DEFECTO)
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestLaUrlDelVolcado:
    def test_se_traduce_el_dialecto_de_sqlalchemy(self, monkeypatch):
        monkeypatch.setenv(
            "DATABASE_ADMIN_URL", "postgresql+psycopg://u:p@servidor:5432/base"
        )
        get_settings.cache_clear()
        assert svc.url_de_administracion() == "postgresql://u:p@servidor:5432/base"

    def test_sin_url_de_administracion_se_niega(self, monkeypatch):
        """**No cae a `DATABASE_URL`**, al contrario que `db.py`.

        Con el rol de la aplicacion `pg_dump` falla todas las noches con un
        error sobre RLS que no se parece a "falta una variable".
        """
        monkeypatch.setenv("DATABASE_ADMIN_URL", "")
        get_settings.cache_clear()
        with pytest.raises(svc.ErrorDeRespaldo, match="DATABASE_ADMIN_URL"):
            svc.url_de_administracion()


class TestNoSeVuelcaSinDatos:
    def test_no_se_pasa_enable_row_security(self, tmp_path, monkeypatch):
        """La bandera que volveria silencioso el respaldo vacio.

        `--enable-row-security` hace que `pg_dump` vuelque **solo las filas
        visibles**. Con el rol de la aplicacion y sin tenant declarado, eso es
        cero filas de empresa en un archivo que pesa y se ve bien.

        Se comprueba **el comando que se ejecuta**, no el texto del archivo: la
        primera version de esta prueba buscaba la cadena en la fuente y fallaba
        por el comentario que explica justamente por que no usarla.
        """
        ordenes: list[list[str]] = []

        def espiar(orden, *, entorno=None):
            ordenes.append(orden)
            destino = next(a for a in orden if a.startswith("--file="))
            Path(destino[len("--file=") :]).write_bytes(b"x" * (svc.MINIMO_CREIBLE_BYTES + 1))
            return ""

        monkeypatch.setattr(svc, "_correr", espiar)
        svc.volcar_base(tmp_path, dia=date(2026, 10, 13))

        assert ordenes and ordenes[0][0] == "pg_dump"
        assert "--enable-row-security" not in ordenes[0]
        # Y la URL que recibe es la del dueno, no la de la aplicacion.
        assert "ambienta_app" not in ordenes[0][-1]

    def test_un_volcado_demasiado_chico_se_rechaza(self, tmp_path, monkeypatch):
        """Un archivo por debajo del piso no es un respaldo de una base chica."""

        def falso_pg_dump(orden, *, entorno=None):
            destino = next(a for a in orden if a.startswith("--file="))
            Path(destino[len("--file=") :]).write_bytes(b"demasiado corto")
            return ""

        monkeypatch.setattr(svc, "_correr", falso_pg_dump)
        with pytest.raises(svc.ErrorDeRespaldo, match="minimo creible"):
            svc.volcar_base(tmp_path, dia=date(2026, 10, 13))


class TestLaAuditoriaViajaAparte:
    def test_sin_carpeta_no_hay_artefacto(self, tmp_path):
        """Normal hasta la primera rotacion mensual: no es un error."""
        assert (
            svc.empaquetar_auditoria(
                tmp_path, dia=date(2026, 10, 13), origen=tmp_path / "no-existe"
            )
            is None
        )

    def test_empaqueta_lo_que_la_rotacion_dejo(self, tmp_path):
        """Y es lo que `pg_dump` **no** contiene: la rotacion borro esas filas."""
        origen = tmp_path / "auditoria"
        (origen / "2026-09").mkdir(parents=True)
        (origen / "2026-09" / "empresa-a.json").write_text('[{"id": 1}]', encoding="utf-8")

        art = svc.empaquetar_auditoria(tmp_path / "salida", dia=date(2026, 10, 13), origen=origen)
        assert art is not None
        assert art.nombre == "ambienta-auditoria-2026-10-13.tar.gz"

        import tarfile

        with tarfile.open(art.ruta) as tar:
            assert "2026-09/empresa-a.json" in tar.getnames()


class TestLaPurgaNuncaDejaCero:
    def _respaldo(self, carpeta: Path, dia: str) -> Path:
        p = carpeta / f"ambienta-base-{dia}.dump"
        p.write_bytes(b"x" * 100)
        return p

    def test_borra_los_viejos_y_conserva_los_nuevos(self, tmp_path):
        viejo = self._respaldo(tmp_path, "2026-08-01")
        nuevo = self._respaldo(tmp_path, "2026-10-13")
        informe = svc.Informe()

        svc.purgar(tmp_path, dias=30, dia=date(2026, 10, 13), informe=informe)

        assert not viejo.exists()
        assert nuevo.exists()
        assert viejo.name in informe.purgados_locales

    def test_si_todo_es_viejo_no_borra_nada_y_avisa(self, tmp_path):
        """El caso se da solo: un mes sin respaldar y la purga arrasa con todo.

        Dejar la instalacion sin ningun respaldo es exactamente lo contrario de
        lo que esta tarea existe para evitar.
        """
        a = self._respaldo(tmp_path, "2026-01-01")
        b = self._respaldo(tmp_path, "2026-02-01")
        informe = svc.Informe()

        svc.purgar(tmp_path, dias=30, dia=date(2026, 10, 13), informe=informe)

        assert a.exists() and b.exists()
        assert informe.purgados_locales == []
        assert any("sin ninguno" in x for x in informe.advertencias)


class TestSinAlmacenamientoSeAvisaYSigue:
    def test_un_respaldo_local_es_mejor_que_ninguno(self, tmp_path, monkeypatch):
        """Pero queda dicho: vive en el mismo disco que puede fallar."""
        monkeypatch.setattr(svc.alm, "esta_configurado", lambda: False)
        informe = svc.Informe()
        art = svc.Artefacto(nombre="x.dump", ruta=tmp_path / "x.dump", bytes=1)

        svc.subir([art], informe)

        assert art.subido is False
        assert any("SOLO" in x for x in informe.advertencias)

    def test_un_fallo_de_subida_no_tumba_la_corrida(self, tmp_path, monkeypatch):
        monkeypatch.setattr(svc.alm, "esta_configurado", lambda: True)

        def revienta(**_):
            raise RuntimeError("403 desde el bucket")

        monkeypatch.setattr(svc.alm, "subir_respaldo", revienta)
        informe = svc.Informe()
        art = svc.Artefacto(nombre="x.dump", ruta=tmp_path / "x.dump", bytes=1)

        svc.subir([art], informe)

        assert art.subido is False
        assert any("403" in x for x in informe.advertencias)


@necesita_pg_dump
class TestSeVerificaRestaurando:
    """Las dos que de verdad importan, contra la base real."""

    def test_se_vuelca_y_se_restaura_con_las_mismas_filas(self, tmp_path):
        art = svc.volcar_base(tmp_path, dia=date(2026, 10, 13))
        assert art.bytes > svc.MINIMO_CREIBLE_BYTES

        filas = svc.verificar(art)

        # `tenants` siempre tiene filas en una base con seed; si saliera en cero
        # la comparacion contra la base viva ya habria levantado el error.
        assert filas["tenants"] > 0
        assert set(filas) == set(svc.TABLAS_TESTIGO)

    def test_un_volcado_truncado_se_detecta(self, tmp_path):
        """Disco lleno, corte a mitad de escritura: el archivo se ve igual.

        Es la mutacion de la verificacion: si `verificar()` solo mirara el
        codigo de salida de `pg_dump`, esta prueba pasaria con el respaldo roto.
        """
        art = svc.volcar_base(tmp_path, dia=date(2026, 10, 13))
        with open(art.ruta, "r+b") as f:
            f.truncate(art.bytes // 2)

        with pytest.raises(svc.ErrorDeRespaldo):
            svc.verificar(art)

    def test_no_quedan_bases_de_verificacion_dando_vueltas(self, tmp_path):
        """Una verificacion que deja basura acumula una copia de la base por dia."""
        import psycopg

        art = svc.volcar_base(tmp_path, dia=date(2026, 10, 13))
        svc.verificar(art)

        with psycopg.connect(svc.url_de_administracion(), autocommit=True) as cx:
            with cx.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM pg_database WHERE datname LIKE 'ambienta_verificacion_%'"
                )
                assert cur.fetchone()[0] == 0
