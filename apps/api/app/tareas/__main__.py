"""Punto de entrada de las tareas programadas. Se invoca desde cron en el VPS.

    python -m app.tareas rotar-auditoria [--mes AAAA-MM] [--en-seco]

## Por que un modulo y no un script suelto

Un script en `scripts/` tendria que reconstruir la configuracion y la conexion
por su cuenta, y esa copia se desincroniza: la API cambia de credenciales y la
tarea sigue con las viejas hasta que falla un martes a las tres de la manana.
Asi comparte `config` y `db` con el resto.

## Como se instala en el VPS

```
0 3 1 * *  cd /srv/ambienta && docker compose exec -T api python -m app.tareas rotar-auditoria >> /var/log/ambienta-rotacion.log 2>&1
```

**El dia 1 a las 3 de la manana**, que es cuando el mes anterior ya cerro y no
hay nadie usando el sistema. La salida va a un archivo: una tarea de cron que no
deja rastro es una tarea que nadie sabe si corrio.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from ..config import get_settings
from ..db import AdminSessionLocal
from .rotar_auditoria import mes_anterior, rotar

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("ambienta.tareas")


def _parsear_mes(texto: str) -> tuple[date, date]:
    """`AAAA-MM` a un rango `[desde, hasta)`."""
    inicio = datetime.strptime(texto, "%Y-%m").date()
    fin = (
        inicio.replace(year=inicio.year + 1, month=1)
        if inicio.month == 12
        else inicio.replace(month=inicio.month + 1)
    )
    return inicio, fin


def rotar_auditoria(args: argparse.Namespace) -> int:
    desde, hasta = (
        _parsear_mes(args.mes) if args.mes else mes_anterior(date.today())
    )
    destino = Path(args.destino)

    logger.info(
        "Rotando auditoria de %s a %s (exclusivo) hacia %s%s",
        desde,
        hasta,
        destino,
        " [EN SECO]" if args.en_seco else "",
    )

    db = AdminSessionLocal()
    try:
        r = rotar(db, desde=desde, hasta=hasta, destino=destino, borrar=not args.en_seco)

        for e in r.por_empresa:
            logger.info("  %s: %d filas -> %s", e.nombre, e.filas, e.archivo)

        if args.en_seco:
            # Se deshace todo: la corrida en seco no debe dejar ni un cambio.
            db.rollback()
            logger.info(
                "EN SECO: %d filas archivadas, 0 borradas. Nada se confirmo.",
                r.filas_archivadas,
            )
            return 0

        db.commit()
        logger.info(
            "Listo: %d filas archivadas y borradas, en %d empresas.",
            r.filas_archivadas,
            len(r.por_empresa),
        )
        return 0
    except Exception:
        # `rollback` explicito: sin el, un fallo a mitad deja la transaccion
        # abierta hasta que el proceso muera, y con ella los candados tomados.
        db.rollback()
        logger.exception("La rotacion fallo. No se borro nada.")
        return 1
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.tareas")
    sub = parser.add_subparsers(dest="tarea", required=True)

    p = sub.add_parser(
        "rotar-auditoria",
        help="Archiva el registro de actividades del mes anterior y lo purga.",
    )
    p.add_argument(
        "--mes",
        help="AAAA-MM. Por defecto, el mes cerrado anterior. **Nunca el mes en curso**",
    )
    p.add_argument(
        "--destino",
        default=get_settings().ruta_archivo_auditoria,
        help="Carpeta donde se escriben los JSON, uno por empresa.",
    )
    p.add_argument(
        "--en-seco",
        action="store_true",
        help="Escribe los archivos y NO borra nada. Para comprobar antes de confiar.",
    )
    p.set_defaults(func=rotar_auditoria)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
