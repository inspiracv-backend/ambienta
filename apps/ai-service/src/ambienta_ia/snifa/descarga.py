"""
Encontrar y bajar los CSV de SNIFA.

La lista de carpetas se lee de la página pública de Datos Abiertos y la de archivos, de la vista
embebida de cada carpeta de Drive. Así un cambio de id en Drive no rompe nada: se sigue el enlace
que publica la SMA.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

import httpx

PAGINA = "https://snifa.sma.gob.cl/DatosAbiertos"

# conjunto → (título de la tarjeta en la página, nombre del CSV en la carpeta)
CONJUNTOS = {
    "unidades": ("Unidades Fiscalizables e Instrumentos", "UF_Instrumentos.csv"),
    "sancionatorios": ("Sancionatorios", "Sancionatorios.csv"),
    "fiscalizaciones": ("Fiscalizaciones", "Fiscalizaciones.csv"),
}


@dataclass(frozen=True)
class Archivo:
    conjunto: str
    nombre: str
    id_drive: str


def carpetas(pagina_html: str) -> dict[str, str]:
    """Título de cada tarjeta → id de la carpeta de Drive."""
    salida = {}
    for m in re.finditer(r'<a href="https://drive\.google\.com/drive/(?:u/\d+/)?folders/([\w-]+)[^"]*"[^>]*>'
                         r'.*?<h4>([^<]+)</h4>', pagina_html, re.S):
        salida.setdefault(html.unescape(m.group(2)).strip(), m.group(1))
    return salida


def archivos_de_carpeta(vista_html: str) -> dict[str, str]:
    """Nombre del archivo → id de Drive, desde la vista embebida de la carpeta."""
    salida = {}
    for m in re.finditer(r'<a href="https://drive\.google\.com/file/d/([\w-]+)/[^"]*"[^>]*>.*?'
                         r'<div class="flip-entry-title">([^<]+)</div>', vista_html, re.S):
        salida[html.unescape(m.group(2)).strip()] = m.group(1)
    return salida


async def ubicar(http: httpx.AsyncClient) -> list[Archivo]:
    r = await http.get(PAGINA)
    r.raise_for_status()
    por_titulo = carpetas(r.text)
    salida = []
    for conjunto, (titulo, nombre) in CONJUNTOS.items():
        carpeta = por_titulo.get(titulo)
        if not carpeta:
            raise LookupError(f"La página de Datos Abiertos no tiene la tarjeta «{titulo}».")
        v = await http.get(f"https://drive.google.com/embeddedfolderview?id={carpeta}")
        v.raise_for_status()
        ids = archivos_de_carpeta(v.text)
        if nombre not in ids:
            raise LookupError(f"La carpeta de «{titulo}» no tiene {nombre} (hay: {', '.join(ids)}).")
        salida.append(Archivo(conjunto, nombre, ids[nombre]))
    return salida


async def bajar(http: httpx.AsyncClient, archivo: Archivo) -> bytes:
    """
    Los archivos grandes pasan por una página de "no se pudo analizar en busca de virus": se
    confirma con el `uuid` que trae esa página.
    """
    url = f"https://drive.google.com/uc?export=download&id={archivo.id_drive}"
    r = await http.get(url)
    r.raise_for_status()
    if b"<html" in r.content[:500].lower():
        uuid = re.search(rb'name="uuid" value="([^"]+)"', r.content)
        r = await http.get("https://drive.usercontent.google.com/download",
                           params={"id": archivo.id_drive, "export": "download", "confirm": "t",
                                   **({"uuid": uuid.group(1).decode()} if uuid else {})})
        r.raise_for_status()
        if b"<html" in r.content[:500].lower():
            raise RuntimeError(f"Drive no entregó {archivo.nombre}: devolvió una página, no el archivo.")
    return r.content
