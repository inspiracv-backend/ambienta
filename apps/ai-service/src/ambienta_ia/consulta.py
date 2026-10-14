"""
Una consulta de punta a punta (SPEC-07).

    sesión → conversación → hilo → guardar la pregunta → agente → guardar la respuesta

La conversación vive en el backend (`/support/chatbot`); el AI Service no guarda historial.
La pregunta se guarda **antes** de llamar al modelo: si el modelo falla, la pregunta no se
pierde. La respuesta se guarda **completa, al terminar**, con sus citas.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from .agente import Agente, RespuestaAgente
from .backend import BackendCaido, ClienteBackend, ErrorBackend, NoEncontrado
from .backend.modelos import MensajeNuevo
from .identidad import Sesion
from .observabilidad import Traza, aviso


class ErrorConsulta(Exception):
    def __init__(self, estado: int, codigo: str, detalle: str):
        super().__init__(detalle)
        self.estado = estado
        self.codigo = codigo
        self.detalle = detalle


@dataclass
class Preparada:
    conversation_id: UUID | None
    hilo: list[tuple[str, str]]
    guardar: bool


async def preparar(
    pregunta: str,
    conversation_id: UUID | None,
    *,
    sesion: Sesion,
    cliente: ClienteBackend,
    turnos: int,
) -> Preparada:
    """Todo lo que puede fallar antes de empezar a responder, para devolverlo como HTTP."""
    if sesion.modo_desarrollo or sesion.usuario_id is None:
        # Sin usuario no hay autor: la consulta se responde pero no se guarda (handoff §2).
        return Preparada(conversation_id=None, hilo=[], guardar=False)
    try:
        if conversation_id is None:
            conv = await cliente.abrir_conversacion(sesion.usuario_id, pregunta[:80])
            conversation_id = conv.id
            hilo: list[tuple[str, str]] = []
        else:
            await cliente.conversacion(conversation_id)  # 404 si no existe o es de otra empresa
            mensajes = await cliente.mensajes(conversation_id)
            hilo = [(m.role, m.content) for m in mensajes if m.role in ("user", "assistant")][-turnos:]
        await cliente.guardar_mensaje(conversation_id, MensajeNuevo(role="user", content=pregunta))
    except NoEncontrado as e:
        raise ErrorConsulta(404, "conversacion_no_encontrada", "La conversación no existe.") from e
    except BackendCaido as e:
        raise ErrorConsulta(503, "backend_no_disponible", "El backend no responde.") from e
    except ErrorBackend as e:
        raise ErrorConsulta(e.estado or 502, "backend_rechazo", e.detalle) from e
    return Preparada(conversation_id=conversation_id, hilo=hilo, guardar=True)


def _citations(r: RespuestaAgente) -> list[dict[str, Any]]:
    if r.se_abstuvo:
        # Hasta que el backend tenga un campo propio: la abstención queda marcada y se distingue
        # de "respondió sin citar".
        return [{"tipo": "abstencion", "motivo": r.motivo_abstencion}]
    return [c.como_dict() for c in r.citas]


def respuesta_consulta(r: RespuestaAgente, *, conversation_id: UUID | None, mensaje_id: int | None,
                       guardado: bool, traza: Traza) -> dict[str, Any]:
    return {
        "conversation_id": str(conversation_id) if conversation_id else None,
        "mensaje_id": mensaje_id,
        "respuesta": r.texto,
        "se_abstuvo": r.se_abstuvo,
        "motivo_abstencion": r.motivo_abstencion,
        "citas": [c.como_dict() for c in r.citas],
        "cited_norm_ids": [str(x) for x in r.cited_norm_ids],
        "guardado": guardado,
        "diagnostico": {
            "request_id": traza.request_id,
            "modo_busqueda": r.modo_busqueda or "ninguna",
            "herramientas": r.herramientas_usadas,
            "fragmentos_evaluados": r.fragmentos_evaluados,
            "mejor_similitud": r.mejor_similitud,
            "modelo": r.modelo,
            "tokens": {"input": r.tokens_entrada, "output": r.tokens_salida},
            "latencia_ms": traza.latencia_ms,
        },
    }


async def ejecutar(
    pregunta: str,
    preparada: Preparada,
    *,
    fecha: date | None,
    sesion: Sesion,
    cliente: ClienteBackend,
    agente: Agente,
    traza: Traza,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Eventos (tipo, datos): herramienta, texto, final, error."""
    traza.conversation_id = str(preparada.conversation_id) if preparada.conversation_id else None
    final: RespuestaAgente | None = None
    try:
        async for ev in agente.responder(pregunta, hilo=preparada.hilo, sesion=sesion, cliente=cliente,
                                         traza=traza, fecha=fecha):
            if ev.tipo == "final":
                final = ev.datos["respuesta"]
            else:
                yield ev.tipo, ev.datos
    except Exception as e:
        traza.error = f"{type(e).__name__}: {e}"
        aviso("agente_fallo", request_id=traza.request_id, error=traza.error)
        yield "error", {"detail": "El modelo no está disponible en este momento.", "codigo": "modelo_no_disponible"}
        return

    assert final is not None
    traza.se_abstuvo = final.se_abstuvo
    traza.motivo_abstencion = final.motivo_abstencion
    traza.citas = [c.etiqueta for c in final.citas]
    traza.tokens_entrada, traza.tokens_salida = final.tokens_entrada, final.tokens_salida

    mensaje_id = None
    error_guardado = None
    if preparada.guardar and preparada.conversation_id:
        try:
            m = await cliente.guardar_mensaje(
                preparada.conversation_id,
                MensajeNuevo(
                    role="assistant",
                    content=final.texto,
                    citations=_citations(final),
                    cited_norm_ids=final.cited_norm_ids,
                    model_name=final.modelo,
                    token_usage={"input": final.tokens_entrada, "output": final.tokens_salida},
                ),
            )
            mensaje_id = m.id
        except ErrorBackend as e:
            error_guardado = e
            aviso("guardar_respuesta_fallo", request_id=traza.request_id, error=str(e))

    guardado = mensaje_id is not None
    traza.guardado = guardado
    traza.cerrar()
    yield "final", respuesta_consulta(final, conversation_id=preparada.conversation_id,
                                      mensaje_id=mensaje_id, guardado=guardado, traza=traza)
    if error_guardado is not None:
        yield "error", {"detail": "La respuesta no se pudo guardar en la conversación.",
                        "codigo": "no_guardado"}
