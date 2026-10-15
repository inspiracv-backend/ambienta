"""
Fusión por posición (Reciprocal Rank Fusion).

La similitud coseno y el rango de texto completo están en escalas distintas; compararlos no
significa nada. RRF ignora los puntajes y usa el puesto de cada resultado en cada lista.

Importante: la fusión **ordena**, no decide si hay evidencia. Eso se decide antes, con la
similitud coseno (SPEC-05). El material original comparaba el puntaje fusionado (~0,016)
contra un umbral de similitud (0,35) y toda pregunta salía "sin evidencia".
"""

from __future__ import annotations

import copy

from .tipos import Resultado

K_FUSION = 60


def fusionar(listas: list[list[Resultado]], pesos: list[float] | None = None) -> list[Resultado]:
    pesos = pesos or [1.0] * len(listas)
    puntajes: dict[str, float] = {}
    objetos: dict[str, Resultado] = {}

    for lista, peso in zip(listas, pesos, strict=True):
        for puesto, r in enumerate(lista, start=1):
            puntajes[r.clave] = puntajes.get(r.clave, 0.0) + peso / (K_FUSION + puesto)
            if r.clave not in objetos:
                objetos[r.clave] = copy.copy(r)
                objetos[r.clave].origen = set(r.origen)
            else:
                o = objetos[r.clave]
                o.origen |= r.origen
                if r.similitud is not None and (o.similitud is None or r.similitud > o.similitud):
                    o.similitud = r.similitud

    salida = []
    for clave, puntaje in sorted(puntajes.items(), key=lambda kv: kv[1], reverse=True):
        r = objetos[clave]
        r.puntaje = puntaje
        salida.append(r)
    return salida
