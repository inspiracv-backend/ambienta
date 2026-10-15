"""Lo que el agente pregunta sobre SNIFA: antecedentes de unas unidades, y candidatas para una instalación."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..conocimiento import BaseConocimiento


@dataclass
class Antecedentes:
    unidad_id: int
    nombre: str
    comuna: str | None
    categoria: str | None
    enlace: str | None
    sancionatorios: list[dict] = field(default_factory=list)
    fiscalizaciones: int = 0
    ultima_fiscalizacion: str | None = None
    instrumentos: list[dict] = field(default_factory=list)


async def antecedentes(base: BaseConocimiento, unidad_ids: list[int]) -> list[Antecedentes]:
    if not unidad_ids:
        return []
    salida = []
    async with base.de_empresa(None) as conn:
        cur = await conn.execute("SELECT id, nombre, comuna, subcategoria, trim(enlace) FROM snifa_unidad "
                                 "WHERE id = ANY(%s) ORDER BY id", (unidad_ids,))
        for uid, nombre, comuna, cat, enlace in await cur.fetchall():
            a = Antecedentes(uid, nombre, comuna, cat, enlace)
            c = await conn.execute(
                "SELECT expediente, tipo, estado, fecha_inicio, fecha_termino, multa_uta, trim(enlace) "
                "FROM snifa_sancionatorio WHERE unidad_id = %s ORDER BY fecha_inicio DESC NULLS LAST", (uid,))
            a.sancionatorios = [
                {"expediente": e, "tipo": t, "estado": s, "inicio": i.isoformat() if i else None,
                 "termino": f.isoformat() if f else None, "multa_uta": float(m) if m is not None else None,
                 "enlace": enlace_s}
                for e, t, s, i, f, m, enlace_s in await c.fetchall()
            ]
            c = await conn.execute("SELECT count(*), max(make_date(anio, greatest(mes, 1), 1)) "
                                   "FROM snifa_fiscalizacion WHERE unidad_id = %s", (uid,))
            n, ultima = await c.fetchone()
            a.fiscalizaciones, a.ultima_fiscalizacion = n, ultima.isoformat()[:7] if ultima else None
            c = await conn.execute("SELECT sigla, descripcion, id_sea FROM snifa_instrumento WHERE unidad_id = %s "
                                   "ORDER BY sigla, descripcion", (uid,))
            a.instrumentos = [{"sigla": s, "descripcion": d, "id_sea": i} for s, d, i in await c.fetchall()]
            salida.append(a)
    return salida


async def unidades_por_id_sea(base: BaseConocimiento, ids_sea: list[str]) -> dict[str, list[int]]:
    """
    El vínculo confiable entre una instalación y SNIFA: el id del proyecto en el SEA. La SMA lo
    guarda como número con decimal ("94982.0"); el backend como texto ("2018050001").
    """
    normalizados = {str(i).split(".")[0].strip(): str(i) for i in ids_sea if str(i).strip()}
    if not normalizados:
        return {}
    async with base.de_empresa(None) as conn:
        cur = await conn.execute(
            "SELECT split_part(id_sea, '.', 1), array_agg(DISTINCT unidad_id) FROM snifa_instrumento "
            "WHERE split_part(id_sea, '.', 1) = ANY(%s) GROUP BY 1", (list(normalizados),))
        return {normalizados[k]: list(v) for k, v in await cur.fetchall()}


async def candidatas(base: BaseConocimiento, nombre: str, *, comuna: str | None = None,
                     latitud: float | None = None, longitud: float | None = None, n: int = 3) -> list[dict]:
    """
    Unidades fiscalizables que podrían ser una instalación. Es una sugerencia para confirmar,
    nunca un dato: dos plantas del mismo grupo en la misma comuna se parecen mucho.
    """
    async with base.de_empresa(None) as conn:
        cur = await conn.execute(
            """
            SELECT id, nombre, comuna, subcategoria,
                   similarity(nombre, %(nombre)s) AS sim,
                   CASE WHEN %(lat)s::float8 IS NULL OR latitud IS NULL THEN NULL
                        ELSE 111.0 * sqrt(power(latitud - %(lat)s, 2) + power((longitud - %(lon)s) * cos(radians(%(lat)s)), 2))
                   END AS km
              FROM snifa_unidad
             WHERE similarity(nombre, %(nombre)s) > 0.2
                OR (%(lat)s::float8 IS NOT NULL AND abs(latitud - %(lat)s) < 0.05 AND abs(longitud - %(lon)s) < 0.05)
             ORDER BY (CASE WHEN %(comuna)s::text IS NOT NULL AND lower(comuna) = lower(%(comuna)s) THEN 0.2 ELSE 0 END)
                      + similarity(nombre, %(nombre)s)
                      - coalesce(least(1.0, (111.0 * sqrt(power(latitud - %(lat)s, 2)
                                 + power((longitud - %(lon)s) * cos(radians(%(lat)s)), 2))) / 20.0), 0) DESC
             LIMIT %(n)s
            """,
            {"nombre": nombre, "comuna": comuna, "lat": latitud, "lon": longitud, "n": n},
        )
        return [{"unidad_id": i, "nombre": nm, "comuna": c, "subcategoria": s,
                 "similitud_nombre": round(float(sim), 2), "distancia_km": round(float(km), 1) if km is not None else None}
                for i, nm, c, s, sim, km in await cur.fetchall()]
