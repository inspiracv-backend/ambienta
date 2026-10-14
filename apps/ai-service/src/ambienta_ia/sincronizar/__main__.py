"""
    python -m ambienta_ia.sincronizar [--completa]

Usa `SERVICIO_TOKEN` (cuenta servicio_lectura) o, contra un backend en modo desarrollo,
`SERVICIO_TENANT_ID`. Escribe con `DATABASE_URL_SINCRONIZADOR`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from ..backend import ClienteBackend
from ..config import config
from ..conocimiento import abrir_base
from ..observabilidad import configurar_logs
from ..proveedores import crear_embeddings
from .sincronizador import sincronizar


async def _correr(completa: bool) -> int:
    c = config()
    if c.servicio_token:
        cliente = ClienteBackend.con_token(c.backend_url, c.servicio_token)
    elif c.servicio_tenant_id:
        cliente = ClienteBackend.modo_desarrollo(c.backend_url, c.servicio_tenant_id)
    else:
        print("Falta SERVICIO_TOKEN (o SERVICIO_TENANT_ID contra un backend en desarrollo).")
        return 2
    if not c.database_url_sincronizador:
        print("Falta DATABASE_URL_SINCRONIZADOR.")
        return 2

    base = await abrir_base(c.database_url_sincronizador, maximo=2)
    embeddings = crear_embeddings(c.proveedor_embeddings, c.modelo_embeddings, c.dimension_embeddings)
    try:
        r = await sincronizar(cliente, base, embeddings, completa=completa)
    finally:
        await cliente.cerrar()
        await base.cerrar()
    print(json.dumps(asdict(r), ensure_ascii=False, indent=2, default=str))
    return 1 if r.errores else 0


def main() -> None:
    p = argparse.ArgumentParser(description="Sincroniza el catálogo normativo del backend.")
    p.add_argument("--completa", action="store_true", help="Revisa todo, ignorando updated_since")
    args = p.parse_args()
    configurar_logs()
    sys.exit(asyncio.run(_correr(args.completa)))


if __name__ == "__main__":
    main()
