"""
El cliente del backend de Ambienta (SPEC-01).

Lo que resuelve, para que nadie más lo tenga que pensar:

1. **La empresa no es un parámetro.** Va en el token (o en `X-Tenant-Id` en modo desarrollo) y
   se fija al construir el cliente. Ningún método acepta `tenant_id`.
2. **Paginación por cabecera.** El cuerpo es un arreglo pelado; se sigue mientras
   `X-Has-More: true`. Nunca se deduce el final por el tamaño de la página: 100 filas de 340 y
   100 de 100 se ven iguales.
3. **Reintentos solo donde sirven.** 5xx y red: 1, 2 y 4 segundos. 4xx: nunca. El 503 de
   descarga tampoco: es almacenamiento sin configurar, insistir no lo arregla.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date, datetime
from typing import Any, TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel

from . import errores
from .modelos import (
    Articulo,
    Comentario,
    Conversacion,
    Documento,
    EmpresaDeCartera,
    EnlaceDescarga,
    Historial,
    Instalacion,
    Me,
    Mensaje,
    MensajeNuevo,
    Norma,
    NormaDeMatriz,
    NormaPropia,
    Notificacion,
    NotificacionNueva,
    Obligacion,
    ResultadoBusqueda,
    Ticket,
    TicketNuevo,
    VersionDocumento,
    VersionNorma,
)

T = TypeVar("T", bound=BaseModel)

LIMITE_MAXIMO = 500  # el backend responde 422 por encima (handoff §3)
REINTENTOS = 3
ESPERA_INICIAL_S = 1.0

Dormir = Callable[[float], Awaitable[None]]


def _iso(valor: datetime | date | None) -> str | None:
    return valor.isoformat() if valor is not None else None


class ClienteBackend:
    def __init__(
        self,
        base_url: str,
        cabeceras: dict[str, str],
        *,
        timeout_s: float = 20.0,
        transporte: httpx.AsyncBaseTransport | None = None,
        dormir: Dormir = asyncio.sleep,
    ):
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=cabeceras,
            timeout=timeout_s,
            transport=transporte,
        )
        self._dormir = dormir

    # -- construcción -------------------------------------------------------

    @classmethod
    def con_token(cls, base_url: str, token: str, **kw: Any) -> ClienteBackend:
        if not token:
            raise ValueError("Sin token no hay cliente: la empresa viaja ahí adentro.")
        return cls(base_url, {"Authorization": f"Bearer {token}"}, **kw)

    @classmethod
    def modo_desarrollo(cls, base_url: str, tenant_id: UUID | str, **kw: Any) -> ClienteBackend:
        """Solo sirve contra un backend sin CLERK_JWKS_URL. Con Clerk, la cabecera se ignora."""
        return cls(base_url, {"X-Tenant-Id": str(tenant_id)}, **kw)

    async def cerrar(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> ClienteBackend:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.cerrar()

    # -- transporte ---------------------------------------------------------

    async def _pedir(
        self,
        metodo: str,
        ruta: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        es_descarga: bool = False,
    ) -> httpx.Response:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        espera = ESPERA_INICIAL_S
        ultimo: str = ""

        for intento in range(REINTENTOS):
            try:
                r = await self._http.request(metodo, ruta, params=params, json=json)
            except httpx.RequestError as e:
                ultimo = f"{type(e).__name__}: {e}"
            else:
                if r.status_code < 400:
                    return r
                detalle = _detalle(r)
                if r.status_code == 503 and es_descarga:
                    raise errores.AlmacenamientoNoConfigurado(detalle, 503)
                if r.status_code < 500:
                    raise _error_4xx(r.status_code, detalle)
                ultimo = f"{r.status_code}: {detalle}"

            if intento < REINTENTOS - 1:
                await self._dormir(espera)
                espera *= 2

        raise errores.BackendCaido(f"{metodo} {ruta} no respondió tras {REINTENTOS} intentos ({ultimo})")

    async def _uno(self, ruta: str, modelo: type[T], **params: Any) -> T:
        r = await self._pedir("GET", ruta, params=params)
        return modelo.model_validate(r.json())

    async def _lista(self, ruta: str, modelo: type[T], **params: Any) -> list[T]:
        return [x async for x in self._paginar(ruta, modelo, **params)]

    async def _paginar(
        self, ruta: str, modelo: type[T], *, limit: int = 100, **params: Any
    ) -> AsyncIterator[T]:
        """
        Recorre las páginas mientras el backend diga `X-Has-More: true`.

        Si la cabecera no viene, el endpoint no pagina y la respuesta está completa.
        """
        if limit > LIMITE_MAXIMO:
            raise ValueError(f"limit {limit} supera el máximo del backend ({LIMITE_MAXIMO}).")
        skip = 0
        while True:
            r = await self._pedir("GET", ruta, params={**params, "skip": skip, "limit": limit})
            for fila in r.json():
                yield modelo.model_validate(fila)
            if r.headers.get("X-Has-More", "false").lower() != "true":
                return
            skip += limit

    # -- identidad ----------------------------------------------------------

    async def yo(self) -> Me:
        return await self._uno("/me", Me)

    # -- catálogo -----------------------------------------------------------

    def normas(
        self,
        *,
        updated_since: datetime | None = None,
        tipo: str | None = None,
        buscar: str | None = None,
        limit: int = 100,
    ) -> AsyncIterator[Norma]:
        return self._paginar(
            "/catalog/norms",
            Norma,
            limit=limit,
            updated_since=_iso(updated_since),
            tipo=tipo,
            buscar=buscar,
        )

    async def norma(self, norm_id: UUID) -> Norma:
        return await self._uno(f"/catalog/norms/{norm_id}", Norma)

    async def versiones(self, norm_id: UUID) -> list[VersionNorma]:
        return await self._lista(f"/catalog/norms/{norm_id}/versions", VersionNorma)

    async def articulos(self, norm_id: UUID, *, vigente_el: date | None = None) -> list[Articulo]:
        """Una norma sin texto para esa fecha devuelve [], no 404 (handoff §4)."""
        return await self._lista(
            f"/catalog/norms/{norm_id}/articles", Articulo, vigente_el=_iso(vigente_el)
        )

    # -- de la empresa ------------------------------------------------------

    def normativa_propia(self) -> AsyncIterator[NormaPropia]:
        return self._paginar("/compliance/normativa-propia/", NormaPropia)

    async def articulos_propios(self, norma_id: UUID) -> list[Articulo]:
        """
        El articulado de una RCA o ISO de la empresa. Ruta propia a propósito: el catálogo
        público también los devuelve, pero por un efecto de borde que el backend no garantiza.
        """
        return await self._lista(f"/compliance/normativa-propia/{norma_id}/articulos", Articulo)

    def instalaciones(self) -> AsyncIterator[Instalacion]:
        return self._paginar("/facilities/", Instalacion)

    def obligaciones(self) -> AsyncIterator[Obligacion]:
        return self._paginar("/obligations/", Obligacion)

    def documentos(self, *, updated_since: datetime | None = None) -> AsyncIterator[Documento]:
        return self._paginar("/documents/", Documento, updated_since=_iso(updated_since))

    async def documentos_vinculados(self, entity_type: str, entity_id: UUID) -> list[Documento]:
        return await self._lista(
            "/documents/vinculados", Documento, entity_type=entity_type, entity_id=str(entity_id)
        )

    async def versiones_documento(self, document_id: UUID) -> list[VersionDocumento]:
        return await self._lista(f"/documents/{document_id}/versions", VersionDocumento)

    async def enlace_descarga(self, document_id: UUID, version_id: UUID) -> EnlaceDescarga:
        """El checksum viene en la misma respuesta que el enlace: se valida contra ese."""
        r = await self._pedir(
            "GET", f"/documents/{document_id}/versions/{version_id}/download-url", es_descarga=True
        )
        return EnlaceDescarga.model_validate(r.json())

    async def buscar(self, q: str) -> ResultadoBusqueda:
        return await self._uno("/buscar/", ResultadoBusqueda, q=q)

    async def historial(self, entity_type: str, entity_id: UUID) -> Historial:
        return await self._uno(
            "/historial/", Historial, entity_type=entity_type, entity_id=str(entity_id)
        )

    async def comentarios(self, entity_type: str, entity_id: UUID) -> list[Comentario]:
        return await self._lista(
            "/comentarios/", Comentario, entity_type=entity_type, entity_id=str(entity_id)
        )

    # -- monitoreo --------------------------------------------------------

    def normas_de_matriz(self) -> AsyncIterator[NormaDeMatriz]:
        return self._paginar("/compliance/matrix-norms", NormaDeMatriz)

    def notificaciones(self) -> AsyncIterator[Notificacion]:
        return self._paginar("/notifications/", Notificacion)

    async def crear_notificacion(self, n: NotificacionNueva) -> Notificacion:
        r = await self._pedir("POST", "/notifications/", json=n.model_dump(mode="json", exclude_none=True))
        return Notificacion.model_validate(r.json())

    def tickets(self) -> AsyncIterator[Ticket]:
        return self._paginar("/support/tickets", Ticket)

    async def crear_ticket(self, t: TicketNuevo) -> Ticket:
        r = await self._pedir("POST", "/support/tickets", json=t.model_dump(mode="json"))
        return Ticket.model_validate(r.json())

    # -- plataforma (Admin Global) ----------------------------------------

    def cartera(self) -> AsyncIterator[EmpresaDeCartera]:
        """Para el Admin Global, todas las empresas; para cualquier otro, la propia."""
        return self._paginar("/tenants/", EmpresaDeCartera)

    async def sincronizaciones_bcn(self, limite: int = 10) -> list[dict]:
        r = await self._pedir("GET", "/catalog/sync-runs", params={"limite": limite})
        return r.json()

    # -- chatbot ------------------------------------------------------------

    async def abrir_conversacion(self, user_id: UUID, titulo: str) -> Conversacion:
        """`user_id` es el UUID interno de /me, no el id de Clerk (handoff §1)."""
        r = await self._pedir(
            "POST",
            "/support/chatbot",
            json={"user_id": str(user_id), "title": titulo[:200], "scope": "tenant"},
        )
        return Conversacion.model_validate(r.json())

    async def conversacion(self, conversation_id: UUID) -> Conversacion:
        return await self._uno(f"/support/chatbot/{conversation_id}", Conversacion)

    async def mensajes(self, conversation_id: UUID) -> list[Mensaje]:
        return await self._lista(f"/support/chatbot/{conversation_id}/messages", Mensaje)

    async def guardar_mensaje(self, conversation_id: UUID, mensaje: MensajeNuevo) -> Mensaje:
        cuerpo = {"conversation_id": str(conversation_id), **mensaje.model_dump(mode="json")}
        r = await self._pedir("POST", f"/support/chatbot/{conversation_id}/messages", json=cuerpo)
        return Mensaje.model_validate(r.json())


def _detalle(r: httpx.Response) -> str:
    try:
        cuerpo = r.json()
    except ValueError:
        return r.text[:300]
    if isinstance(cuerpo, dict) and "detail" in cuerpo:
        d = cuerpo["detail"]
        # El handoff dice que `detail` es siempre texto, pero algunos 403 lo traen como objeto
        # ({"codigo": "sesion_sin_usuario", "mensaje": "..."}): verificado el 21/09/2026.
        if isinstance(d, dict):
            return str(d.get("mensaje") or d.get("detail") or d)
        return d if isinstance(d, str) else str(d)
    return str(cuerpo)[:300]


def _error_4xx(estado: int, detalle: str) -> errores.ErrorBackend:
    clase = {
        401: errores.SinAutenticar,
        403: errores.SinPermiso,
        404: errores.NoEncontrado,
        409: errores.EstadoNoAdmite,
        422: errores.PeticionInvalida,
    }.get(estado, errores.ErrorBackend)
    return clase(detalle, estado)
