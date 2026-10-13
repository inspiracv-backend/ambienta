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

#: Cualquier uso de la sesion despues del commit, **no solo `db.refresh`**.
#:
#: La primera version miraba `db.refresh(`, `db.execute(`, `crud_x.get(`... al
#: inicio de la sentencia, y se le escaparon dos en `roles.py` (21-sep): ahi la
#: consulta va **dentro de una funcion auxiliar** —`return _alcance(db, id)`—, y
#: esa funcion consulta igual. Pasarle `db` a algo despues del commit es
#: consultar sin empresa, se llame como se llame.
USO_DE_SESION = re.compile(
    r"\bdb\.(?!commit\(|close\(|rollback\()\w+\("  # db.algo(...)
    r"|[(,]\s*db\s*[,)]"                           # f(db, ...) / f(x, db)
    r"|\bdb\s*=\s*db\b"                            # f(db=db)
)
COMMIT = re.compile(r"^(?:\w+\s*=\s*)?db\.commit\(\)")
#: Volver a declarar la empresa despues del commit es legitimo: es lo que hacen
#: las tareas que recorren empresas. Desde ahi la sesion vuelve a tener empresa.
REDECLARA = re.compile(r"\b(?:volver_a_)?declarar\(\s*db\b")
#: Un `def` o un decorador cierran el bloque que se mira.
FIN_DE_BLOQUE = re.compile(r"\s*(def |async def |@)")
#: Una rama hermana, menos sangrada que el commit, **no corre despues de el**:
#: un commit en un `except` y un uso de la sesion en el `except` siguiente son
#: dos caminos distintos. Sin esto el despachador de avisos salia marcado.
OTRA_RAMA = re.compile(r"(except\b|elif\b|else\s*:)")
COMILLAS = ('"""', "'''")
#: El texto entre comillas no es codigo: un `description=` que explica el
#: patron no es una infraccion.
CADENA = re.compile(r"""[rbfuRBFU]{0,2}("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")


def _codigo(lineas: list[str]) -> list[tuple[int, str]]:
    """Las lineas de codigo, sin docstrings, comentarios ni cadenas."""
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
        # Primero las cadenas y despues el comentario: un `#` dentro de una
        # cadena no empieza nada. La sangria se conserva: es lo que dice en que
        # rama esta cada linea.
        desnuda = CADENA.sub('""', linea).split("#", 1)[0].rstrip()
        if desnuda.strip():
            fuera.append((n, desnuda))
    return fuera


def _sangria(linea: str) -> int:
    return len(linea) - len(linea.lstrip())


def infracciones_en(texto: str, nombre: str = "<texto>") -> list[str]:
    """Separado del recorrido para poder probar el detector con codigo inventado."""
    encontradas: list[str] = []
    codigo = _codigo(texto.split("\n"))
    for k, (_n, linea) in enumerate(codigo):
        if not COMMIT.match(linea.strip()):
            continue
        for n_sig, siguiente in codigo[k + 1 :]:
            sentencia = siguiente.strip()
            if FIN_DE_BLOQUE.match(siguiente) or REDECLARA.search(sentencia):
                break
            if _sangria(siguiente) < _sangria(linea) and OTRA_RAMA.match(sentencia):
                break
            if USO_DE_SESION.search(sentencia):
                encontradas.append(f"{nombre}:{n_sig}: {sentencia}")
                break
    return encontradas


def _infracciones() -> list[str]:
    encontradas: list[str] = []
    for archivo in sorted(APP.rglob("*.py")):
        encontradas += infracciones_en(
            archivo.read_text(encoding="utf-8"), str(archivo.relative_to(APP.parent))
        )
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


# El detector, contra codigo inventado. Contar archivos y commits no prueba que
# `USO_DE_SESION` reconozca algo: con ese patron roto el barrido encontraria
# cero infracciones y pasaria en verde, que es justo como se le escaparon las
# dos de `roles.py`.
_MARCA = [
    # La forma de `roles.py::fijar_alcance`: la consulta va en una auxiliar.
    "def f(db):\n    db.commit()\n    return _alcance(db, user_id)\n",
    # La de `fijar_roles`: dentro de una comprension, en una linea de
    # continuacion de la respuesta.
    "def f(db):\n    db.commit()\n    return R(\n        ids=[a for a in svc.vigentes(db, u)],\n    )\n",
    "def f(db):\n    db.commit()\n    db.refresh(obj)\n",
    "def f(db):\n    db.commit()\n    fila = crud_x.get(db, i)\n",
    "def f(db):\n    db.commit()\n    g(db=db)\n",
]
_NO_MARCA = [
    # Leer antes de confirmar: la regla.
    "def f(db):\n    leido = S.model_validate(o)\n    db.commit()\n    return leido\n",
    # Volver a declarar la empresa antes de releer.
    "def f(db):\n    db.commit()\n    volver_a_declarar(db)\n    return g(db, i)\n",
    "def f(db):\n    db.commit()\n    declarar(db, t)\n    db.execute(q)\n",
    # El despachador: el commit y el uso estan en ramas hermanas.
    "def f(db):\n    try:\n        x()\n    except A:\n        db.commit()\n        break\n    except B:\n        _rendirse(db, a)\n",
    # Texto que habla del patron no es el patron.
    "def f(db):\n    db.commit()\n    log(\"no hacer db.refresh(x) aca\")\n",
    # Un commit en una funcion no contamina a la siguiente.
    "def f(db):\n    db.commit()\n\ndef g(db):\n    return db.get(M, 1)\n",
]


def test_el_detector_reconoce_el_patron() -> None:
    no_vistos = [c for c in _MARCA if not infracciones_en(c)]
    assert no_vistos == [], "El detector no ve estos casos:\n" + "\n---\n".join(no_vistos)


def test_el_detector_no_marca_lo_legitimo() -> None:
    marcados = [c for c in _NO_MARCA if infracciones_en(c)]
    assert marcados == [], "El detector marca codigo correcto:\n" + "\n---\n".join(marcados)


def test_nadie_consulta_despues_del_commit() -> None:
    infracciones = _infracciones()
    assert infracciones == [], (
        "Se consulta la base despues de `db.commit()`, y ahi ya no hay empresa "
        "declarada: la consulta ve cero filas y `refresh` revienta. Lee antes de "
        "confirmar (`Schema.model_validate(obj)` y despues `db.commit()`).\n  "
        + "\n  ".join(infracciones)
    )
