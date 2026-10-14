"""
Modelos sin red, para pruebas y demo.

- `ModeloGuionado`: devuelve respuestas predefinidas en orden. Para probar el grafo sin gastar
  tokens ni depender de lo que un modelo real decida ese día.
- `ModeloDemo`: una heurística que imita el comportamiento esperado (busca, y responde citando el mejor fragmento
  o dice SIN_INFORMACION). Sirve para levantar la demo completa sin
  claves. **No redacta**: pega oraciones de la evidencia.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

Guion = AIMessage | Callable[[list[BaseMessage]], AIMessage]


def pedir(herramienta: str, **args: Any) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": herramienta, "args": args, "id": uuid.uuid4().hex[:8]}])


class ModeloGuionado(BaseChatModel):
    guion: list[Any]
    llamadas: list[list[BaseMessage]] = []
    repetir_ultimo: bool = False

    @property
    def _llm_type(self) -> str:
        return "guionado"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ModeloGuionado:
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None,
                  run_manager: CallbackManagerForLLMRun | None = None, **kwargs: Any) -> ChatResult:
        self.llamadas.append(list(messages))
        if not self.guion:
            raise RuntimeError("El guion se terminó: el grafo llamó al modelo más veces de lo esperado.")
        paso = self.guion[0] if (self.repetir_ultimo and len(self.guion) == 1) else self.guion.pop(0)
        mensaje = paso(messages) if callable(paso) else paso.model_copy(deep=True)
        if mensaje.tool_calls:
            mensaje = AIMessage(content=mensaje.content,
                                tool_calls=[{**t, "id": uuid.uuid4().hex[:8]} for t in mensaje.tool_calls])
        mensaje.usage_metadata = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        return ChatResult(generations=[ChatGeneration(message=mensaje)])


class ModeloDemo(BaseChatModel):
    model_name: str = "demo-sin-modelo"

    @property
    def _llm_type(self) -> str:
        return "demo"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ModeloDemo:
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None,
                  run_manager: CallbackManagerForLLMRun | None = None, **kwargs: Any) -> ChatResult:
        pregunta = next(str(m.content) for m in reversed(messages) if isinstance(m, HumanMessage))
        herramientas = [m for m in messages if isinstance(m, ToolMessage)]
        if not herramientas:
            p = pregunta.lower()
            if any(x in p for x in ("vence", "venc", "obligaci", "pendiente")):
                msg = pedir("obligaciones")
            elif "rca" in p or "mi resolución" in p:
                msg = pedir("normativa_propia", pregunta=pregunta)
            else:
                msg = pedir("buscar_normativa", pregunta=pregunta)
        else:
            ultimo = str(herramientas[-1].content)
            if ultimo.startswith("SIN_RESULTADOS"):
                msg = AIMessage(content="SIN_INFORMACION")
            elif "[F" in ultimo:
                bloques = re.findall(r"(\[F\d+\]) ([^\n]+)\nUbicación: [^\n]+\nTexto: ([^\n]+)", ultimo)[:1]
                frases = [f"{texto.split('. ')[0].rstrip('.')}. {etq}" for etq, _, texto in bloques]
                msg = AIMessage(content=" ".join(frases) or "SIN_INFORMACION")
            else:
                msg = AIMessage(content=ultimo)
        msg.usage_metadata = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        return ChatResult(generations=[ChatGeneration(message=msg)])
