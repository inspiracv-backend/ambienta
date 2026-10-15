"""
    python -m ambienta_ia.snifa

Baja los datos abiertos de la SMA y los carga en la base del AI Service (DATABASE_URL_SINCRONIZADOR).
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict

from ..config import config
from ..conocimiento import abrir_base
from ..observabilidad import configurar_logs, evento
from . import sincronizar_snifa


async def _correr() -> int:
    c = config()
    if not c.database_url_sincronizador:
        print("Falta DATABASE_URL_SINCRONIZADOR.")
        return 2
    base = await abrir_base(c.database_url_sincronizador, maximo=2)
    try:
        resultados = await sincronizar_snifa(base)
    finally:
        await base.cerrar()
    for r in resultados:
        evento("snifa_carga", **{k: v for k, v in asdict(r).items() if k not in ("nuevos", "cambios_de_estado")},
               nuevos=len(r.nuevos), cambios_de_estado=len(r.cambios_de_estado))
    print(json.dumps([asdict(r) for r in resultados], ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> None:
    configurar_logs()
    sys.exit(asyncio.run(_correr()))


if __name__ == "__main__":
    main()
