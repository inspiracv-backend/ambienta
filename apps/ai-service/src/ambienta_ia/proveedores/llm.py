"""
El modelo de lenguaje detrás de la interfaz de LangChain (`BaseChatModel`).

Cualquier proveedor que implemente tool calling sirve. El agente no importa nada de acá salvo
`crear_modelo`.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel


def crear_modelo(proveedor: str, modelo: str) -> BaseChatModel:
    if proveedor == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=modelo, temperature=0, timeout=60, max_retries=2)
    if proveedor == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=modelo, temperature=0, timeout=60, max_retries=2)
    if proveedor == "ollama":
        # Modelos propios, como define la arquitectura de Ambienta (Qwen3 con Ollama).
        # `reasoning=False`: Qwen3 "piensa" por defecto y eso multiplica la latencia y rompe la
        # salida estructurada del reordenador y el revisor.
        import os

        from langchain_ollama import ChatOllama

        return ChatOllama(model=modelo, temperature=0, reasoning=False,
                          base_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
                          num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "16384")), keep_alive="30m")
    raise ValueError(
        f"Proveedor de modelo desconocido: {proveedor}. "
        "El proveedor 'falso' solo se construye desde las pruebas o la demo."
    )
