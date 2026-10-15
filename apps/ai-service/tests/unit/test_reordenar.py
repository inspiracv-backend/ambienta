"""SPEC-05 · El reordenador decide la evidencia cuando el coseno no alcanza (catálogo real, 21/09/2026)."""

from __future__ import annotations

import uuid

from ambienta_ia.recuperacion import Cita, Resultado
from ambienta_ia.recuperacion.reordenar import DIRECTA, aplicar


def _r(clave: str, similitud: float = 0.6) -> Resultado:
    cita = Cita(norma="Ley 19300", articulo=clave, ruta=f"Ley 19300 › Artículo {clave}", texto="…",
                norm_id=uuid.uuid4(), article_id=uuid.uuid4(), norm_version_id=None)
    return Resultado(clave=clave, cita=cita, similitud=similitud, origen={"semantica"})


def test_lo_irrelevante_se_descarta_aunque_tenga_mas_similitud():
    candidatos = [_r("18 quater", 0.69), _r("12", 0.70), _r("11", 0.66)]
    elegidos = aplicar(candidatos, {"18 quater": 1, "12": 1, "11": 3}, k=5)
    assert [e.clave for e in elegidos] == ["11"]


def test_ordena_por_relevancia_y_a_igualdad_conserva_el_orden():
    candidatos = [_r("a"), _r("b"), _r("c"), _r("d")]
    elegidos = aplicar(candidatos, {"a": 2, "b": 3, "c": 2, "d": 0}, k=5)  # hay un 3: entran los 2 como contexto
    assert [e.clave for e in elegidos] == ["b", "a", "c"]


def test_sin_nada_relevante_no_hay_evidencia():
    assert aplicar([_r("a"), _r("b")], {"a": 1, "b": 0}, k=5) == []


def test_lo_pedido_por_numero_no_se_cae():
    elegidos = aplicar([_r("10"), _r("8")], {"10": 0, "8": 3}, minimos={"10"}, k=5)
    assert [e.clave for e in elegidos] == ["10", "8"]
    assert elegidos[0].puntaje == DIRECTA


def test_sin_ninguno_directo_no_hay_evidencia():
    """Medido: 'velocidad en autopistas' pasaba con un 2 del art. 3 del DS 40."""
    assert aplicar([_r("3"), _r("4")], {"3": 2, "4": 2}, k=5) == []


def test_tope_de_partes_por_articulo():
    art = uuid.uuid4()
    partes = []
    for i in range(5):
        r = _r(f"19:{i}")
        r.cita = Cita(norma="DS 40", articulo="19", ruta="DS 40 › Artículo 19", texto="…", norm_id=art,
                      article_id=art, norm_version_id=None)
        partes.append(r)
    otro = _r("12 bis")
    elegidos = aplicar(partes + [otro], {**{p.clave: 3 for p in partes}, "12 bis": 3}, k=5)
    assert [e.cita.articulo for e in elegidos].count("19") == 2
    assert "12 bis" in [e.cita.articulo for e in elegidos]


def test_respeta_k():
    candidatos = [_r(str(i)) for i in range(10)]
    assert len(aplicar(candidatos, {str(i): 3 for i in range(10)}, k=4)) == 4
