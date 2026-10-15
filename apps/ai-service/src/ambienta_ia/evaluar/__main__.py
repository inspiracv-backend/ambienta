"""
    python -m ambienta_ia.evaluar --dataset evaluacion/semilla_demo.jsonl \
        [--modo recuperacion|respuestas] [--k 5] [--barrido] \
        [--umbrales evaluacion/umbrales.json] [--salida reporte.json]

Contra la base de conocimiento de `DATABASE_URL_CONSULTA` y el backend de `BACKEND_URL`,
como la empresa `--tenant` en modo desarrollo del backend o con `--token`.

Sale con código 1 si algún umbral no se cumple, y nombra los casos.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
from uuid import UUID

from ..backend import ClienteBackend
from ..config import config
from ..conocimiento import abrir_base
from ..proveedores import crear_embeddings
from ..recuperacion import Recuperador
from .correr import comparar_umbrales, evaluar_recuperacion, evaluar_respuestas
from .metricas import cargar_dataset


def _resumen(reporte: dict) -> str:
    lineas = [f"## Evaluación de {reporte['tipo']} · {reporte['casos']} casos", ""]
    lineas += [f"- **{k}**: {v}" for k, v in reporte.items() if k not in ("detalle", "tipo", "casos", "barrido")]
    if "barrido" in reporte:
        lineas += ["", "| k | recall | precisión | mrr |", "|---|---|---|---|"]
        for b in reporte["barrido"]:
            k = b["k"]
            lineas.append(f"| {k} | {b['recall@' + str(k)]} | {b['precision@' + str(k)]} | {b['mrr']} |")
    fallas = [f for f in reporte["detalle"] if not f["abstencion_ok"] or (f.get("recall") not in (None, 1.0))]
    if fallas:
        lineas += ["", "### Casos con fallas", ""]
        lineas += [f"- `{f['id']}`: {f.get('recuperados') or f.get('citas')}" for f in fallas]
    return "\n".join(lineas)


async def _correr(args: argparse.Namespace) -> int:
    c = config()
    casos = cargar_dataset(args.dataset)
    base = await abrir_base(c.database_url_consulta, maximo=2)
    embeddings = crear_embeddings(c.proveedor_embeddings, c.modelo_embeddings, c.dimension_embeddings)
    reordenador = None
    if c.proveedor_llm != "falso" and c.reordenar_con_modelo:
        from ..proveedores import crear_modelo as _crear
        from ..recuperacion import ReordenadorModelo

        reordenador = ReordenadorModelo(_crear(c.proveedor_llm, c.modelo_llm))
    recuperador = Recuperador(base, embeddings, umbral=c.umbral_evidencia, k=args.k, reordenador=reordenador)
    cliente = (ClienteBackend.con_token(c.backend_url, args.token) if args.token
               else ClienteBackend.modo_desarrollo(c.backend_url, args.tenant))
    try:
        if args.modo == "recuperacion":
            reporte = await evaluar_recuperacion(casos, recuperador, UUID(args.tenant), k=args.k, cliente=cliente)
            if args.barrido:
                reporte["barrido"] = []
                for k in (1, 3, 5, 10, 20):
                    r = await evaluar_recuperacion(casos, recuperador, UUID(args.tenant), k=k, cliente=cliente)
                    reporte["barrido"].append({x: r[x] for x in (f"recall@{k}", f"precision@{k}", "mrr")} | {"k": k})
        else:
            from ..agente import Agente, RevisorModelo, RevisorNulo
            from ..identidad import Sesion
            from ..proveedores import crear_modelo

            if c.proveedor_llm == "falso":
                from ..agente.falso import ModeloDemo

                modelo, revisor = ModeloDemo(), RevisorNulo()
            else:
                modelo = crear_modelo(c.proveedor_llm, c.modelo_llm)
                revisor = RevisorModelo(modelo) if c.revisor_con_modelo else RevisorNulo()
            agente = Agente(modelo, revisor, recuperador, embeddings, max_herramientas=c.max_herramientas,
                            max_revisiones=c.max_revisiones, max_tokens=c.max_tokens_consulta)
            if args.token:
                # La misma sesión que armaría la API: permisos reales de /me. Sin esto el agente
                # quedaba sin herramientas y se abstenía en todo (encontrado el 21/09/2026).
                me = await cliente.yo()
                sesion = Sesion(tenant_id=me.empresa.id if me.empresa else UUID(args.tenant),
                                usuario_id=me.usuario.id if me.usuario else None,
                                permisos=frozenset(me.permisos), modo_desarrollo=False, token=args.token)
            else:
                sesion = Sesion(tenant_id=UUID(args.tenant), usuario_id=None, permisos=frozenset(),
                                modo_desarrollo=True)
            reporte = await evaluar_respuestas(casos, agente, sesion, cliente)
    finally:
        await cliente.cerrar()
        await base.cerrar()

    if args.salida:
        pathlib.Path(args.salida).write_text(json.dumps(reporte, ensure_ascii=False, indent=2, default=str))
    print(_resumen(reporte))

    if args.umbrales:
        umbrales = json.loads(pathlib.Path(args.umbrales).read_text())[args.modo]
        fallas = comparar_umbrales(reporte, umbrales)
        if fallas:
            print("\n### Umbrales no cumplidos\n")
            print("\n".join(f"- {f}" for f in fallas))
            return 1
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Evalúa recuperación y respuestas contra un dataset.")
    p.add_argument("--dataset", required=True)
    p.add_argument("--modo", choices=["recuperacion", "respuestas"], default="recuperacion")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--barrido", action="store_true")
    p.add_argument("--umbrales")
    p.add_argument("--salida")
    p.add_argument("--tenant", default="a0000000-0000-0000-0000-000000000001")
    p.add_argument("--token")
    sys.exit(asyncio.run(_correr(p.parse_args())))


if __name__ == "__main__":
    main()
