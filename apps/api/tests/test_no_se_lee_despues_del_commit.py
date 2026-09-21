"""Ningun handler consulta la base despues de `db.commit()`.

## Por que es una prueba que lee el codigo

`declarar()` usa `SET LOCAL`, que dura lo que dura la transaccion. El `commit`
la cierra, asi que **la empresa declarada se pierde**: cualquier consulta
posterior —`db.refresh()` incluido— ve cero filas y, en el caso de `refresh`,
revienta con `Could not refresh instance`. Es lo que CLAUDE.md llama "no
consultar despues de `db.commit()`", y ya paso tres veces.

## Por que las pruebas normales no lo ven

Buena parte de la suite abre la sesion con
`join_transaction_mode="create_savepoint"`: ahi el `commit` del handler solo
cierra un savepoint y la transaccion de afuera —con su `SET LOCAL` intacto—
sigue viva. El codigo roto pasa en verde y falla en ejecucion real. Se midio el
20-sep: `POST /iso14001/aspects/{id}/evaluate` respondia **500** en el navegador
con su servicio probado y su suite en verde.

Por eso esto se comprueba **leyendo el codigo**, como las cinco listas de
migraciones o el flag de uvicorn: es una regla de forma, y una regla de forma se
verifica sobre la forma.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

#: Lo que no puede aparecer despues de un commit dentro de la misma funcion.
#:
#: Anclado al **inicio de la sentencia**: de otro modo marca la prosa que habla
#: del patron —los docstrings de este repositorio lo explican en varios lados— y
#: un detector que grita por su propia documentacion se termina apagando.
CONSULTA = re.compile(
    r"^(?:\w+\s*=\s*)?(db\.(refresh|scalar|scalars|execute|get|query)\(|crud_\w+\.(get|get_multi)\()"
)
COMMIT = re.compile(r"^(?:\w+\s*=\s*)?db\.commit\(\)")
#: Un `def` o un decorador cierran el bloque que se mira.
FIN_DE_BLOQUE = re.compile(r"\s*(def |async def |@)")
COMILLAS = ('"""', "'''")


def _codigo(lineas: list[str]) -> list[tuple[int, str]]:
    """Las lineas de codigo, sin docstrings ni comentarios."""
    fuera: list[tuple[int, str]] = []
    dentro_de_texto = False
    for n, linea in enumerate(lineas, start=1):
        comillas = sum(linea.count(c) for c in COMILLAS)
        if dentro_de_texto:
            if comillas % 2 == 1:
                dentro_de_texto = False
            continue
        if comillas % 2 == 1:
            dentro_de_texto = True
            continue
        desnuda = linea.strip()
        if desnuda and not desnuda.startswith("#"):
            fuera.append((n, linea))
    return fuera


def _infracciones() -> list[str]:
    encontradas: list[str] = []
    for archivo in sorted(APP.rglob("*.py")):
        codigo = _codigo(archivo.read_text(encoding="utf-8").split("\n"))
        for k, (_n, linea) in enumerate(codigo):
            if not COMMIT.match(linea.strip()):
                continue
            for n_sig, siguiente in codigo[k + 1 :]:
                if FIN_DE_BLOQUE.match(siguiente):
                    break
                if CONSULTA.match(siguiente.strip()):
                    encontradas.append(
                        f"{archivo.relative_to(APP.parent)}:{n_sig}: {siguiente.strip()}"
                    )
                    break
    return encontradas


def test_el_barrido_mira_algo() -> None:
    """Sin esto, una ruta equivocada recorre cero archivos y pasa en verde."""
    archivos = list(APP.rglob("*.py"))
    assert len(archivos) > 50, f"solo {len(archivos)} archivos: la ruta esta mal"
    commits = sum(
        1
        for f in archivos
        for _n, linea in _codigo(f.read_text(encoding="utf-8").splitlines())
        if COMMIT.match(linea.strip())
    )
    assert commits > 20, f"solo {commits} commits vistos: el patron ya no reconoce nada"


def test_nadie_consulta_despues_del_commit() -> None:
    infracciones = _infracciones()
    assert infracciones == [], (
        "Se consulta la base despues de `db.commit()`, y ahi ya no hay empresa "
        "declarada: la consulta ve cero filas y `refresh` revienta. Lee antes de "
        "confirmar (`Schema.model_validate(obj)` y despues `db.commit()`).\n  "
        + "\n  ".join(infracciones)
    )
