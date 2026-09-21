"""Traer el catalogo normativo desde la BCN (RF-17).

## Por que esta tarea existe

`services/bcn.py` sabe buscar, leer versiones y guardar articulado desde el
25-ago-2026. Pero **nadie la llamaba**: no habia router ni tarea. La
sincronizacion se corrio una vez desde un script suelto y el dato **no
sobrevivio** — medido: las 8 normas del catalogo tienen `last_source_sync_at`
en `nunca` y la Ley 19.300 tiene 2 articulos, no los 151 que decia CLAUDE.md.

Es el mismo patron que tuvo `audit_log`: la pieza lista, sin nadie que la use, y
un numero publicado que ya no era cierto.

## Que normas se traen, y por que no todas

La BCN tiene **748.000 normas** y la enorme mayoria son nombramientos y
concesiones de acuicultura. Traerlas todas no es exhaustividad: es ruido que
despues alguien tiene que clasificar a mano, una por una.

Se traen las de `TERMINOS`, que son **las que ya estan clasificadas por sector**
en `norm_sectors`. Ese vinculo es el trabajo humano que hace funcionar el CORE,
y sincronizar **adopta la fila sembrada en vez de crear una al lado**, asi que
la clasificacion se conserva y pasa a apuntar a la norma real.

Ampliar la lista es agregar una linea. Cual ampliar es decision de negocio, no
tecnica.

## La trampa que costo encontrar: la busqueda distingue acentos

`FILTER(CONTAINS(LCASE(...)))` en SPARQL **no normaliza tildes**. Buscar
`"norma de emision para centrales termoelectricas"` devuelve **cero**, porque el
titulo real dice `EMISIÓN` y `TERMOELÉCTRICAS`. Y devuelve cero **sin error**,
que es lo peor: se lee como "esa norma no esta en la BCN".

Por eso los terminos de abajo son subcadenas **sin ninguna letra acentuada**.
Cada uno lleva al lado la norma que debe encontrar, para que se note si algun
dia deja de encontrarla.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.catalog import NormSyncRun
from ..services import bcn

logger = logging.getLogger(__name__)

#: Que buscar, y que norma tiene que aparecer.
#:
#: El segundo valor **no es documentacion**: es lo que se comprueba despues de
#: cada busqueda. Si la BCN cambia un titulo o el termino deja de calzar, la
#: tarea lo dice en vez de sincronizar de menos en silencio.
#:
#: **Sin acentos, a proposito.** Ver el docstring del modulo.
TERMINOS: list[tuple[str, str]] = [
    ("bases generales del medio ambiente", "19300"),
    ("responsabilidad extendida del productor", "20920"),
    ("manejo de residuos peligrosos", "148"),
    ("residuos liquidos a aguas marinas y continentales", "90"),
    ("ruidos generados por fuentes que indica", "38"),
    ("centrales termoel", "13"),
    ("aprueba reglamento del sistema de evaluaci", "40"),
    ("reglamento del registro de emisiones y transferencias de contaminantes", "1"),
    # D.S. 609/1998 MOP, la norma de RILes a alcantarillado que fiscaliza la
    # SISS: una de las normas del piloto (decision 1 del plan de cierre,
    # 21-sep). Trae tambien los dos decretos que la modifican (3592 y 601),
    # porque su titulo contiene el de ella; el texto vigente del 609 ya los
    # incorpora.
    #
    # **Empieza por "establece norma" a proposito.** Sin eso el termino calza
    # tambien con las resoluciones que iniciaron y aprobaron el anteproyecto
    # (1958 y 281 exenta), que no se cumplen: se corrio asi una vez el 21-sep y
    # entraron las dos.
    (
        "establece norma de emision para la regulacion de contaminantes "
        "asociados a las descargas de residuos industriales liquidos a sistemas",
        "609",
    ),
]

#: Cuantas normas se piden por termino.
#:
#: Bajo a proposito. Cada norma extra descarga su articulado completo desde Ley
#: Chile, y traer de mas no es gratis: son normas que despues nadie clasifico y
#: que ensucian la busqueda del especialista.
POR_TERMINO = 5


@dataclass
class Informe:
    """Lo que paso, para que la salida del cron sirva de algo."""

    terminos: int = 0
    encontradas: int = 0
    nuevas: int = 0
    actualizadas: int = 0
    #: Normas de ejemplo del seed que pasaron a ser las reales **conservando su
    #: clasificacion por sector**. Es el numero que dice que el CORE sigue vivo.
    adoptadas: int = 0
    versiones_nuevas: int = 0
    articulos_nuevos: int = 0
    con_texto: int = 0
    #: Normas cuya version vigente cambio. **Son las que hay que mirar**: puede
    #: haber empresas con su matriz evaluada contra el texto anterior.
    con_version_nueva: list[str] = field(default_factory=list)
    #: Terminos que **no** trajeron la norma que debian. Es lo primero que hay
    #: que mirar: significa que el catalogo quedo incompleto sin fallar.
    sin_su_norma: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        lineas = [
            f"{self.terminos} terminos, {self.encontradas} normas encontradas",
            f"nuevas {self.nuevas} · actualizadas {self.actualizadas} · "
            f"adoptadas {self.adoptadas}",
            f"versiones {self.versiones_nuevas} · articulos "
            f"{self.articulos_nuevos} · con texto {self.con_texto}",
        ]
        if self.con_version_nueva:
            lineas.append(
                f"CON VERSION NUEVA ({len(self.con_version_nueva)}): "
                f"{', '.join(self.con_version_nueva)} — puede haber empresas "
                f"evaluadas contra el texto anterior"
            )
        if self.sin_su_norma:
            lineas.append(f"NO ENCONTRARON SU NORMA: {', '.join(self.sin_su_norma)}")
        if self.errores:
            lineas.append(f"errores: {'; '.join(self.errores)}")
        return chr(10).join(lineas)


def sincronizar(db: Session, *, en_seco: bool = False) -> Informe:
    """Corre la sincronizacion de todos los terminos. **No hace `commit`.**

    Quien llama decide, y por eso `--en-seco` puede correr el trabajo completo
    —incluidas las descargas— y no dejar nada escrito. Sirve para ver que traeria
    antes de dejarlo entrar al catalogo.

    Un termino que falla **no detiene a los demas**. La BCN se cae, cambia un
    titulo o responde lento; que eso impida traer las otras siete normas seria
    peor que traer siete.
    """
    informe = Informe(terminos=len(TERMINOS))
    inicio = datetime.now(timezone.utc)

    for termino, numero_esperado in TERMINOS:
        try:
            normas = bcn.buscar(termino, limite=POR_TERMINO)
        except Exception as exc:  # la BCN es un servicio ajeno
            logger.error("Fallo la busqueda de %r: %s", termino, exc)
            informe.errores.append(f"{termino}: {exc}")
            continue

        if not any((n.numero or "") == numero_esperado for n in normas):
            # No es un error de red: es que el termino dejo de encontrar lo que
            # tenia que encontrar. Sin este aviso, el catalogo queda incompleto
            # y todo parece haber funcionado.
            logger.warning(
                "El termino %r ya no encuentra la norma %s", termino, numero_esperado
            )
            informe.sin_su_norma.append(f"{termino} (esperaba {numero_esperado})")

        informe.encontradas += len(normas)

        try:
            # **Un savepoint por termino.** Antes esto era `db.rollback()`, que
            # deshace la transaccion entera: un fallo al guardar el quinto
            # termino borraba lo escrito por los cuatro anteriores —que todavia
            # no tenian commit— mientras el informe los seguia contando como
            # nuevos. El savepoint descarta solo lo de este termino.
            with db.begin_nested():
                r = bcn.sincronizar(db, normas, con_texto=True)
        except Exception as exc:
            logger.error("Fallo al guardar %r: %s", termino, exc)
            informe.errores.append(f"{termino} (al guardar): {exc}")
            continue

        informe.nuevas += r.nuevas
        informe.actualizadas += r.actualizadas
        informe.adoptadas += r.adoptadas
        informe.versiones_nuevas += r.versiones_nuevas
        informe.articulos_nuevos += r.articulos_nuevos
        informe.con_texto += r.con_texto
        informe.con_version_nueva.extend(r.con_version_nueva)
        logger.info("%r: %s", termino, r)

    if en_seco:
        db.rollback()
        logger.info("En seco: no se escribio nada.")
    else:
        anotar_corrida(db, informe, inicio)

    return informe


def estado_de(informe: Informe) -> str:
    """`success`, `partial` o `failed`, con los valores del CHECK de la tabla.

    **`partial` incluye a los terminos que no encontraron su norma**, aunque no
    haya habido excepcion: el catalogo quedo incompleto, y eso es lo que la
    bitacora tiene que dejar ver.
    """
    if informe.terminos and len(informe.errores) >= informe.terminos:
        return "failed"
    if informe.errores or informe.sin_su_norma:
        return "partial"
    return "success"


def anotar_corrida(db: Session, informe: Informe, inicio: datetime) -> NormSyncRun:
    """Deja la corrida en `norm_sync_runs`. **No hace `commit`**, igual que el resto.

    La tabla existia desde el esquema inicial y **nadie la escribia**: no habia
    forma de saber cuando se sincronizo el catalogo por ultima vez, ni si la
    ultima corrida trajo todo o se quedo a medias. Que el catalogo diga de donde
    salio y cuando es lo que se contesta en una auditoria de la matriz legal.
    """
    fuente_id = db.execute(
        text("SELECT id FROM legal_sources WHERE code = :c"), {"c": bcn.CODIGO_FUENTE}
    ).scalar_one()
    corrida = NormSyncRun(
        source_id=fuente_id,
        started_at=inicio,
        finished_at=datetime.now(timezone.utc),
        status=estado_de(informe),
        request_parameters={
            "terminos": [t for t, _ in TERMINOS],
            "por_termino": POR_TERMINO,
        },
        response_metadata={
            "encontradas": informe.encontradas,
            "adoptadas": informe.adoptadas,
            "articulos_nuevos": informe.articulos_nuevos,
            "con_texto": informe.con_texto,
            "con_version_nueva": informe.con_version_nueva,
            "sin_su_norma": informe.sin_su_norma,
        },
        norms_created=informe.nuevas,
        norms_updated=informe.actualizadas + informe.adoptadas,
        versions_created=informe.versiones_nuevas,
        error_detail="; ".join(informe.errores) or None,
    )
    db.add(corrida)
    db.flush()
    return corrida
