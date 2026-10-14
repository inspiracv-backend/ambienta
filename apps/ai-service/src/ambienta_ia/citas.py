"""
Cómo se nombra una norma y un artículo, en la pregunta y en los datos.

La búsqueda exacta (D-03) solo sirve si "DS 40", "D.S. N° 40" y "decreto supremo 40" llegan a
la misma clave que el `norm_type` + `norm_number` del backend ("decreto_supremo", "40/2012").
Este módulo es esa equivalencia, y la usan tanto el sincronizador (al guardar) como la
recuperación (al buscar).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _plano(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower().replace("_", " "))
    return "".join(c for c in t if not unicodedata.combining(c))


# El orden importa: lo más largo primero ("decreto con fuerza de ley" antes que "decreto").
_TIPOS: list[tuple[str, str]] = [
    (r"decreto\s+con\s+fuerza\s+de\s+ley|d\.?\s?f\.?\s?l\.?", "dfl"),
    (r"decreto\s+ley|d\.\s?l\.|\bdl\b", "dl"),
    (r"decreto\s+supremo|d\.\s?s\.?|\bds\b|decreto", "ds"),
    (r"resolucion\s+exenta|res\.?\s*ex\.?|resolucion|\bres\b", "res"),
    (r"\bley\b", "ley"),
]

_NUMERO = r"(?:n\s*[°º.o]?\s*|numero\s+)?(\d[\d.]*(?:\s*[/-]\s*\d{2,4})?)"

_RE_NORMA = [(re.compile(rf"(?:{tipo})\s*{_NUMERO}"), clave) for tipo, clave in _TIPOS]

_ORDINALES = {
    "primero": "1", "segundo": "2", "tercero": "3", "cuarto": "4", "quinto": "5", "sexto": "6",
    "septimo": "7", "octavo": "8", "noveno": "9", "decimo": "10", "unico": "unico",
}
_SUFIJOS = r"bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies"
_NUMERO_ART = r"(\d+|" + "|".join(_ORDINALES) + r")"

_RE_ARTICULO = re.compile(
    r"\bart(?:iculo|\.)?s?\s*(?:n\s*[°º.o]?\s*)?" + _NUMERO_ART + r"\s*(?:[°º]|o\b)?"
    r"(?:\s*(" + _SUFIJOS + r"))?"
    r"(\s+transitori[oa])?",
)

# Nota: al quitar tildes, "º" (indicador ordinal) se vuelve la letra "o": "7º" → "7o".
# El encabezado con que empieza el texto de un artículo en la BCN: "Artículo 11 bis.-",
# "Artículo 1° transitorio", "Artículo primero:". Es más confiable que `article_number`, que
# en los datos reales pierde el sufijo (11, 11 bis y 11 ter llegan los tres como "Artículo 11").
_RE_ENCABEZADO = re.compile(
    r"^\W*art[ií]culo\s+" + _NUMERO_ART + r"\s*(?:[°º]|o\b)?\s*(?:(" + _SUFIJOS + r")\b)?\s*(transitori[oa])?",
)


def _numero(base: str, sufijo: str | None, transitorio: bool) -> str:
    partes = [_ORDINALES.get(base, base.lstrip("0") or "0")]
    if sufijo:
        partes.append(sufijo)
    if transitorio:
        partes.append("transitorio")
    return " ".join(partes)


def numero_desde_texto(contenido: str | None, *, transitorio: bool = False) -> str | None:
    """'Artículo 11 bis.- Los proponentes...' → '11 bis'. None si el texto no empieza así."""
    if not contenido:
        return None
    m = _RE_ENCABEZADO.match(_plano(contenido.strip().lstrip('"')))
    if not m:
        m2 = re.match(r"^\W*art[ií]culo\s+transitori[oa]\b", _plano(contenido.strip()))
        return "unico transitorio" if m2 else None
    return _numero(m.group(1), m.group(2), transitorio or bool(m.group(3)))


def _numero_base(numero: str) -> str:
    """'19.300' → '19300'; '40/2012' → '40'. El año no es parte de la clave."""
    base = re.split(r"\s*[/-]\s*", numero.strip())[0]
    return base.replace(".", "").lstrip("0") or "0"


def normalizar_norma(texto: str | None) -> str | None:
    """Devuelve 'ley/19300', 'ds/40', etc., o None si no reconoce una norma con número."""
    if not texto:
        return None
    plano = _plano(texto)
    for patron, clave in _RE_NORMA:
        m = patron.search(plano)
        if m:
            return f"{clave}/{_numero_base(m.group(1))}"
    return None


def numero_normal(article_number: str | None, article_type: str = "") -> str | None:
    """Número de artículo comparable: '10 bis', '1 transitorio', '11'."""
    if not article_number:
        return None
    t = _plano(article_number)
    t = re.sub(r"^(articulo|art\.?)\s*", "", t)
    t = re.sub(r"[°º]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if "transitori" in _plano(article_type) and "transitorio" not in t:
        t = f"{t} transitorio"
    return t


@dataclass(frozen=True)
class CitaDetectada:
    articulo: str | None
    norma: str | None

    def __bool__(self) -> bool:
        return self.articulo is not None


def detectar_cita(pregunta: str) -> CitaDetectada:
    """
    Lee la pregunta y ve si nombra un artículo y/o una norma por su número.

    Es deliberadamente simple: si acierta, gana precisión; si no detecta nada, la búsqueda
    sigue por significado, que es el comportamiento normal.
    """
    plano = _plano(pregunta)
    m = _RE_ARTICULO.search(plano)
    articulo = _numero(m.group(1), m.group(2), bool(m.group(3))) if m else None
    # La norma se busca en el texto sin el tramo del artículo, para no leer "artículo 11" como
    # una norma.
    resto = plano[: m.start()] + " " + plano[m.end() :] if m else plano
    return CitaDetectada(articulo=articulo, norma=normalizar_norma(resto))


_ETIQUETA_TIPO = {
    "ley": "Ley",
    "decreto supremo": "DS",
    "decreto": "Decreto",
    "decreto con fuerza de ley": "DFL",
    "decreto ley": "DL",
    "resolucion": "Resolución",
    "resolucion exenta": "Resolución Exenta",
}


def etiqueta_norma(norm_type: str, norm_number: str | None, titulo: str) -> str:
    """'Ley 19.300', 'DS 40/2012'. Sin número, el título."""
    if not norm_number:
        return titulo
    tipo = _ETIQUETA_TIPO.get(_plano(norm_type), norm_type.replace("_", " ").capitalize())
    return f"{tipo} {norm_number}"
