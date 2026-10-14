from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from ..config import config
from ..observabilidad import configurar_logs, evento
from .estado import guardar_estado


async def _correr(nombre: str, modulo: str, intervalo: int, env: dict[str, str]) -> None:
    url = config().database_url_sincronizador
    if not url:
        raise RuntimeError("DATABASE_URL_SINCRONIZADOR es obligatoria para el worker")
    while True:
        await guardar_estado(url, nombre, "ejecutando")
        inicio = time.monotonic()
        proceso = await asyncio.create_subprocess_exec(
            sys.executable, "-m", modulo, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, env=env,
        )
        salida, _ = await proceso.communicate()
        salida_texto = salida.decode("utf-8", errors="replace")
        correcto = proceso.returncode == 0
        elementos = 0
        if correcto:
            # El comando de ingesta termina con un objeto JSON de resumen.
            for linea in reversed(salida_texto.splitlines()):
                try:
                    resumen = json.loads(linea)
                    if "documentos" in resumen:
                        elementos = int(resumen["documentos"])
                    elif "cambios_normativos" in resumen:
                        elementos = sum(len(resumen.get(k, [])) for k in ("cambios_normativos", "novedades_sma", "avisos"))
                    break
                except (ValueError, AttributeError):
                    continue
        estado = "ok" if correcto else "error"
        await guardar_estado(url, nombre, estado, elementos=elementos,
                             detalle=None if correcto else f"El proceso terminó con código {proceso.returncode}. Revisa el log del worker.")
        evento("agente_job_finalizado", agente=nombre, estado=estado, elementos=elementos,
               duracion_ms=int((time.monotonic() - inicio) * 1000))
        if not correcto:
            evento("agente_job_error", agente=nombre, codigo_salida=proceso.returncode)
        await asyncio.sleep(intervalo)


async def ejecutar() -> None:
    env = os.environ.copy()
    cuentas = env.get("AI_CUENTAS_ARCHIVO")
    if cuentas:
        env.setdefault("MONITOREO_CUENTAS_ARCHIVO", cuentas)
        env.setdefault("INGESTA_CUENTAS_ARCHIVO", cuentas)
    monitoreo_s = max(60, int(env.get("AI_MONITOREO_INTERVALO_SEGUNDOS", "86400")))
    ingesta_s = max(60, int(env.get("AI_INGESTA_INTERVALO_SEGUNDOS", "1800")))
    await asyncio.gather(
        _correr("monitoreo_normativo", "ambienta_ia.monitoreo", monitoreo_s, env),
        _correr("ingesta_documentos", "ambienta_ia.ingesta", ingesta_s, env),
    )


def main() -> None:
    configurar_logs()
    asyncio.run(ejecutar())


if __name__ == "__main__":
    main()
