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
    articulos_nuevos: int = 0
    #: Normas de las que se pudo bajar el texto. Las demas quedan con sus
    #: metadatos y su historial, que ya valen por si solos.
    con_texto: int = 0
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


def _guardar_articulado(
    db: Session, version_id, texto: TextoDeNorma, ahora: datetime
) -> int:
    """Escribe el articulado de una version. Devuelve cuantos articulos entraron.

    `external_article_id` guarda el `idParte` de Ley Chile, que es estable: por
    eso reimportar actualiza en vez de duplicar.

    **Un articulo derogado se guarda igual**, marcado con `effective_to`. Sacarlo
    dejaria huecos en la numeracion y volveria imposible responder que decia la
    norma en un periodo pasado — que es media auditoria.
    """
    entraron = 0
    for a in texto.articulos:
        ya = db.execute(
            text(
                "SELECT id FROM legal_articles "
                "WHERE norm_version_id = :v AND external_article_id = :e"
            ),
            {"v": version_id, "e": a.id_parte},
        ).scalar()

        datos = {
            "v": version_id,
            "e": a.id_parte,
            "tipo": a.tipo,
            "num": a.numero[:40],
            "texto": a.texto,
            "orden": a.orden,
            "desde": a.fecha_version,
            # `effective_to` marca el articulo derogado sin borrarlo.
            "hasta": a.fecha_version if a.derogado else None,
        }

        if ya:
            db.execute(
                text(
                    "UPDATE legal_articles SET article_type = :tipo, "
                    "article_number = :num, content = :texto, display_order = :orden, "
                    "effective_from = :desde, effective_to = :hasta WHERE id = :id"
                ),
                {**datos, "id": ya},
            )
            continue

        db.execute(
            text(
                "INSERT INTO legal_articles "
                "(norm_version_id, external_article_id, article_type, "
                " article_number, content, display_order, effective_from, "
                " effective_to) "
                "VALUES (:v, :e, :tipo, :num, :texto, :orden, :desde, :hasta)"
            ),
            datos,
        )
        entraron += 1
    return entraron


