"""Trae normativa real desde la Biblioteca del Congreso Nacional.

Hasta ahora el catalogo eran **ocho normas escritas a mano** en el seed: sin
texto, sin identificador de version real, y con la misma marca de tiempo en
todas —la hora en que se sembro la base, no la hora en que se consulto a nadie—.
Se veian bien y no venian de ninguna parte.

## Dos fuentes, y solo una funciona sin credenciales

| Que da | Como | Clave |
|---|---|---|
| Normas, fechas, organismo, **versiones y cual es la vigente** | SPARQL en `datos.bcn.cl` | **no** |
| El texto de los articulos | `leychile.cl/Consulta/obtxml` | **si** |

Comprobado: el XML responde **401** sin clave. Por eso este modulo trae todo lo
que se puede —que incluye lo que pidio el negocio, saber si una norma tiene una
version mas nueva que la evaluada— y el articulado queda para cuando la clave
este habilitada.

## Como modela la BCN una norma

Es FRBR: una obra con expresiones. `RootNorm` es la norma; cada `NormInstance`
es una version suya, con `versionDate` e `isLatestVersion`. Eso mapea uno a uno
contra `legal_norms` y `legal_norm_versions`, que ya existian con esa forma.

## Que NO hace

**No pisa lo que edito una persona.** Una norma que ya existe se actualiza solo
en los campos que vienen de la fuente; `norm_sectors` —la clasificacion, que es
trabajo humano— no se toca nunca. Sincronizar no puede destruir el criterio que
alguien aplico.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


logger = logging.getLogger(__name__)

ENDPOINT = "https://datos.bcn.cl/sparql"
BCN_NORMS = "http://datos.bcn.cl/ontologies/bcn-norms#"

#: Tipos de norma de la BCN que interesan para cumplimiento ambiental.
#:
#: La BCN tiene 748.000 normas, la enorme mayoria irrelevante —concesiones de
#: acuicultura, nombramientos—. Traerlas todas no es exhaustividad: es ruido que
#: despues alguien tiene que clasificar a mano.
TIPOS = ("ley", "dfl", "ds", "decreto", "res")


@dataclass
class NormaBCN:
    """Una norma tal como la devuelve la BCN, ya normalizada."""

    uri: str
    leychile_code: str
    tipo: str
    numero: str | None
    titulo: str
    organismo: str | None
    publicacion: date | None
    promulgacion: date | None
    versiones: list[VersionBCN] = field(default_factory=list)


@dataclass
class VersionBCN:
    uri: str
    fecha: date | None
    es_vigente: bool
    url_html: str | None
    url_xml: str | None


@dataclass
class Resultado:
    """Que trajo la sincronizacion.

    Se separan `nuevas` de `actualizadas` porque responden preguntas distintas:
    la primera dice cuanto crecio el catalogo, la segunda si la BCN publico
    cambios sobre lo que ya teniamos — que es lo que dispara revisar una matriz.
    """

    consultadas: int = 0
    nuevas: int = 0
    actualizadas: int = 0
    versiones_nuevas: int = 0
    #: Normas cuya version vigente cambio. **Son las que hay que mirar**: alguna
    #: empresa puede tener su matriz evaluada contra el texto anterior.
    con_version_nueva: list[str] = field(default_factory=list)


def _consultar(sparql: str, timeout: int = 120) -> list[dict[str, Any]]:
    """Una consulta al endpoint publico. Sin credenciales."""
    url = f"{ENDPOINT}?query={urllib.parse.quote(sparql)}&output=json"
    req = urllib.request.Request(
        url, headers={"Accept": "application/sparql-results+json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))["results"]["bindings"]


def _fecha(valor: str | None) -> date | None:
    """`AAAA-MM-DD` a fecha, tolerando lo que no lo sea.

    Una fecha mal formada **no debe tumbar la sincronizacion entera**: se pierde
    ese dato y se sigue. Perder una fecha es molesto; perder la corrida completa
    por una norma rara es peor.
    """
    if not valor:
        return None
    try:
        return datetime.strptime(valor[:10], "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Fecha ilegible en la BCN: %r", valor)
        return None


def _v(fila: dict, clave: str) -> str | None:
    return fila.get(clave, {}).get("value")


def buscar(termino: str, limite: int = 50) -> list[NormaBCN]:
    """Normas cuyo titulo contiene `termino`, con sus versiones.

    Se busca por titulo y no se descarga el catalogo entero a proposito: son
    748.000 normas y la mayoria no tiene nada que ver con medio ambiente.
    """
    filas = _consultar(
        f"""PREFIX bcn: <{BCN_NORMS}>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
