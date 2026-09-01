"""Paginacion acotada, y que nunca corte en silencio (#167).

## Los tres hallazgos, medidos contra el contrato en ejecucion

| Hallazgo | Medicion |
|---|---|
| `limit` sin tope maximo | **25 de 25** endpoints que lo exponen |
| Truncamiento silencioso | Un listado devuelve 100 filas de 340 y el cliente no tiene forma de saberlo |
| Sin `has_more` | La respuesta es un arreglo pelado |

**El truncamiento silencioso es el peor de los tres, y es mas enganoso que no
paginar**: una pantalla que muestra 100 filas de 340 se ve perfectamente normal.
Nadie la reporta, porque no hay nada que se vea mal.

## Por que la senal va en una cabecera y no en el cuerpo

Envolver la respuesta en `{items, has_more}` es lo que pediria un diseno de API
desde cero, y **rompe los 25 endpoints a la vez** — todos los stores del
frontend leen un arreglo. Un cambio de esa forma tiene que ser deliberado y
revisable por si solo, no un efecto secundario de poner un tope.

`X-Has-More` no rompe a nadie: quien lee el arreglo sigue funcionando igual, y
quien quiera saber si falta puede preguntarlo. Es el mismo camino que toma
GitHub con `Link`.

## Como se sabe si hay mas sin contar

Se piden `limit + 1` filas y se devuelven `limit`. Si vino la de mas, hay mas.

Un `COUNT(*)` aparte seria una segunda consulta sobre las mismas tablas en cada
listado, y ademas puede **no coincidir** con la pagina: entre las dos consultas
alguien inserta una fila. La fila de sobra responde exactamente la pregunta que
se hace, con una sola consulta y sin ventana de incoherencia.

Lo que **no** da es el total. Si algun dia una pantalla lo necesita, se agrega
`X-Total-Count` con su costo declarado, en vez de pagarlo en todos los listados
para las pantallas que no lo usan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from fastapi import Query, Response

#: El techo duro. Ninguna peticion puede pedir mas, y **se rechaza en vez de
#: recortarse**: recortar en silencio es el mismo defecto que este modulo
#: existe para arreglar, solo que del lado del parametro.
#:
#: 500 y no menos porque el frontend ya pide `limit=500` en las tres pantallas
#: ISO. Bajarlo seria romper lo que funciona hoy para satisfacer un numero
#: elegido a ojo; subirlo dejaria de acotar nada.
TOPE_DE_PAGINA = 500

#: Cuantas filas se devuelven si nadie dice. Se conserva el 100 que ya usaban
#: los 25 endpoints: cambiarlo de paso alteraria lo que ve cada pantalla sin
#: que nadie lo haya pedido.
POR_DEFECTO = 100


@dataclass(frozen=True)
class Pagina:
    """Los dos parametros, ya validados.

    `limit` lleva `le=TOPE_DE_PAGINA`, asi que el tope **sale en el OpenAPI** y
    pedir de mas responde 422 con el maximo en el mensaje. Un tope que solo vive
    en el codigo obliga a descubrirlo probando.
    """

    skip: int
    limit: int

    @property
    def pedir(self) -> int:
        """Una fila mas de las que se van a devolver: la que delata que hay mas."""
        return self.limit + 1


def paginacion(
    skip: int = Query(
        default=0,
        ge=0,
        description="Cuantas filas saltar desde el principio.",
    ),
    limit: int = Query(
        default=POR_DEFECTO,
        ge=1,
        le=TOPE_DE_PAGINA,
        description=(
            f"Cuantas filas devolver, hasta {TOPE_DE_PAGINA}. Pedir mas responde "
            "422: el servidor no acepta consultas de tamano arbitrario. La "
            "cabecera `X-Has-More` dice si quedaron filas fuera."
        ),
    ),
) -> Pagina:
    return Pagina(skip=skip, limit=limit)


def recortar(
    respuesta: Response, filas: Sequence[Any], pagina: Pagina
) -> list[Any]:
    """Devuelve la pagina y **deja dicho si se corto**.

    `filas` viene con hasta `pagina.pedir` elementos. Si llegaron mas de
    `limit`, sobra al menos uno: hay mas alla de esta pagina.

    Las dos cabeceras van **siempre**, tambien cuando no hay mas. Una cabecera
    que solo aparece cuando falta algo obliga a distinguir "no hay mas" de "esta
    version del servidor no lo dice", y son cosas distintas.
    """
    hay_mas = len(filas) > pagina.limit
    respuesta.headers["X-Has-More"] = "true" if hay_mas else "false"
    respuesta.headers["X-Page-Limit"] = str(pagina.limit)
    return list(filas[: pagina.limit])