def sincronizar(
    db: Session, normas: list[NormaBCN], *, con_texto: bool = True
) -> Resultado:
    """Escribe las normas, sus versiones y su articulado. Devuelve que cambio.

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

        # ── El texto manda sobre SPARQL para la vigencia ─────────────────
        #
        # SPARQL da el historial de versiones, pero se quedo atras: para la Ley
        # 19.300 dice que la ultima es de 2010-11-13 y Ley Chile dice
        # **2024-04-10**. Marcar la de 2010 como vigente le diria a una empresa
        # que cumple con un texto que tiene catorce anos de atraso.
        texto = None
        if con_texto:
            try:
                texto = descargar_texto(n.leychile_code)
            except Exception:  # noqa: BLE001
                # Que falle la descarga del texto **no debe perder la norma**:
                # los metadatos y el historial de versiones ya se guardaron y
                # valen por si solos. Se reintenta en la proxima corrida.
                logger.warning(
                    "No se pudo bajar el texto de %s; se guarda sin articulado",
                    n.leychile_code,
                    exc_info=True,
                )

        if texto is not None and texto.fecha_version is not None:
            r.con_texto += 1
            db.execute(
                text("UPDATE legal_norms SET status = :st WHERE id = :id"),
                {
                    "st": "derogada" if texto.derogada else "vigente",
                    "id": norm_id,
                },
            )

            # La version que Ley Chile declara vigente puede no estar entre las
            # que dio SPARQL. Si no esta, se crea: es la que rige.
            chash = hashlib.sha256(
                f"{n.uri}@{texto.fecha_version}".encode()
            ).hexdigest()
            version_id = db.execute(
                text(
                    "SELECT id FROM legal_norm_versions "
                    "WHERE norm_id = :n AND content_hash = :h"
                ),
                {"n": norm_id, "h": chash},
            ).scalar()

            if version_id is None:
                version_id = db.execute(
                    text(
                        "INSERT INTO legal_norm_versions "
                        "(norm_id, version_label, valid_from, is_current, "
                        " external_version_id, content_hash, source_retrieved_at) "
                        "VALUES (:n, :etiqueta, :desde, true, :ext, :h, :ahora) "
                        "RETURNING id"
                    ),
                    {
                        "n": norm_id,
                        "etiqueta": f"Texto vigente al {texto.fecha_version:%d-%m-%Y}",
                        "desde": texto.fecha_version,
                        "ext": f"leychile@{texto.fecha_version}"[:100],
                        "h": chash,
                        "ahora": ahora,
                    },
                ).scalar_one()
                r.versiones_nuevas += 1

            db.execute(
                text(
                    "UPDATE legal_norm_versions SET is_current = (id = :id), "
                    "source_retrieved_at = :ahora WHERE norm_id = :n"
                ),
                {"id": version_id, "ahora": ahora, "n": norm_id},
            )
            r.articulos_nuevos += _guardar_articulado(db, version_id, texto, ahora)
            continue

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


# ── El texto de la norma, desde el XML de Ley Chile ───────────────────────
#
# **La vigencia sale de aca, no de SPARQL.** SPARQL da el historial de versiones
# y sirve para descubrir normas, pero se quedo atras: para la Ley 19.300 dice
# que la ultima version es de 2010-11-13 y el XML dice **2024-04-10**. Catorce
# anos de diferencia, y decirle a una empresa que cumple con el texto de 2010 es
# justo el error que este sistema existe para evitar.

#: Sin esto el sitio de Ley Chile responde **401 a todo**, incluida su propia
#: pagina de documentacion. No es autenticacion: es que rechaza a quien no se
#: identifica como navegador. Se perdio media tarde diagnosticandolo como un
#: problema de credenciales, que era la explicacion obvia y equivocada.
NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

XML_NORMA = "https://www.leychile.cl/Consulta/obtxml?opt=7&idNorma={codigo}"
ESQUEMA = "{http://www.leychile.cl/esquemas}"

#: Como se traduce `tipoParte` al vocabulario de `legal_articles`, que tiene
#: CHECK. Los transitorios se distinguen por el atributo `transitorio`, no por
#: el tipo: hay "Articulo Transitorio" pero tambien articulos comunes marcados
#: como transitorios.
TIPO_DE_PARTE = {
    "Artículo": "article",
    "Artículo Transitorio": "transitory",
    "Título": "subsection",
    "Párrafo": "paragraph",
}


@dataclass
class ArticuloBCN:
    id_parte: str
    tipo: str
    numero: str
    texto: str
    orden: int
    derogado: bool
    #: **Cada articulo tiene su propia fecha de version.** En la Ley 19.300 el
    #: articulo 1 es de 1994 y el 2 de 2023: la norma no cambia entera de golpe.
    fecha_version: date | None


@dataclass
class TextoDeNorma:
    codigo: str
    #: La fecha de la version vigente **segun Ley Chile**, que es la que manda.
    fecha_version: date | None
    derogada: bool
    articulos: list[ArticuloBCN] = field(default_factory=list)


def _numero_de_articulo(texto: str, orden: int) -> str:
    """El numero tal como lo escribe la ley: `Articulo 1°`, `TITULO I`.

    Se saca del texto porque el XML no lo trae como campo. Si no se reconoce se
    usa el orden — **nunca queda vacio**: `article_number` es NOT NULL y un
    articulo sin identificar no se puede citar en una auditoria.
    """
    import re

    # Se quitan comillas y espacios del principio: varios titulos vienen como
    # `"TITULO I`, y sin esto caian al numero por defecto.
    limpio = " ".join(texto.split()).lstrip("\"' “”")[:120]
    m = re.match(
        r"^(Art[íi]culo\s+[\w°ºsº]+"
        r"|T[ÍI]TULO\s+[IVXLC]+"
        r"|P[áa]rrafo\s+\S+)",
        limpio,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else f"Parte {orden}"


def descargar_texto(codigo_leychile: str, timeout: int = 90) -> TextoDeNorma:
    """El texto completo y vigente de una norma, con su articulado.

    No exige clave: se comprobo que responde igual con y sin ella. Lo que si
    exige es identificarse como navegador — ver `NAVEGADOR`.
    """
    import xml.etree.ElementTree as ET

    req = urllib.request.Request(
        XML_NORMA.format(codigo=codigo_leychile), headers={"User-Agent": NAVEGADOR}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        raiz = ET.fromstring(r.read())

    texto = TextoDeNorma(
        codigo=codigo_leychile,
        fecha_version=_fecha(raiz.get("fechaVersion")),
        derogada=raiz.get("derogado") == "derogado",
    )

    for orden, e in enumerate(raiz.iter(f"{ESQUEMA}EstructuraFuncional"), start=1):
        nodo = e.find(f"{ESQUEMA}Texto")
        contenido = (nodo.text or "").strip() if nodo is not None else ""
        if not contenido:
            continue

        tipo = TIPO_DE_PARTE.get(e.get("tipoParte", ""), "article")
        if e.get("transitorio") == "transitorio":
            tipo = "transitory"

        texto.articulos.append(
            ArticuloBCN(
                id_parte=e.get("idParte") or f"orden-{orden}",
                tipo=tipo,
                numero=_numero_de_articulo(contenido, orden),
                texto=contenido,
                orden=orden,
                derogado=e.get("derogado") == "derogado",
                fecha_version=_fecha(e.get("fechaVersion")),
            )
        )

    return texto
