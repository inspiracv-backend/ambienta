"""Todo listado paginado lleva un orden total, o leerlo por paginas miente.

Sin `ORDER BY`, Postgres no promete que dos consultas con `OFFSET` devuelvan las
filas en el mismo orden: leer un listado por paginas puede **repetir filas y
saltarse otras**, y nada falla. `CRUDBase.get_multi` paginaba asi hasta el
21-sep. No se notaba porque la web leia solo la primera pagina — que era el
otro defecto: la Matriz Legal recibia 100 de 264 evaluaciones y mostraba las
demas como "sin evaluar". Al arreglar ese (`api.getTodas`, que recorre las
paginas) este dejo de ser teorico.

**Es una prueba de forma, a proposito.** Una prueba que pagine contra la base
pasaria igual con el defecto: en tablas chicas el orden fisico casi siempre
coincide con el de insercion. Lo que se comprueba es que la consulta **pida**
un orden y que termine en la clave primaria, que es lo que lo hace total.
"""
from __future__ import annotations

import importlib
import pkgutil

import pytest
from sqlalchemy import inspect as sa_inspect

import app.crud as paquete_crud
from app.crud.base import CRUDBase


def _instancias() -> list[tuple[str, CRUDBase]]:
    encontradas: dict[int, tuple[str, CRUDBase]] = {}
    for modulo in pkgutil.iter_modules(paquete_crud.__path__):
        m = importlib.import_module(f"app.crud.{modulo.name}")
        for nombre, valor in vars(m).items():
            if isinstance(valor, CRUDBase):
                encontradas.setdefault(id(valor), (f"{modulo.name}.{nombre}", valor))
    return sorted(encontradas.values(), key=lambda par: par[0])


INSTANCIAS = _instancias()


class _SesionQueAnota:
    """Lo minimo para que `get_multi` arme su consulta y la entregue."""

    def __init__(self) -> None:
        # Alcance ya resuelto como "sin acotar": aca no se prueba el alcance.
        self.info = {"alcance_de_instalaciones": None}
        self.consulta = None

    def scalars(self, consulta):
        self.consulta = consulta
        return self

    def all(self):
        return []


def test_se_encontraron_los_recursos() -> None:
    """Control: si el recorrido no encuentra nada, lo de abajo pasa en vacio."""
    assert len(INSTANCIAS) >= 40, [n for n, _ in INSTANCIAS]


@pytest.mark.parametrize("nombre,crud", INSTANCIAS, ids=[n for n, _ in INSTANCIAS])
def test_el_listado_pide_un_orden_que_termina_en_la_clave(nombre: str, crud: CRUDBase, monkeypatch) -> None:
    monkeypatch.setattr("app.alcance.instalaciones_permitidas", lambda db: None)
    sesion = _SesionQueAnota()

    crud.get_multi(sesion, skip=0, limit=10)  # type: ignore[arg-type]

    orden = list(sesion.consulta._order_by_clauses)
    assert orden, f"{nombre}: get_multi pagina sin ORDER BY"
    claves = [c.key for c in sa_inspect(crud.model).primary_key]
    ultimas = [getattr(c, "key", None) for c in orden[-len(claves):]]
    assert ultimas == claves, (
        f"{nombre}: el orden {[getattr(c, 'key', c) for c in orden]} no termina en la "
        f"clave primaria {claves}; sin eso los empates de created_at quedan sin orden"
    )
