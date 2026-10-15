from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from ..agente import Agente
from ..backend import ClienteBackend
from ..citas import normalizar_norma, numero_normal
from ..identidad import Sesion
from ..observabilidad import Traza
from ..recuperacion import Recuperador
from .metricas import Caso, mrr, precision_en_k, recall_en_k


def _promedio(filas: list[dict], campo: str) -> float:
    valores = [f[campo] for f in filas if f.get(campo) is not None]
    return round(sum(valores) / len(valores), 4) if valores else 0.0


async def evaluar_recuperacion(
    casos: list[Caso],
    recuperador: Recuperador,
    tenant_id: UUID,
    *,
    k: int = 5,
    cliente: ClienteBackend | None = None,
) -> dict[str, Any]:
    """Sin modelo de lenguaje: barato, corre en cada PR (SPEC-08)."""
    filas = []
    for caso in casos:
        r = await recuperador.recuperar(caso.pregunta, tenant_id, fecha=caso.fecha, cliente=cliente, k=k)
        if caso.clave_norma:
            recuperados = [f"{normalizar_norma(x.cita.norma)}:{numero_normal(x.cita.articulo)}" for x in r.resultados]
            esperados = {f"{caso.clave_norma}:{a}" for a in caso.esperados}
        else:
            recuperados = [numero_normal(x.cita.articulo) or "" for x in r.resultados]
            esperados = caso.esperados
        filas.append({
            "id": caso.id,
            "debe_abstenerse": caso.debe_abstenerse,
            "hay_evidencia": r.hay_evidencia,
            "abstencion_ok": caso.debe_abstenerse == (not r.hay_evidencia),
            "recall": None if caso.debe_abstenerse else recall_en_k(esperados, recuperados, k),
            "precision": None if caso.debe_abstenerse else precision_en_k(esperados, recuperados, k),
            "mrr": None if caso.debe_abstenerse else mrr(esperados, recuperados),
            "mejor_similitud": r.mejor_similitud,
            "modo": r.modo,
            "recuperados": recuperados,
        })
    con_respuesta = [f for f in filas if not f["debe_abstenerse"]]
    deben = [f for f in filas if f["debe_abstenerse"]]
    return {
        "tipo": "recuperacion",
        "k": k,
        "casos": len(casos),
        f"recall@{k}": _promedio(con_respuesta, "recall"),
        f"precision@{k}": _promedio(con_respuesta, "precision"),
        "mrr": _promedio(con_respuesta, "mrr"),
        "abstencion_correcta": round(sum(f["abstencion_ok"] for f in filas) / len(filas), 4) if filas else 0.0,
        "falsos_positivos": sum(1 for f in deben if f["hay_evidencia"]),
        "detalle": filas,
    }


async def evaluar_respuestas(
    casos: list[Caso],
    agente: Agente,
    sesion: Sesion,
    cliente: ClienteBackend,
) -> dict[str, Any]:
    """Con el modelo: cuesta tokens, corre en la rama principal (SPEC-08)."""
    filas = []
    for caso in casos:
        traza = Traza(pregunta=caso.pregunta)
        inicio = time.monotonic()
        final = None
        async for ev in agente.responder(caso.pregunta, hilo=[], sesion=sesion, cliente=cliente,
                                         traza=traza, fecha=caso.fecha):
            if ev.tipo == "final":
                final = ev.datos["respuesta"]
        assert final is not None
        citas = [(normalizar_norma(c.norma), numero_normal(c.articulo)) for c in final.citas]
        validas = [
            c for c in citas
            if c[1] in caso.esperados and (caso.clave_norma is None or c[0] == caso.clave_norma)
        ]
        filas.append({
            "id": caso.id,
            "debe_abstenerse": caso.debe_abstenerse,
            "se_abstuvo": final.se_abstuvo,
            "motivo": final.motivo_abstencion,
            "abstencion_ok": caso.debe_abstenerse == final.se_abstuvo,
            "citas": [f"{n}:{a}" for n, a in citas],
            "citas_validas": (len(validas) / len(citas)) if citas else None,
            "tokens": final.tokens_entrada + final.tokens_salida,
            "latencia_ms": int((time.monotonic() - inicio) * 1000),
            "respuesta": final.texto,
        })
    deben = [f for f in filas if f["debe_abstenerse"]]
    latencias = sorted(f["latencia_ms"] for f in filas)
    return {
        "tipo": "respuestas",
        "casos": len(casos),
        "abstencion_correcta": round(sum(f["abstencion_ok"] for f in filas) / len(filas), 4) if filas else 0.0,
        "falsos_positivos": sum(1 for f in deben if not f["se_abstuvo"]),
        "citas_validas": _promedio([f for f in filas if not f["debe_abstenerse"]], "citas_validas"),
        # Al menos una cita esperada. `citas_validas` es precisión y castiga citar además otros
        # artículos pertinentes; esta mide si la respuesta se apoya en lo que tenía que apoyarse.
        "cita_esperada": round(
            sum(1 for f in filas if not f["debe_abstenerse"] and f["citas_validas"])
            / max(1, sum(1 for f in filas if not f["debe_abstenerse"])), 4),
        "tokens_medios": _promedio(filas, "tokens"),
        "latencia_p95_ms": latencias[int(len(latencias) * 0.95) - 1] if latencias else 0,
        "detalle": filas,
    }


def comparar_umbrales(reporte: dict[str, Any], umbrales: dict[str, float]) -> list[str]:
    """
    Devuelve los incumplimientos, nombrando los casos. Vacío = pasa.

    Convención: `falsos_positivos` es un máximo; todo lo demás, un mínimo.
    """
    fallas = []
    for metrica, limite in umbrales.items():
        if metrica not in reporte:
            continue
        valor = reporte[metrica]
        if metrica == "falsos_positivos":
            if valor > limite:
                casos = [f["id"] for f in reporte["detalle"] if f["debe_abstenerse"]
                         and (f.get("hay_evidencia") or f.get("se_abstuvo") is False)]
                fallas.append(f"falsos_positivos = {valor} (máximo {limite}): {', '.join(casos)}")
        elif valor < limite:
            fallas.append(f"{metrica} = {valor} (mínimo {limite})")
    return fallas
