"""
Del articulado del backend a fragmentos que se pueden citar.

El handoff describe un árbol: `parent_article_id` arma título → capítulo → artículo. **Los datos
reales llegan planos** (verificado el 21/09/2026 contra el backend con el catálogo de la BCN):
`parent_article_id` viene vacío en los 689 artículos, los títulos y párrafos son filas sueltas
tipadas `subsection` / `paragraph` con el encabezado como texto, y la jerarquía solo se deduce
del orden (`display_order`). Además `article_number` pierde el sufijo: 11, 11 bis y 11 ter
llegan como "Artículo 11", y los transitorios repiten los números de los permanentes.

Por eso acá se soportan las dos formas: si hay `parent_article_id`, se recorre el árbol; si no,
se reconstruye la ruta por orden. En las dos, el número que se cita sale del encabezado del
texto ("Artículo 11 bis.-") y `article_number` queda como respaldo.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from ..backend.modelos import Articulo, Norma, VersionNorma
from ..citas import etiqueta_norma, numero_desde_texto, numero_normal

# Un artículo más largo se parte por párrafos. Las partes comparten la identidad (D-01).
MAX_CARACTERES = 1800

_TIPOS_ARTICULO = ("articulo", "artículo", "transitorio", "article", "transitory")
_TIPOS_TRANSITORIO = ("transitorio", "transitory")
_TIPOS_CONTENEDOR = (
    "titulo", "título", "capitulo", "capítulo", "parrafo", "párrafo", "libro", "seccion", "sección",
    "subsection", "paragraph", "title", "chapter", "section", "considerando",
)
_RE_EMPIEZA_ARTICULO = re.compile(r"^\W*art[íi]culo\s+\S", re.IGNORECASE)
_ETIQUETAS = {
    "titulo": "Título",
    "título": "Título",
    "capitulo": "Capítulo",
    "capítulo": "Capítulo",
    "parrafo": "Párrafo",
    "párrafo": "Párrafo",
    "libro": "Libro",
    "seccion": "Sección",
    "sección": "Sección",
    "articulo": "Artículo",
    "artículo": "Artículo",
    "transitorio": "Artículo transitorio",
    "transitory": "Artículo transitorio",
    "article": "Artículo",
    "subsection": "Título",
    "paragraph": "Párrafo",
    "inciso": "Inciso",
    "numeral": "Numeral",
    "letra": "Letra",
}


def _es_articulo(a: Articulo) -> bool:
    return a.article_type.lower() in _TIPOS_ARTICULO


def _etiqueta(a: Articulo) -> str:
    base = _ETIQUETAS.get(a.article_type.lower(), a.article_type.replace("_", " ").capitalize())
    return f"{base} {a.article_number}".strip() if a.article_number else base


def elegir_vigente(versiones: list[VersionNorma], hoy: date | None = None) -> VersionNorma | None:
    """
    La versión a indexar.

    La BCN marca más de una como vigente a la vez (ya pasó con la Ley 19.300: 1994 y 2010).
    Regla del handoff: `is_current`; si empata, la que empezó después.
    Si ninguna está marcada, la que rige hoy por fechas (`valid_to` null = todavía rige).
    """
    marcadas = [v for v in versiones if v.is_current]
    if not marcadas:
        hoy = hoy or date.today()
        marcadas = [
            v
            for v in versiones
            if (v.valid_from is None or v.valid_from <= hoy) and (v.valid_to is None or v.valid_to >= hoy)
        ]
    if not marcadas:
        return None
    return max(marcadas, key=lambda v: v.valid_from or date.min)


def armar_ruta(articulo: Articulo, por_id: dict[UUID, Articulo], norma: Norma) -> str:
    """'Ley 19.300 › Título II › Párrafo 2º › Artículo 11'."""
    cadena: list[str] = []
    actual: Articulo | None = articulo
    vistos: set[UUID] = set()
    while actual is not None and actual.id not in vistos:
        vistos.add(actual.id)
        cadena.append(_etiqueta(actual))
        actual = por_id.get(actual.parent_article_id) if actual.parent_article_id else None
    cadena.append(etiqueta_norma(norma.norm_type, norma.norm_number, norma.title))
    return " › ".join(reversed(cadena))


@dataclass
class FragmentoNuevo:
    article_id: UUID
    article_type: str
    article_number: str | None
    numero_normal: str | None
    parte: int
    total_partes: int
    ruta: str
    texto: str


def _partir(texto: str, maximo: int = MAX_CARACTERES) -> list[str]:
    """Por párrafos; un párrafo que solo ya excede, por oraciones. Nunca a mitad de oración."""
    if len(texto) <= maximo:
        return [texto]
    unidades: list[str] = []
    for parrafo in [p.strip() for p in re.split(r"\n\s*\n|\n", texto) if p.strip()]:
        if len(parrafo) <= maximo:
            unidades.append(parrafo)
        else:
            unidades.extend(o.strip() for o in re.split(r"(?<=[.;:])\s+", parrafo) if o.strip())
    partes: list[str] = []
    actual = ""
    for u in unidades:
        if actual and len(actual) + 1 + len(u) > maximo:
            partes.append(actual)
            actual = u
        else:
            actual = f"{actual}\n{u}" if actual else u
    if actual:
        partes.append(actual)
    return partes


def _articulo_de(a: Articulo, por_id: dict[UUID, Articulo]) -> Articulo | None:
    """El artículo que se cita para este nodo: él mismo o su ancestro artículo más cercano."""
    actual: Articulo | None = a
    while actual is not None:
        if _es_articulo(actual):
            return actual
        actual = por_id.get(actual.parent_article_id) if actual.parent_article_id else None
    return None


def _es_encabezado(a: Articulo) -> bool:
    """
    Una fila que es un título o párrafo, aunque venga tipada como artículo: en la Ley 19.300
    la fila "ARTICULOS TRANSITORIOS" llega como `transitory`.
    """
    tipo = a.article_type.lower()
    if tipo in _TIPOS_CONTENEDOR:
        return True
    texto = (a.content or "").strip()
    if tipo not in _TIPOS_ARTICULO or _RE_EMPIEZA_ARTICULO.match(texto) or len(texto) >= 200:
        return False
    # Solo si parece un rótulo: primera línea en mayúsculas. Un considerando corto de una RCA
    # ("Considerando 9.2.- El titular deberá...") es texto citable, no un título.
    lineas = _lineas(texto)
    return bool(lineas) and lineas[0].isupper()


def _lineas(texto: str | None) -> list[str]:
    return [x.strip().strip('"').strip() for x in (texto or "").splitlines() if x.strip().strip('"').strip()]


def _titular(linea: str) -> str:
    """'TITULO II' → 'Título II'; 'ARTICULOS TRANSITORIOS' → 'Artículos transitorios'."""
    if not linea.isupper():
        return linea
    palabras = []
    for i, p in enumerate(linea.split()):
        if re.fullmatch(r"[IVXLCDM]+", p):
            palabras.append(p)
        else:
            p = p.lower().replace("titulo", "título").replace("articulo", "artículo").replace("capitulo", "capítulo")
            palabras.append(p.capitalize() if i == 0 else p)
    return " ".join(palabras)


def _etiqueta_encabezado(a: Articulo) -> tuple[str, int]:
    """(etiqueta, nivel). Nivel 1: título, libro, transitorios. Nivel 2: párrafo, capítulo."""
    lineas = _lineas(a.content) or [_etiqueta(a)]
    nombre = _titular(lineas[0])
    if a.heading:
        nombre = f"{nombre} · {a.heading.strip()}"
    elif len(lineas) > 1 and len(lineas[1]) < 120:
        sub = lineas[1]
        nombre = f"{nombre} · {sub[0] + sub[1:].lower() if sub.isupper() else sub}"
    plano = lineas[0].lower()
    nivel = 1 if re.match(r"^(t[ií]tulo|libro|art[ií]culos transitorios|disposiciones)", plano) else 2
    if a.article_type.lower() == "subsection":
        nivel = 1
    return nombre, nivel


@dataclass
class _Citable:
    articulo: Articulo
    numero: str | None  # normalizado: "11 bis", "1 transitorio"
    ruta: str


def _numero_citable(a: Articulo, transitorio: bool) -> str | None:
    return numero_desde_texto(a.content, transitorio=transitorio) or numero_normal(
        a.article_number, "transitorio" if transitorio else a.article_type
    )


def _citables_arbol(norma: Norma, articulos: list[Articulo]) -> list[_Citable]:
    por_id = {a.id: a for a in articulos}
    salida = []
    for a in sorted(articulos, key=lambda a: a.display_order):
        if not (a.content and a.content.strip()):
            continue
        ancestro = por_id.get(a.parent_article_id) if a.parent_article_id else None
        cubierto = False
        while ancestro is not None:
            if ancestro.content and ancestro.content.strip():
                cubierto = True
                break
            ancestro = por_id.get(ancestro.parent_article_id) if ancestro.parent_article_id else None
        if cubierto:
            continue
        citado = _articulo_de(a, por_id) or a
        transitorio = citado.article_type.lower() in _TIPOS_TRANSITORIO
        numero = _numero_citable(citado, transitorio) if citado is a else (
            numero_desde_texto(citado.content, transitorio=transitorio)
            or numero_normal(citado.article_number, citado.article_type))
        salida.append(_Citable(a, numero, armar_ruta(a, por_id, norma)))
    return salida


def _citables_por_orden(norma: Norma, articulos: list[Articulo]) -> list[_Citable]:
    """La forma en que llegan los datos reales: filas planas, títulos y párrafos intercalados."""
    raiz = etiqueta_norma(norma.norm_type, norma.norm_number, norma.title)
    nivel1: str | None = None
    nivel2: str | None = None
    en_transitorios = False
    salida = []
    for a in sorted(articulos, key=lambda a: a.display_order):
        if not (a.content and a.content.strip()):
            continue
        if _es_encabezado(a):
            nombre, nivel = _etiqueta_encabezado(a)
            if nivel == 1:
                nivel1, nivel2 = nombre, None
            else:
                nivel2 = nombre
            if "transitori" in nombre.lower():
                en_transitorios = True
            continue
        transitorio = en_transitorios or a.article_type.lower() in _TIPOS_TRANSITORIO
        numero = _numero_citable(a, transitorio)
        etiqueta = f"Artículo {numero}" if numero else _etiqueta(a)
        ruta = " › ".join(x for x in (raiz, nivel1, nivel2, etiqueta) if x)
        salida.append(_Citable(a, numero, ruta))
    return salida


def fragmentar_norma(norma: Norma, articulos: list[Articulo]) -> list[FragmentoNuevo]:
    """
    Los fragmentos de una versión. Los títulos y párrafos no son fragmentos: son la ruta.

    Con árbol: se indexa cada nodo con texto cuyo ancestro no tenga texto (si el artículo trae
    su contenido completo, sus incisos no se repiten). Sin árbol: se reconstruye por orden.
    """
    hay_arbol = any(a.parent_article_id for a in articulos)
    citables = _citables_arbol(norma, articulos) if hay_arbol else _citables_por_orden(norma, articulos)

    salida: list[FragmentoNuevo] = []
    for c in citables:
        partes = _partir((c.articulo.content or "").strip())
        for i, texto in enumerate(partes, start=1):
            salida.append(
                FragmentoNuevo(
                    article_id=c.articulo.id,
                    article_type=c.articulo.article_type,
                    article_number=c.numero or c.articulo.article_number,
                    numero_normal=c.numero,
                    parte=i,
                    total_partes=len(partes),
                    ruta=c.ruta,
                    texto=texto,
                )
            )
    return salida


def texto_para_embedding(titulo: str, ruta: str, texto: str) -> str:
    """
    Lo que se convierte en vector. Lleva el título de la norma y la ruta además del texto: un
    artículo suelto no dice que es de una RCA, ni de qué capítulo sale.

    Es la misma función al indexar y al comparar en vivo; si cambia, hay que reindexar.
    """
    return f"{titulo}\n{ruta}\n\n{texto}"


def hash_de_articulos(articulos: list[Articulo]) -> str:
    """Si el backend no manda `content_hash`, se calcula igual de estable."""
    h = hashlib.sha256()
    for a in sorted(articulos, key=lambda a: a.display_order):
        h.update(str(a.id).encode())
        h.update((a.content or "").encode())
    return h.hexdigest()
