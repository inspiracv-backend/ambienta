from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
from uuid import UUID

from ..config import config
from ..conocimiento import abrir_base
from ..observabilidad import configurar_logs, evento
from ..proveedores import crear_embeddings
from .pdf import CuentaIngesta, ingerir_documentos


async def ejecutar() -> tuple[int, int]:
    c = config()
    archivo = os.getenv("INGESTA_CUENTAS_ARCHIVO") or os.getenv("MONITOREO_CUENTAS_ARCHIVO")
    if not archivo or not c.database_url_sincronizador:
        raise RuntimeError("Faltan INGESTA_CUENTAS_ARCHIVO y DATABASE_URL_SINCRONIZADOR")
    cuentas = [CuentaIngesta(UUID(x["tenant_id"]), x["token"])
               for x in json.loads(pathlib.Path(archivo).read_text(encoding="utf-8"))]
    base = await abrir_base(c.database_url_sincronizador, maximo=3)
    try:
        embeddings = crear_embeddings(c.proveedor_embeddings, c.modelo_embeddings, c.dimension_embeddings)
        r = await ingerir_documentos(backend_url=c.backend_url, cuentas=cuentas, base=base, embeddings=embeddings)
    finally:
        await base.cerrar()
    evento("ingesta_documentos", documentos=r.documentos, fragmentos=r.fragmentos,
           omitidos=r.omitidos, errores=len(r.errores or []))
    if r.errores:
        for error in r.errores:
            evento("ingesta_documento_error", detalle=error)
    return r.documentos, r.fragmentos


def main() -> None:
    configurar_logs()
    try:
        docs, chunks = asyncio.run(ejecutar())
        print(json.dumps({"documentos": docs, "fragmentos": chunks}))
    except Exception as exc:
        evento("ingesta_documentos_fallo", error=f"{type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
