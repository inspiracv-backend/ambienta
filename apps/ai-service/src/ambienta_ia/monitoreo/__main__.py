"""
    python -m ambienta_ia.monitoreo [--sin-snifa]

Una corrida del agente de monitoreo normativo, pensada para un cron diario:

1. Sincroniza el catálogo (SERVICIO_TOKEN) y recoge las normas que cambiaron de versión.
2. Sincroniza SNIFA y recoge los procesos sancionatorios nuevos o con cambio de estado.
3. Avisa a cada empresa afectada y abre un ticket para el equipo de plataforma.

Cuentas (nunca en el repositorio):
    MONITOREO_CUENTAS_ARCHIVO   JSON: [{"tenant_id": "...", "token": "..."}] una por empresa
    MONITOREO_TOKEN_PLATAFORMA  token de la cuenta de plataforma, para el ticket (opcional)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys
from dataclasses import asdict
from uuid import UUID

from ..backend import ClienteBackend
from ..config import config
from ..conocimiento import BaseConocimiento, abrir_base
from ..observabilidad import configurar_logs
from ..proveedores import crear_embeddings
from ..sincronizar import sincronizar
from ..snifa import sincronizar_snifa
from . import CuentaDeEmpresa, CuentaDePlataforma, NovedadSMA, monitorear


async def novedades_de(base: BaseConocimiento, nuevos: list[int], cambios: list[tuple[int, str, str]]) -> list[NovedadSMA]:
    ids = list(nuevos) + [c[0] for c in cambios]
    if not ids:
        return []
    anterior = {c[0]: c[1] for c in cambios}
    async with base.de_empresa(None) as conn:
        cur = await conn.execute("SELECT id, unidad_id, expediente, tipo, estado, multa_uta, trim(enlace) "
                                 "FROM snifa_sancionatorio WHERE id = ANY(%s)", (ids,))
        return [NovedadSMA(u, e, t, s, anterior.get(i), float(m) if m is not None else None, enlace)
                for i, u, e, t, s, m, enlace in await cur.fetchall() if u is not None]


async def _correr(sin_snifa: bool) -> int:
    c = config()
    archivo = os.getenv("MONITOREO_CUENTAS_ARCHIVO")
    if not archivo or not c.servicio_token or not c.database_url_sincronizador:
        print("Faltan MONITOREO_CUENTAS_ARCHIVO, SERVICIO_TOKEN o DATABASE_URL_SINCRONIZADOR.")
        return 2
    cuentas = [CuentaDeEmpresa(UUID(x["tenant_id"]), x["token"])
               for x in json.loads(pathlib.Path(archivo).read_text())]
    plataforma = CuentaDePlataforma(os.environ["MONITOREO_TOKEN_PLATAFORMA"]) \
        if os.getenv("MONITOREO_TOKEN_PLATAFORMA") else None

    base = await abrir_base(c.database_url_sincronizador, maximo=2)
    try:
        embeddings = crear_embeddings(c.proveedor_embeddings, c.modelo_embeddings, c.dimension_embeddings)
        async with ClienteBackend.con_token(c.backend_url, c.servicio_token) as servicio:
            catalogo = await sincronizar(servicio, base, embeddings)
        novedades: list[NovedadSMA] = []
        if not sin_snifa:
            for r in await sincronizar_snifa(base):
                if r.conjunto == "sancionatorios":
                    novedades = await novedades_de(base, r.nuevos, r.cambios_de_estado)
        informe = await monitorear(backend_url=c.backend_url, cuentas=cuentas, base=base,
                                   cambios=catalogo.cambios, novedades=novedades, plataforma=plataforma)
    finally:
        await base.cerrar()
    print(json.dumps({"cambios_normativos": [asdict(x) for x in catalogo.cambios],
                      "novedades_sma": [asdict(n) for n in novedades],
                      "avisos": [asdict(a) for a in informe.avisos], "ticket": informe.ticket,
                      "errores": informe.errores}, ensure_ascii=False, separators=(",", ":"), default=str))
    return 1 if informe.errores else 0


def main() -> None:
    p = argparse.ArgumentParser(description="Corre el agente de monitoreo normativo.")
    p.add_argument("--sin-snifa", action="store_true")
    configurar_logs()
    sys.exit(asyncio.run(_correr(p.parse_args().sin_snifa)))


if __name__ == "__main__":
    main()