SELECT ?norma ?titulo ?numero ?codigo ?publicacion ?promulgacion ?organismo ?tipo
WHERE {{
  ?norma a bcn:RootNorm ;
         dc:title ?titulo ;
         bcn:leychileCode ?codigo .
  OPTIONAL {{ ?norma bcn:hasNumber ?numero }}
  OPTIONAL {{ ?norma bcn:publishDate ?publicacion }}
  OPTIONAL {{ ?norma bcn:promulgationDate ?promulgacion }}
  OPTIONAL {{ ?norma bcn:createdBy ?organismo }}
  OPTIONAL {{ ?norma a ?tipo . FILTER(CONTAINS(STR(?tipo), "norma/tipo#")) }}
  FILTER(CONTAINS(LCASE(STR(?titulo)), LCASE("{termino}")))
}}
LIMIT {limite}"""
    )

    normas = []
    for f in filas:
        uri = _v(f, "norma")
        tipo_uri = _v(f, "tipo") or ""
        normas.append(
            NormaBCN(
                uri=uri,
                leychile_code=_v(f, "codigo") or "",
                tipo=tipo_uri.split("#")[-1] or "norma",
                numero=_v(f, "numero"),
                titulo=_v(f, "titulo") or "",
                organismo=(_v(f, "organismo") or "").split("/")[-1] or None,
                publicacion=_fecha(_v(f, "publicacion")),
                promulgacion=_fecha(_v(f, "promulgacion")),
            )
        )
    return normas


def versiones_de(uri_norma: str) -> list[VersionBCN]:
    """Las versiones de una norma, ordenadas, sin duplicados y con la vigente marcada.

    **Es el nucleo de lo que pidio el negocio**: guardar las versiones y poder
    decir si la que la empresa evaluo sigue siendo la ultima.

    ## Dos cosas que la fuente hace y hay que absorber

    **Devuelve filas repetidas.** Los `OPTIONAL` de la consulta multiplican una
    misma version por cada combinacion de campos presentes. Sin deduplicar, la
    Ley 19.300 aparecia con 11 versiones cuando tiene 9.

    **`isLatestVersion` viene marcado en mas de una.** En la Ley 19.300 estan
    marcadas la de 1994 y la de 2010. Confiar en la primera que aparece daba
    como vigente **el texto original de 1994** — dieciseis anos de reformas
    ignoradas, y sin ningun error a la vista.

    Por eso la vigente se decide **por la fecha mas alta**, y `isLatestVersion`
    se usa solo para corroborar. Si los dos criterios discrepan se registra un
    aviso: significa que la fuente cambio de forma y conviene mirarlo.
    """
    filas = _consultar(
        f"""PREFIX bcn: <{BCN_NORMS}>
SELECT ?version ?fecha ?vigente ?html ?xml
WHERE {{
  <{uri_norma}> bcn:hasVersion ?version .
  OPTIONAL {{ ?version bcn:versionDate ?fecha }}
  OPTIONAL {{ ?version bcn:isLatestVersion ?vigente }}
  OPTIONAL {{ ?version bcn:hasHtmlDocument ?html }}
  OPTIONAL {{ ?version bcn:hasXmlDocument ?xml }}
}}
ORDER BY ?fecha"""
    )
    # Deduplicar por URI: la fuente repite la misma version varias veces.
    por_uri: dict[str, VersionBCN] = {}
    marcadas_por_la_fuente: set[str] = set()
    for f in filas:
        uri = _v(f, "version")
        if not uri:
            continue
        if _v(f, "vigente") in ("1", "true"):
            marcadas_por_la_fuente.add(uri)
        if uri not in por_uri:
            por_uri[uri] = VersionBCN(
                uri=uri,
                fecha=_fecha(_v(f, "fecha")),
                es_vigente=False,
                url_html=_v(f, "html"),
                url_xml=_v(f, "xml"),
            )

    versiones = sorted(por_uri.values(), key=lambda v: (v.fecha or date.min, v.uri))
    if not versiones:
        return []

    # La vigente es la de fecha mas alta. **No la primera marcada por la
    # fuente**, que en la Ley 19.300 seria el texto de 1994.
    vigente = versiones[-1]
    vigente.es_vigente = True

    if marcadas_por_la_fuente and vigente.uri not in marcadas_por_la_fuente:
        # Los dos criterios discrepan. No se cambia la decision —la fecha manda—
        # pero se deja constancia: si esto empieza a pasar seguido, la fuente
        # cambio de forma y la regla hay que revisarla.
        logger.warning(
            "La version mas nueva de %s (%s) no viene marcada como vigente por "
            "la BCN. Se usa la fecha.",
            uri_norma,
            vigente.fecha,
        )

    return versiones
