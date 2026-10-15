"""
Cargar los CSV de SNIFA en la base del AI Service.

Los archivos vienen en ISO-8859-1, separados por punto y coma, con fechas dd-mm-aaaa y enlaces
con espacios de relleno. Cada conjunto se reemplaza entero en una transacción, y antes de
reemplazar los sancionatorios se calcula qué hay de nuevo: es lo que usa el monitoreo.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx

from ..conocimiento import BaseConocimiento
from .descarga import Archivo, bajar, ubicar


@dataclass
class ResultadoCarga:
    conjunto: str
    filas: int
    sin_cambios: bool = False
    actualizado_sma: str | None = None
    # solo sancionatorios: lo que el monitoreo tiene que avisar
    nuevos: list[int] = field(default_factory=list)
    cambios_de_estado: list[tuple[int, str, str]] = field(default_factory=list)  # id, antes, ahora


def _filas(contenido: bytes) -> list[dict[str, str]]:
    texto = contenido.decode("latin-1")
    lector = csv.DictReader(io.StringIO(texto), delimiter=";")
    return [{k.strip(): (v or "").strip() for k, v in fila.items() if k} for fila in lector]


def _fecha(v: str) -> date | None:
    try:
        return datetime.strptime(v, "%d-%m-%Y").date() if v else None
    except ValueError:
        return None


def _entero(v: str) -> int | None:
    try:
        return int(float(v)) if v else None
    except ValueError:
        return None


def _numero(v: str) -> float | None:
    try:
        return float(v) if v else None
    except ValueError:
        return None


def _unidades(filas: list[dict]) -> tuple[list[tuple], list[tuple]]:
    unidades: dict[int, tuple] = {}
    instrumentos: dict[tuple[int, int], tuple] = {}
    for f in filas:
        uid = _entero(f.get("UnidadFiscalizableId", ""))
        if uid is None:
            continue
        unidades.setdefault(uid, (uid, f.get("Nombre"), f.get("RegionNombre"), f.get("ComunaNombre"),
                                  _numero(f.get("Latitud", "")), _numero(f.get("Longitud", "")),
                                  f.get("CategoriaEconomicaNombre"), f.get("SubCategoriaEconomicaNombre"),
                                  f.get("LinkSNIFA")))
        iid = _entero(f.get("InstrumentoSmaId", ""))
        if iid is not None:
            instrumentos[(uid, iid)] = (uid, iid, f.get("SiglaInstrumento"), f.get("DescripcionCorta"),
                                        f.get("DescripcionLarga"), f.get("IdSea"), f.get("LinkDocumentoExterno"))
    return list(unidades.values()), list(instrumentos.values())


def _sancionatorios(filas: list[dict]) -> list[tuple]:
    salida = {}
    for f in filas:
        sid = _entero(f.get("ProcesoSancionId", ""))
        if sid is None:
            continue
        salida[sid] = (sid, f.get("Expediente"), f.get("ProcesoSancionTipoNombre"), f.get("ProcesoSancionEstado"),
                       _fecha(f.get("FechaInicio", "")), _fecha(f.get("FechaTermino", "")),
                       f.get("ConfirmaPdC", "").lower().startswith("s"), _numero(f.get("MultaTotalUTA", "")),
                       f.get("LinkSNIFA"), _entero(f.get("UnidadFiscalizableId", "")))
    return list(salida.values())


def _fiscalizaciones(filas: list[dict]) -> list[tuple]:
    salida = {}
    for f in filas:
        fid = _entero(f.get("ProcesoFiscalizacionId", ""))
        if fid is None:
            continue
        salida[fid] = (fid, f.get("Expediente"), _entero(f.get("Ano", "")), _entero(f.get("Mes", "")),
                       f.get("OrganismoPublico"), f.get("LinkSNIFA"), _entero(f.get("UnidadFiscalizableId", "")))
    return list(salida.values())


async def cargar_conjunto(base: BaseConocimiento, conjunto: str, contenido: bytes,
                          archivo_id: str = "local") -> ResultadoCarga:
    sha = hashlib.sha256(contenido).hexdigest()
    async with base.transaccion() as conn:
        cur = await conn.execute("SELECT sha256 FROM snifa_carga WHERE conjunto = %s", (conjunto,))
        previo = await cur.fetchone()
    filas = _filas(contenido)
    actualizado = next((f.get("FechaActualizacion") for f in filas if f.get("FechaActualizacion")), None)
    if previo and previo[0] == sha:
        return ResultadoCarga(conjunto, len(filas), sin_cambios=True, actualizado_sma=actualizado)

    r = ResultadoCarga(conjunto, len(filas), actualizado_sma=actualizado)
    async with base.transaccion() as conn:
        async with conn.cursor() as c:
            if conjunto == "unidades":
                unidades, instrumentos = _unidades(filas)
                await c.execute("TRUNCATE snifa_unidad, snifa_instrumento")
                await c.executemany("INSERT INTO snifa_unidad VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", unidades)
                await c.executemany("INSERT INTO snifa_instrumento VALUES (%s,%s,%s,%s,%s,%s,%s)", instrumentos)
                r.filas = len(unidades)
            elif conjunto == "sancionatorios":
                nuevas = _sancionatorios(filas)
                cur = await conn.execute("SELECT id, estado FROM snifa_sancionatorio")
                antes = dict(await cur.fetchall())
                if previo:  # la primera carga no es "novedad": es el punto de partida
                    r.nuevos = [s[0] for s in nuevas if s[0] not in antes]
                    r.cambios_de_estado = [(s[0], antes[s[0]], s[3]) for s in nuevas
                                           if s[0] in antes and antes[s[0]] != s[3]]
                await c.execute("TRUNCATE snifa_sancionatorio")
                await c.executemany("INSERT INTO snifa_sancionatorio VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", nuevas)
                r.filas = len(nuevas)
            elif conjunto == "fiscalizaciones":
                nuevas = _fiscalizaciones(filas)
                await c.execute("TRUNCATE snifa_fiscalizacion")
                await c.executemany("INSERT INTO snifa_fiscalizacion VALUES (%s,%s,%s,%s,%s,%s,%s)", nuevas)
                r.filas = len(nuevas)
            else:
                raise ValueError(f"Conjunto desconocido: {conjunto}")
        await conn.execute(
            """INSERT INTO snifa_carga (conjunto, archivo_id, sha256, filas, actualizado_sma)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (conjunto) DO UPDATE SET archivo_id = EXCLUDED.archivo_id, sha256 = EXCLUDED.sha256,
                   filas = EXCLUDED.filas, actualizado_sma = EXCLUDED.actualizado_sma, cargado_en = now()""",
            (conjunto, archivo_id, sha, r.filas, actualizado),
        )
    return r


async def sincronizar_snifa(base: BaseConocimiento, *, http: httpx.AsyncClient | None = None) -> list[ResultadoCarga]:
    propio = http is None
    http = http or httpx.AsyncClient(timeout=300, follow_redirects=True)
    try:
        archivos: list[Archivo] = await ubicar(http)
        resultados = []
        for a in archivos:
            resultados.append(await cargar_conjunto(base, a.conjunto, await bajar(http, a), a.id_drive))
        return resultados
    finally:
        if propio:
            await http.aclose()
