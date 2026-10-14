"""
La API del AI Service. Contrato: `specs/contrato/ai-service.openapi.yaml`.

    uvicorn ambienta_ia.api.app:app --port 8100

Las dependencias (base, modelo, embeddings, verificador) se inyectan: en producción se arman
desde la configuración; en las pruebas se pasan armadas.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

from .. import __version__
from ..agente import Agente, Revisor, RevisorModelo, RevisorNulo
from ..config import Config, config
from ..conocimiento import BaseConocimiento, abrir_base
from ..consulta import ErrorConsulta, ejecutar, preparar
from ..identidad import ErrorIdentidad, VerificadorClerk, resolver_sesion
from ..observabilidad import (
    Exportador,
    ExportadorCompuesto,
    ExportadorLog,
    Traza,
    configurar_logs,
    evento,
)
from ..proveedores import Embeddings, crear_embeddings, crear_modelo
from ..recuperacion import Recuperador, Reordenador, ReordenadorModelo


class PeticionConsulta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pregunta: str = Field(min_length=2, max_length=2000)
    conversation_id: UUID | None = None
    fecha: date | None = None


@dataclass
class Dependencias:
    config: Config
    base: BaseConocimiento
    embeddings: Embeddings
    modelo: BaseChatModel
    revisor: Revisor
    verificador: VerificadorClerk | None
    exportador: Exportador = field(default_factory=ExportadorLog)
    opciones_cliente: dict[str, Any] = field(default_factory=dict)
    reordenador: Reordenador | None = None

    def agente(self) -> Agente:
        c = self.config
        recuperador = Recuperador(self.base, self.embeddings, umbral=c.umbral_evidencia, k=c.k_recuperacion,
                                  reordenador=self.reordenador)
        return Agente(self.modelo, self.revisor, recuperador, self.embeddings,
                      max_herramientas=c.max_herramientas, max_revisiones=c.max_revisiones,
                      max_tokens=c.max_tokens_consulta)


async def dependencias_desde_config(c: Config) -> Dependencias:
    base = await abrir_base(c.database_url_consulta)
    embeddings = crear_embeddings(c.proveedor_embeddings, c.modelo_embeddings, c.dimension_embeddings)
    if c.proveedor_llm == "falso":
        from ..agente.falso import ModeloDemo

        modelo: BaseChatModel = ModeloDemo()
        revisor: Revisor = RevisorNulo()
        reordenador: Reordenador | None = None
    else:
        modelo = crear_modelo(c.proveedor_llm, c.modelo_llm)
        revisor = RevisorModelo(modelo) if c.revisor_con_modelo else RevisorNulo()
        reordenador = ReordenadorModelo(modelo) if c.reordenar_con_modelo else None
    verificador = VerificadorClerk(c.clerk_jwks_url, c.clerk_issuer) if c.clerk_jwks_url else None
    return Dependencias(config=c, base=base, embeddings=embeddings, modelo=modelo, revisor=revisor,
                        verificador=verificador, exportador=ExportadorCompuesto(ExportadorLog()),
                        reordenador=reordenador)


def _error(estado: int, codigo: str, detalle: str) -> JSONResponse:
    return JSONResponse({"detail": detalle, "codigo": codigo}, status_code=estado)


def _sse(tipo: str, datos: dict[str, Any]) -> bytes:
    return f"event: {tipo}\ndata: {json.dumps(datos, ensure_ascii=False, default=str)}\n\n".encode()


def crear_app(deps: Dependencias | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo(app: FastAPI) -> AsyncIterator[None]:
        propias = deps is None
        if propias:
            configurar_logs()
            app.state.deps = await dependencias_desde_config(config())
        else:
            app.state.deps = deps
        evento("arranque", version=__version__, modo_desarrollo=app.state.deps.verificador is None)
        yield
        if propias:
            await app.state.deps.base.cerrar()

    app = FastAPI(title="Ambienta AI Service", version=__version__, lifespan=ciclo)
    if deps is not None:
        app.state.deps = deps  # disponible aunque el servidor de pruebas no corra el ciclo de vida

    @app.exception_handler(RequestValidationError)
    async def invalida(_: Request, exc: RequestValidationError) -> JSONResponse:
        primero = exc.errors()[0] if exc.errors() else {}
        campo = ".".join(str(x) for x in primero.get("loc", []) if x != "body")
        return _error(422, "peticion_invalida", f"{campo}: {primero.get('msg', 'inválido')}")

    @app.get("/salud")
    async def salud() -> dict[str, str]:
        return {"estado": "ok"}

    @app.get("/listo")
    async def listo(request: Request) -> JSONResponse:
        d: Dependencias = request.app.state.deps
        base_ok = await d.base.viva()
        backend_ok = False
        try:
            async with httpx.AsyncClient(timeout=5, transport=d.opciones_cliente.get("transporte")) as h:
                r = await h.get(f"{d.config.backend_url.rstrip('/')}/me")
                backend_ok = r.status_code < 500
        except httpx.HTTPError:
            backend_ok = False
        sincronizado = None
        if base_ok:
            try:
                async with d.base.de_empresa(None) as conn:
                    cur = await conn.execute("SELECT max(ultima_corrida) FROM sincronizacion")
                    (sincronizado,) = await cur.fetchone()
            except Exception:
                sincronizado = None
        cuerpo = {"base": "ok" if base_ok else "caida", "backend": "ok" if backend_ok else "caido",
                  "catalogo_sincronizado_en": sincronizado.isoformat() if sincronizado else None}
        return JSONResponse(cuerpo, status_code=200 if base_ok and backend_ok else 503)

    @app.post("/consulta")
    async def consulta(
        request: Request,
        peticion: PeticionConsulta,
        authorization: str | None = Header(None),
        x_tenant_id: str | None = Header(None),
        accept: str | None = Header(None),
    ):
        d: Dependencias = request.app.state.deps
        traza = Traza(pregunta=peticion.pregunta, fecha=peticion.fecha.isoformat() if peticion.fecha else None)
        try:
            sesion, cliente = await resolver_sesion(
                authorization=authorization,
                x_tenant_id=x_tenant_id,
                backend_url=d.config.backend_url,
                verificador=d.verificador,
                opciones_cliente={"timeout_s": d.config.backend_timeout_s, **d.opciones_cliente},
            )
        except ErrorIdentidad as e:
            return _error(e.estado, e.codigo, e.detalle)
        traza.tenant_id = str(sesion.tenant_id)

        try:
            preparada = await preparar(peticion.pregunta, peticion.conversation_id, sesion=sesion,
                                       cliente=cliente, turnos=d.config.turnos_de_contexto)
        except ErrorConsulta as e:
            await cliente.cerrar()
            traza.error = e.codigo
            traza.cerrar()
            d.exportador.exportar(traza)
            return _error(e.estado, e.codigo, e.detalle)

        eventos = ejecutar(peticion.pregunta, preparada, fecha=peticion.fecha, sesion=sesion,
                           cliente=cliente, agente=d.agente(), traza=traza)

        if accept and "text/event-stream" in accept:
            async def flujo() -> AsyncIterator[bytes]:
                try:
                    async for tipo, datos in eventos:
                        yield _sse(tipo, datos)
                finally:
                    await cliente.cerrar()
                    d.exportador.exportar(traza)

            return StreamingResponse(flujo(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Request-Id": traza.request_id})

        final: dict[str, Any] | None = None
        error: dict[str, Any] | None = None
        try:
            async for tipo, datos in eventos:
                if tipo == "final":
                    final = datos
                elif tipo == "error" and final is None:
                    error = datos
        finally:
            await cliente.cerrar()
            d.exportador.exportar(traza)
        if final is None:
            return _error(503, (error or {}).get("codigo", "no_disponible"),
                          (error or {}).get("detail", "No se pudo responder."))
        return JSONResponse(final, headers={"X-Request-Id": traza.request_id})

    return app


def __getattr__(nombre: str) -> Any:
    # `uvicorn ambienta_ia.api.app:app` construye la app recién cuando se la pide, así importar
    # el módulo (por ejemplo en las pruebas) no exige variables de entorno.
    if nombre == "app":
        return crear_app()
    raise AttributeError(nombre)
