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

import hashlib
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

ENDPOINT = "https://datos.bcn.cl/sparql"
BCN_NORMS = "http://datos.bcn.cl/ontologies/bcn-norms#"

#: Tipos de norma de la BCN que interesan para cumplimiento ambiental.
#:
#: La BCN tiene 748.000 normas, la enorme mayoria irrelevante —concesiones de
#: acuicultura, nombramientos—. Traerlas todas no es exhaustividad: es ruido que
#: despues alguien tiene que clasificar a mano.
TIPOS = ("ley", "dfl", "ds", "decreto", "res")

#: Id de `legal_sources` de la BCN, y de Chile en `countries`. Sembrados en
#: `db/02_seed.sql`; se resuelven por codigo al sincronizar, no se cablean.
CODIGO_FUENTE = "BCN_LEYCHILE"
NOMBRE_PAIS = "Chile"

#: Como se traduce el tipo de la BCN al vocabulario de `legal_norms`.
#:
#: La columna no tiene CHECK, pero los valores sembrados son estos tres. Meter
#: el tipo crudo de la fuente crearia un cuarto y un quinto sin que nadie lo
#: decida, y las pantallas que agrupan por tipo empezarian a mostrar categorias
#: nuevas de la nada.
TIPO_DE_NORMA = {
    "ley": "ley",
    "dfl": "ley",
    "dl": "ley",
    "ds": "decreto_supremo",
    "decreto": "decreto_supremo",
    "res": "resolucion",
}
TIPO_POR_DEFECTO = "resolucion"


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
    #: Normas de ejemplo del seed que pasaron a ser las reales, conservando su
    #: clasificacion por sector.
    adoptadas: int = 0
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


