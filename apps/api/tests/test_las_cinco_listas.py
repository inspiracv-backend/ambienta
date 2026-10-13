"""Las cinco listas de migraciones dicen lo mismo.

CLAUDE.md lo advierte y aun asi vuelve a pasar:

> **La lista de archivos vive en CINCO lugares que deben coincidir**, y el
> quinto es el que se olvida: `docker-compose.yml`, `docker-compose.prod.yml`,
> `db/run.sh`, `db/README.md` y **el bucle de `.github/workflows/ci.yml`**.

Olvidar el quinto **no rompe nada en local** —donde Docker ya aplico el
archivo— y hace fallar CI con `column ... does not exist`, que se lee como un
error del codigo y no de la configuracion.

Y hay una forma de romperlo que la advertencia no cubre: **agregarlo mal**. El
4-sep el nombre entro al bucle de `ci.yml` con un `\n` literal en vez de un
salto de linea, asi que el shell vio una migracion llamada `n`:

    -> n
    psql: error: ../../db/n.sql: No such file or directory

Registrado en las cinco listas, y aun asi CI en rojo. Por eso esta prueba no
comprueba que el nombre "aparezca": comprueba que **cada nombre del bucle sea un
archivo que existe**, y que ningun archivo de `db/` se quede fuera.

Es una prueba sobre configuracion, como la que lee los Dockerfile para el flag
de uvicorn. Lo que vive fuera del codigo tambien se puede romper, y ahi ninguna
suite de Python mira.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
DB = RAIZ / "db"

#: Lo que no es una migracion del esquema y por eso no va en todas las listas.
#:
#: `02_seed` son datos de demostracion: el compose de **produccion** no lo monta
#: a proposito, porque produccion arranca vacia. `02_smoke_test` son las
#: comprobaciones del esquema, que CI corre en su propio paso. `ambienta_dump`
#: es un volcado, no una migracion.
APARTE = {"02_seed", "02_smoke_test", "ambienta_dump"}


def _migraciones_en_disco() -> set[str]:
    return {p.stem for p in DB.glob("*.sql")} - APARTE


def _nombres_del_bucle_de_ci() -> list[str]:
    """Los nombres tal como los va a expandir el shell.

    Se quitan las barras de continuacion y los retornos de carro, que es
    exactamente lo que hace `bash` al leer el bloque.
    """
    # Se lee en binario y se decodifica: `Path.read_text` no acepta `newline`,
    # y hay que ver los `\r` tal como estan — el repositorio es CRLF y esta
    # prueba existe justamente por un salto de linea mal escrito.
    texto = (RAIZ / ".github" / "workflows" / "ci.yml").read_bytes().decode("utf-8")
    bloque = re.search(r"for f in (.*?); do", texto, re.S)
    assert bloque, "no se encontro el bucle de migraciones en ci.yml"
    crudo = bloque.group(1).replace(chr(13), " ").replace(chr(92), " ")
    return crudo.split()


def test_todo_nombre_del_bucle_de_ci_es_un_archivo_que_existe() -> None:
    """**La comprobacion que habria cazado el `\\n` literal.**

    Un nombre que no corresponde a un archivo hace fallar CI con un mensaje que
    habla de `psql`, no de la configuracion que lo causo.
    """
    faltan = [n for n in _nombres_del_bucle_de_ci() if not (DB / f"{n}.sql").exists()]

    assert faltan == [], (
        f"El bucle de `ci.yml` nombra migraciones que no existen: {faltan}. "
        "Suele ser un salto de linea mal escrito en la continuacion."
    )


def test_ninguna_migracion_se_queda_fuera_del_bucle_de_ci() -> None:
    """El otro lado: CI aplicando un esquema que no es el que corre en ningun
    lado. Ya paso — con solo `01` y `03` faltaban el rol de la aplicacion, la
    secuencia de tickets y los permisos individuales."""
    fuera = sorted(_migraciones_en_disco() - set(_nombres_del_bucle_de_ci()))

    assert fuera == [], (
        f"Estas migraciones no estan en el bucle de `ci.yml`: {fuera}. "
        "CI va a dar verde sobre un esquema distinto al real."
    )


@pytest.mark.parametrize(
    "archivo",
    ["docker-compose.yml", "db/run.sh", "db/README.md"],
)
def test_las_otras_listas_nombran_todas_las_migraciones(archivo: str) -> None:
    texto = (RAIZ / archivo).read_text(encoding="utf-8", errors="ignore")
    fuera = sorted(m for m in _migraciones_en_disco() if m not in texto)

    assert fuera == [], f"{archivo} no nombra: {fuera}"


def test_el_compose_de_produccion_las_nombra_menos_el_seed() -> None:
    """Produccion **no monta `02_seed`** a proposito: arranca vacia. Por eso va
    aparte y no en el parametrizado de arriba — para que la excepcion quede
    escrita como una decision y no como un olvido."""
    texto = (RAIZ / "docker-compose.prod.yml").read_text(encoding="utf-8")

    fuera = sorted(m for m in _migraciones_en_disco() if m not in texto)
    assert fuera == [], f"docker-compose.prod.yml no nombra: {fuera}"
    assert "02_seed.sql" not in texto, (
        "El compose de produccion monta los datos de demostracion. Produccion "
        "arranca vacia: sembrar ejemplos ahi los deja indistinguibles de los "
        "datos reales del cliente."
    )
