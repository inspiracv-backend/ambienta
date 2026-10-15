"""
El revisor: segunda capa, después de la verificación en código.

La verificación en código (etiquetas que existen, afirmaciones con cita) es determinista y
barata. El revisor con modelo mira lo que el código no puede: si lo que se afirma sale de
verdad del fragmento citado.
"""

from __future__ import annotations

from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field


class Evaluacion(BaseModel):
    fundamentada: bool = Field(description="¿Cada afirmación normativa sale de un fragmento citado?")
    cita_correctamente: bool = Field(description="¿Cada etiqueta [F#] apunta al fragmento del que sale lo afirmado?")
    deberia_abstenerse: bool = Field(description="¿La evidencia no alcanza para responder la pregunta?")
    observacion: str = Field(description="Qué corregir, en una frase")


class Revisor(Protocol):
    async def revisar(self, pregunta: str, respuesta: str, evidencia: str) -> Evaluacion: ...


class RevisorNulo:
    """Aprueba siempre. Quedan solo los chequeos en código."""

    async def revisar(self, pregunta: str, respuesta: str, evidencia: str) -> Evaluacion:
        return Evaluacion(fundamentada=True, cita_correctamente=True, deberia_abstenerse=False, observacion="")


INSTRUCCION = """\
Revisás respuestas de un asistente de cumplimiento ambiental. Sé estricto: una afirmación
normativa sin respaldo puede hacer que una empresa incumpla.

Pregunta del usuario:
{pregunta}

Evidencia disponible (fragmentos con su etiqueta):
{evidencia}

Respuesta a revisar:
{respuesta}

Evaluá:
1. Si cada afirmación normativa sale del fragmento que cita, CON EL SENTIDO que tiene ahí. Un
   número o término que el fragmento usa para otra cosa (por ejemplo, un umbral que define qué
   proyectos entran a evaluación ambiental, usado como si fuera un límite de velocidad) es una
   cita incorrecta.
2. Si las etiquetas son las correctas.
3. Si la evidencia en realidad no alcanza para responder, o si la pregunta no es de materia
   ambiental: en los dos casos, debería abstenerse."""


class RevisorModelo:
    def __init__(self, modelo: BaseChatModel):
        self._modelo = modelo.with_structured_output(Evaluacion)

    async def revisar(self, pregunta: str, respuesta: str, evidencia: str) -> Evaluacion:
        return await self._modelo.ainvoke(
            INSTRUCCION.format(pregunta=pregunta, evidencia=evidencia or "(ninguna)", respuesta=respuesta)
        )