def _tipo_desde_uri(uri: str | None, tipo_declarado: str | None) -> str:
    """De que tipo es la norma. **Sale de la URI, no del `rdf:type`.**

    Parece al reves y no lo es: la Ley 19.300 **no declara** su tipo como
    `rdf:type` —solo dice `Norm` y `RootNorm`— mientras que una resolucion si
    declara `norma/tipo#res`. Confiar en el tipo declarado dejaba las leyes
    cayendo al valor por defecto, y la Ley de Bases Generales del Medio Ambiente
    quedaba guardada como "resolucion".

    La URI, en cambio, siempre lo lleva:
    `/recurso/cl/{tipo}/{organismo}/{fecha}/{numero}`. Se usa el tipo declarado
    solo como respaldo.
    """
    if uri:
        partes = uri.split("/recurso/cl/", 1)
        if len(partes) == 2:
            candidato = partes[1].split("/", 1)[0]
            if candidato in TIPO_DE_NORMA:
                return candidato
    if tipo_declarado:
        return tipo_declarado.split("#")[-1]
    return "norma"


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
        normas.append(
            NormaBCN(
                uri=uri,
                leychile_code=_v(f, "codigo") or "",
                tipo=_tipo_desde_uri(uri, _v(f, "tipo")),
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


# ── Escribir lo leido en la base ──────────────────────────────────────────


def _hash_de_version(v: VersionBCN) -> str:
    """Identifica la version de forma estable, para poder reimportar sin duplicar.

    `legal_norm_versions` exige `content_hash` y lo usa como clave unica junto
    con la norma. Como todavia **no tenemos el texto** —eso necesita la clave de
    Ley Chile— se calcula sobre la URI de la version, que es estable en la
    fuente.

    Cuando llegue el texto, el hash pasara a calcularse sobre el contenido y una
    version cuyo texto cambio se distinguira de una que no. Hasta entonces esto
    cumple lo unico que hace falta hoy: **que correr la sincronizacion dos veces
    no cree dos filas**.
    """
    return hashlib.sha256(v.uri.encode("utf-8")).hexdigest()


def sincronizar(db: Session, normas: list[NormaBCN]) -> Resultado:
    """Escribe las normas y sus versiones. Devuelve que cambio.

    **No hace `commit`.** Quien llama decide, para poder correrlo en seco.

    ## Que no toca

    `norm_sectors` —a que sector aplica cada norma— **es trabajo humano** y no se
    modifica nunca. Sincronizar no puede destruir el criterio que alguien
    aplico; si lo hiciera, cada corrida borraria la clasificacion y el sistema
    volveria a no proponer nada.

    Tampoco se borra ninguna norma. Que la BCN deje de devolver una en una
    busqueda no significa que se haya derogado: significa que la busqueda fue
    distinta.

    ## Por que interesa `con_version_nueva`

    Son las normas cuya version vigente cambio respecto de lo que teniamos. Cada
    una puede tener empresas con su matriz evaluada contra el texto anterior, y
    es exactamente lo que la pantalla de la matriz avisa.
    """
    r = Resultado(consultadas=len(normas))
    ahora = datetime.now(timezone.utc)

    fuente_id = db.execute(
        text("SELECT id FROM legal_sources WHERE code = :c"), {"c": CODIGO_FUENTE}
    ).scalar_one()
    pais_id = db.execute(
        text("SELECT id FROM countries WHERE name = :n"), {"n": NOMBRE_PAIS}
    ).scalar_one()

    for n in normas:
        if not n.leychile_code:
            # Sin identificador estable no hay forma de reconocerla la proxima
            # corrida, y se duplicaria en cada una.
            logger.warning("Norma sin leychileCode, se omite: %s", n.uri)
            continue

        existente = db.execute(
            text(
                "SELECT id FROM legal_norms "
                "WHERE source_id = :s AND external_norm_id = :e"
            ),
            {"s": fuente_id, "e": n.leychile_code},
        ).scalar()

        if existente is None and n.numero:
            # **Se adopta la norma sembrada en vez de crear una al lado.**
            #
            # El catalogo trae normas de ejemplo sin identificador externo, y
            # con el mismo numero que las reales. Crear una fila nueva las
            # duplicaria — pero el problema de fondo es otro: `norm_sectors`,
            # que es la clasificacion por sector y **el trabajo humano que hace
            # funcionar todo el CORE**, esta pegada a la fila sembrada. Duplicar
            # dejaria la clasificacion en la copia falsa y la norma real sin
            # nada, y la matriz de las empresas se vaciaria sin ningun error.
            #
            # Adoptar convierte la fila de ejemplo en la real conservando lo que
            # alguien clasifico.
            existente = db.execute(
                text(
                    "SELECT id FROM legal_norms "
                    "WHERE source_id = :s AND external_norm_id IS NULL "
                    "AND norm_number = :num AND deleted_at IS NULL "
                    "LIMIT 1"
                ),
                {"s": fuente_id, "num": n.numero},
            ).scalar()
            if existente:
                logger.info(
                    "Se adopta la norma sembrada %s con los datos reales de la BCN",
                    n.numero,
                )
                db.execute(
                    text(
                        "UPDATE legal_norms SET external_norm_id = :e WHERE id = :id"
                    ),
                    {"e": n.leychile_code, "id": existente},
                )
                r.adoptadas += 1

        datos = {
            "titulo": n.titulo,
            "tipo": TIPO_DE_NORMA.get(n.tipo, TIPO_POR_DEFECTO),
            "numero": n.numero,
            "organismo": n.organismo,
            "pub": n.publicacion,
            "prom": n.promulgacion,
            "url": f"https://www.leychile.cl/Navegar?idNorma={n.leychile_code}",
            "payload": json.dumps({"uri": n.uri, "tipo_bcn": n.tipo}),
            "ahora": ahora,
        }

        if existente:
            db.execute(
                text(
                    "UPDATE legal_norms SET title = :titulo, norm_type = :tipo, "
                    "norm_number = :numero, issuing_body = :organismo, "
                    "publication_date = :pub, promulgation_date = :prom, "
                    "official_url = :url, source_payload = CAST(:payload AS jsonb), "
                    "last_source_sync_at = :ahora "
                    "WHERE id = :id"
                ),
                {**datos, "id": existente},
            )
            norm_id = existente
            r.actualizadas += 1
        else:
            norm_id = db.execute(
                text(
                    "INSERT INTO legal_norms "
                    "(country_id, source_id, external_norm_id, norm_type, "
                    " norm_number, title, issuing_body, publication_date, "
                    " promulgation_date, status, official_url, source_payload, "
                    " last_source_sync_at) "
                    "VALUES (:pais, :fuente, :ext, :tipo, :numero, :titulo, "
                    " :organismo, :pub, :prom, 'vigente', :url, "
                    " CAST(:payload AS jsonb), :ahora) RETURNING id"
                ),
                {**datos, "pais": pais_id, "fuente": fuente_id, "ext": n.leychile_code},
            ).scalar_one()
            r.nuevas += 1

        vigente_antes = db.execute(
            text(
                "SELECT external_version_id FROM legal_norm_versions "
                "WHERE norm_id = :n AND is_current AND deleted_at IS NULL"
            ),
            {"n": norm_id},
        ).scalar()

        for v in n.versiones:
            if v.fecha is None:
                # `valid_from` es NOT NULL. Una version sin fecha no se puede
                # ubicar en la linea de tiempo, que es para lo unico que sirve.
                logger.warning("Version sin fecha, se omite: %s", v.uri)
                continue

            chash = _hash_de_version(v)
            ya = db.execute(
                text(
                    "SELECT id FROM legal_norm_versions "
                    "WHERE norm_id = :n AND content_hash = :h"
                ),
                {"n": norm_id, "h": chash},
            ).scalar()

            if ya:
                db.execute(
                    text(
                        "UPDATE legal_norm_versions SET is_current = :vig, "
                        "source_retrieved_at = :ahora WHERE id = :id"
                    ),
                    {"vig": v.es_vigente, "ahora": ahora, "id": ya},
                )
                continue

            db.execute(
                text(
                    "INSERT INTO legal_norm_versions "
                    "(norm_id, version_label, valid_from, is_current, "
                    " external_version_id, content_hash, source_retrieved_at) "
                    "VALUES (:n, :etiqueta, :desde, :vig, :ext, :h, :ahora)"
                ),
                {
                    "n": norm_id,
                    "etiqueta": f"Texto vigente al {v.fecha:%d-%m-%Y}",
                    "desde": v.fecha,
                    "vig": v.es_vigente,
                    # **El sufijo, no la URI entera.** `external_version_id` es
                    # `varchar(100)` y las URI de la BCN pasan de 110. El sufijo
                    # (`es@1994-03-09`) identifica la version dentro de su norma,
                    # que es el alcance de la restriccion unica, y la URI
                    # completa se reconstruye con `source_payload.uri`.
                    "ext": v.uri.rsplit("/", 1)[-1][:100],
                    "h": chash,
                    "ahora": ahora,
                },
            )
            r.versiones_nuevas += 1

        # **Solo una version puede estar vigente.** La norma sembrada traia la
        # suya marcada, y al adoptarla quedaban dos: la de ejemplo y la real.
        # Dos vigentes rompen la deteccion de matrices desactualizadas —no hay
        # contra cual comparar— y no hay ningun error que lo delate.
        vigente = next((v for v in n.versiones if v.es_vigente), None)
        if vigente is not None:
            db.execute(
                text(
                    "UPDATE legal_norm_versions SET is_current = false "
                    "WHERE norm_id = :n AND content_hash <> :h AND is_current"
                ),
                {"n": norm_id, "h": _hash_de_version(vigente)},
            )

        vigente_ahora = (
            vigente.uri.rsplit("/", 1)[-1][:100] if vigente is not None else None
        )
        if vigente_antes and vigente_ahora and vigente_antes != vigente_ahora:
            r.con_version_nueva.append(n.titulo)

    return r
