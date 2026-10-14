"""
Backend simulado con las reglas del handoff del 08/09.

    uvicorn ambienta_ia.demo.backend_simulado:app --port 8000

Identidad:
- Con `X-Tenant-Id` y sin `Authorization`: modo desarrollo (usuario null, permisos vacíos).
- Con `Authorization: Bearer <jwt>`: lee `tenant_id` y `sub` **sin verificar la firma**. La
  verificación es del AI Service (SPEC-02); acá solo se simula qué haría el backend con ese
  token. Nunca usar esto fuera de pruebas.
"""

from __future__ import annotations

import copy
import itertools
from datetime import UTC, date, datetime
from typing import Any

import jwt
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel

from . import datos as D

LIMITE_POR_DEFECTO = 100
LIMITE_MAXIMO = 500


class ConversacionNueva(BaseModel):
    user_id: str
    title: str | None = None
    scope: str = "tenant"


class MensajeNuevo(BaseModel):
    conversation_id: str
    role: str
    content: str
    citations: list[Any] = []
    cited_norm_ids: list[str] = []
    model_name: str | None = None
    token_usage: dict[str, Any] = {}


class Estado:
    def __init__(self) -> None:
        self.datos = D.construir()
        self.conversaciones: dict[str, dict] = {}
        self.mensajes: dict[str, list[dict]] = {}
        self.ids_mensaje = itertools.count(1)
        self.fallas: dict[str, int] = {}  # ruta → cuántas veces responder 500 (para pruebas)
        self.peticiones: list[tuple[str, str, dict]] = []


def crear_app(estado: Estado | None = None) -> FastAPI:
    app = FastAPI(title="Ambienta API (simulada)")
    app.state.e = estado or Estado()

    def e(request: Request) -> Estado:
        return request.app.state.e

    # -- identidad ---------------------------------------------------------

    def identidad(request: Request, authorization: str | None, x_tenant_id: str | None) -> dict:
        est = e(request)
        est.peticiones.append((request.method, request.url.path, {"auth": bool(authorization), "tenant": x_tenant_id}))
        falla = est.fallas.get(request.url.path, 0)
        if falla:
            est.fallas[request.url.path] = falla - 1
            raise HTTPException(500, "falla simulada")
        if authorization:
            token = authorization.removeprefix("Bearer ").strip()
            try:
                claims = jwt.decode(token, options={"verify_signature": False})
            except jwt.PyJWTError as ex:
                raise HTTPException(401, "Token inválido") from ex
            tenant = claims.get("tenant_id")
            if not tenant:
                raise HTTPException(403, "La cuenta no tiene empresa asignada")
            usuario = est.datos["usuarios"].get(claims.get("sub"))
            permisos = claims.get("permisos_demo", D.PERMISOS_COMPLETOS)
            return {"tenant": tenant, "usuario": usuario, "permisos": permisos, "dev": False}
        if x_tenant_id:
            return {"tenant": x_tenant_id, "usuario": None, "permisos": [], "dev": True}
        raise HTTPException(401, "Falta el token")

    def exigir(ident: dict, permiso: str) -> None:
        if not ident["dev"] and permiso not in ident["permisos"]:
            raise HTTPException(403, f"Falta el permiso {permiso}.")

    def paginar(response: Response, filas: list, skip: int, limit: int) -> list:
        if limit > LIMITE_MAXIMO:
            raise HTTPException(422, f"limit no puede superar {LIMITE_MAXIMO}")
        pagina = filas[skip : skip + limit]
        response.headers["X-Has-More"] = "true" if skip + limit < len(filas) else "false"
        response.headers["X-Page-Limit"] = str(limit)
        return pagina

    @app.get("/api/v1/me")
    def me(request: Request, authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        empresa = e(request).datos["empresas"].get(ident["tenant"])
        u = ident["usuario"]
        return {
            "modo_desarrollo": ident["dev"],
            "usuario": {k: v for k, v in u.items() if k != "tenant_id"} if u else None,
            "empresa": empresa,
            "roles": [] if ident["dev"] else ["admin_empresa"],
            "permisos": ident["permisos"],
            "acotado": False,
            "instalaciones": [],
            "departamentos": [],
        }

    # -- catálogo ----------------------------------------------------------

    def normas_visibles(est: Estado, tenant: str) -> list[dict]:
        return [n for n in est.datos["normas"] if n.get("tenant_id") in (None, tenant)]

    @app.get("/api/v1/catalog/norms")
    def normas(
        request: Request, response: Response,
        updated_since: datetime | None = None, tipo: str | None = None, buscar: str | None = None,
        skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
        authorization: str | None = Header(None), x_tenant_id: str | None = Header(None),
    ):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "catalog.read")
        # Como el real (verificado el 21/09/2026): RLS deja ver lo público MÁS lo propio de la
        # empresa que pregunta, y la respuesta no trae tenant_id para distinguirlos.
        filas = normas_visibles(e(request), ident["tenant"])
        if updated_since:
            if updated_since.tzinfo is None:
                updated_since = updated_since.replace(tzinfo=UTC)
            filas = [n for n in filas if datetime.fromisoformat(n["updated_at"]) > updated_since]
        if tipo:
            filas = [n for n in filas if n["norm_type"] == tipo]
        if buscar:
            b = buscar.lower()
            filas = [n for n in filas if b in n["title"].lower() or b in (n["norm_number"] or "").lower()]
        filas.sort(key=lambda n: (n["norm_type"], n["norm_number"] or "", n["id"]))
        return paginar(response, [{k: v for k, v in n.items() if k != "tenant_id"} for n in filas], skip, limit)

    @app.get("/api/v1/catalog/norms/{norm_id}/versions")
    def versiones(request: Request, norm_id: str, response: Response, skip: int = 0,
                  limit: int = LIMITE_POR_DEFECTO, authorization: str | None = Header(None),
                  x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        est = e(request)
        if norm_id not in {n["id"] for n in normas_visibles(est, ident["tenant"])}:
            raise HTTPException(404, "No encontrado")
        filas = sorted(est.datos["versiones"].get(norm_id, []), key=lambda v: v["valid_from"], reverse=True)
        return paginar(response, filas, skip, limit)

    @app.get("/api/v1/catalog/norms/{norm_id}/articles")
    def articulos(request: Request, norm_id: str, response: Response, vigente_el: date | None = None,
                  skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                  authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        est = e(request)
        if norm_id not in {n["id"] for n in normas_visibles(est, ident["tenant"])}:
            raise HTTPException(404, "No encontrado")
        dia = vigente_el or date.today()
        version = None
        for desde, hasta, vid in est.datos["vigencia"].get(norm_id, []):
            if desde <= dia and (hasta is None or dia <= hasta):
                version = vid
        filas = est.datos["articulos"].get(version, []) if version else []
        return paginar(response, filas, skip, limit)

    # -- empresa -----------------------------------------------------------

    @app.get("/api/v1/compliance/normativa-propia/")
    def normativa_propia(request: Request, response: Response, skip: int = 0,
                         limit: int = LIMITE_POR_DEFECTO, authorization: str | None = Header(None),
                         x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "legal_matrix.read")
        est = e(request)
        filas = []
        for n in est.datos["normas"]:
            if n.get("tenant_id") != ident["tenant"]:
                continue
            vid = est.datos["versiones"][n["id"]][0]["id"]
            filas.append({"id": n["id"], "tenant_id": n["tenant_id"], "source_id": 2,
                          "norm_type": n["norm_type"], "norm_number": n["norm_number"],
                          "title": n["title"], "issuing_body": n["issuing_body"],
                          "publication_date": None, "articulos": len(est.datos["articulos"][vid])})
        return filas  # como el real: sin updated_at, sin paginar

    @app.get("/api/v1/compliance/normativa-propia/{norma_id}/articulos")
    def articulos_propios(request: Request, norma_id: str, authorization: str | None = Header(None),
                          x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "legal_matrix.read")
        est = e(request)
        norma = next((n for n in est.datos["normas"] if n["id"] == norma_id), None)
        if norma is None or norma.get("tenant_id") != ident["tenant"]:
            raise HTTPException(404, "No encontrado")
        vid = est.datos["versiones"][norma_id][0]["id"]
        return est.datos["articulos"][vid]

    @app.get("/api/v1/facilities/")
    def instalaciones(request: Request, response: Response, skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                      authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "company_profile.read")
        filas = [f for f in e(request).datos["instalaciones"] if f["tenant_id"] == ident["tenant"]]
        return paginar(response, filas, skip, limit)

    # -- monitoreo y plataforma -------------------------------------------

    @app.get("/api/v1/compliance/matrix-norms")
    def normas_de_matriz(request: Request, response: Response, skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                         authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "legal_matrix.read")
        return paginar(response, [m for m in e(request).datos["matriz"] if m["tenant_id"] == ident["tenant"]],
                       skip, limit)

    @app.get("/api/v1/notifications/")
    def notificaciones(request: Request, response: Response, skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                       authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "notification.configure")
        return paginar(response, [n for n in e(request).datos["notificaciones"] if n["tenant_id"] == ident["tenant"]],
                       skip, limit)

    @app.post("/api/v1/notifications/", status_code=201)
    def crear_notificacion(request: Request, cuerpo: dict, authorization: str | None = Header(None),
                           x_tenant_id: str | None = Header(None)):
        import uuid

        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "notification.configure")
        if cuerpo.get("channel") not in ("email", "in_app") or not cuerpo.get("body"):
            raise HTTPException(422, "channel y body son obligatorios")
        n = {"id": str(uuid.uuid4()), "tenant_id": ident["tenant"], "rule_id": None, "status": "queued",
             "recipient_user_id": cuerpo.get("recipient_user_id"), "channel": cuerpo["channel"],
             "subject": cuerpo.get("subject"), "body": cuerpo["body"], "context": cuerpo.get("context") or {},
             "autor": (ident["usuario"] or {}).get("clerk_id")}
        e(request).datos["notificaciones"].append(n)
        return n

    @app.get("/api/v1/support/tickets")
    def tickets(request: Request, response: Response, skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        return paginar(response, [t for t in e(request).datos["tickets"] if t["tenant_id"] == ident["tenant"]],
                       skip, limit)

    @app.post("/api/v1/support/tickets", status_code=201)
    def crear_ticket(request: Request, cuerpo: dict, authorization: str | None = Header(None),
                     x_tenant_id: str | None = Header(None)):
        import uuid

        ident = identidad(request, authorization, x_tenant_id)
        est = e(request)
        t = {"id": str(uuid.uuid4()), "tenant_id": ident["tenant"],
             "ticket_number": f"TCK-{len(est.datos['tickets']) + 1:04d}", "status": "open", **cuerpo}
        est.datos["tickets"].append(t)
        return t

    @app.get("/api/v1/tenants/")
    def cartera(request: Request, response: Response, skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        est = e(request)
        global_ = bool(ident["usuario"]) and ident["usuario"].get("admin_global")
        filas = [{"id": k, "tenant_type": "company", "legal_name": v["nombre"], "trade_name": v["nombre"],
                  "status": "active", "sector_id": v.get("sector_id"), "size_bracket": v.get("tramo"),
                  "tiene_perfil_normativo": True}
                 for k, v in est.datos["empresas"].items() if global_ or k == ident["tenant"]]
        return paginar(response, filas, skip, limit)

    @app.get("/api/v1/catalog/sync-runs")
    def sincronizaciones(request: Request, limite: int = 10, authorization: str | None = Header(None),
                         x_tenant_id: str | None = Header(None)):
        identidad(request, authorization, x_tenant_id)
        return [{"id": 1, "status": "success", "started_at": "2026-09-21T10:38:00+00:00",
                 "finished_at": "2026-09-21T10:39:24+00:00", "response_metadata": {"normas": 23}}][:limite]

    @app.get("/api/v1/obligations/")
    def obligaciones(request: Request, response: Response, skip: int = 0,
                     limit: int = LIMITE_POR_DEFECTO, authorization: str | None = Header(None),
                     x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "obligation.read")
        filas = [o for o in e(request).datos["obligaciones"] if o["tenant_id"] == ident["tenant"]]
        return paginar(response, filas, skip, limit)

    @app.get("/api/v1/documents/")
    def documentos(request: Request, response: Response, updated_since: datetime | None = None,
                   skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                   authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "document.read")
        filas = [d for d in e(request).datos["documentos"] if d["tenant_id"] == ident["tenant"]]
        if updated_since:
            filas = [d for d in filas if datetime.fromisoformat(d["updated_at"]) > updated_since]
        return paginar(response, filas, skip, limit)

    @app.get("/api/v1/documents/vinculados")
    def vinculados(request: Request, entity_type: str, entity_id: str, response: Response,
                   skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                   authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "document.read")
        est = e(request)
        ids = est.datos["vinculos"].get((entity_type, entity_id), [])
        filas = [d for d in est.datos["documentos"] if d["id"] in ids and d["tenant_id"] == ident["tenant"]]
        return paginar(response, filas, skip, limit)

    @app.get("/api/v1/documents/{document_id}/versions")
    def versiones_documento(request: Request, document_id: str, response: Response, skip: int = 0,
                            limit: int = LIMITE_POR_DEFECTO, authorization: str | None = Header(None),
                            x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "document.read")
        filas = [v for v in e(request).datos["versiones_documento"].get(document_id, [])
                 if v["tenant_id"] == ident["tenant"]]
        if not filas:
            raise HTTPException(404, "No encontrado")
        return paginar(response, filas, skip, limit)

    @app.get("/api/v1/documents/{document_id}/versions/{version_id}/download-url")
    def descarga(request: Request, document_id: str, version_id: str,
                 authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        identidad(request, authorization, x_tenant_id)
        raise HTTPException(503, "Almacenamiento de archivos no configurado")

    @app.get("/api/v1/buscar/")
    def buscar_transversal(request: Request, q: str = Query(...),
                           authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        if len(q.strip()) < 2:
            raise HTTPException(422, "La búsqueda necesita al menos 2 caracteres")
        est = e(request)
        b = q.lower()
        grupos = []
        obl = [o for o in est.datos["obligaciones"] if o["tenant_id"] == ident["tenant"] and b in o["title"].lower()]
        if obl:
            grupos.append({"tipo": "obligation", "hay_mas": len(obl) > 10, "coincidencias": [
                {"tipo": "obligation", "id": o["id"], "titulo": o["title"], "codigo": o["code"], "contexto": {}}
                for o in obl[:10]]})
        docs = [d for d in est.datos["documentos"] if d["tenant_id"] == ident["tenant"] and b in d["title"].lower()]
        if docs:
            grupos.append({"tipo": "document", "hay_mas": False, "coincidencias": [
                {"tipo": "document", "id": d["id"], "titulo": d["title"], "codigo": None, "contexto": {}}
                for d in docs[:10]]})
        return {"grupos": grupos}

    @app.get("/api/v1/historial/")
    def historial(request: Request, entity_type: str, entity_id: str,
                  authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        identidad(request, authorization, x_tenant_id)
        return {"eventos": [], "fuentes": ["actividad", "comentarios", "adjuntos"],
                "fuentes_pendientes": ["correo"], "hay_mas": False}

    @app.get("/api/v1/comentarios/")
    def comentarios(request: Request, entity_type: str, entity_id: str, response: Response,
                    skip: int = 0, limit: int = LIMITE_POR_DEFECTO,
                    authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        filas = [c for c in e(request).datos["comentarios"].get((entity_type, entity_id), [])
                 if c["tenant_id"] == ident["tenant"]]
        return paginar(response, filas, skip, limit)

    # -- chatbot -----------------------------------------------------------

    def conversacion_propia(est: Estado, conv_id: str, tenant: str) -> dict:
        c = est.conversaciones.get(conv_id)
        if not c or c["tenant_id"] != tenant:
            raise HTTPException(404, "No encontrado")  # ajena o inexistente: no se distingue
        return c

    @app.post("/api/v1/support/chatbot", status_code=201)
    def abrir(request: Request, cuerpo: ConversacionNueva, authorization: str | None = Header(None),
              x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "chatbot.use")
        if ident["usuario"] is None:
            raise HTTPException(409, "Una conversación necesita un usuario identificado")
        if cuerpo.user_id != ident["usuario"]["id"]:
            raise HTTPException(422, "user_id no corresponde a la sesión")
        import uuid

        ahora = datetime.now(UTC).isoformat()
        c = {"id": str(uuid.uuid4()), "tenant_id": ident["tenant"], "user_id": cuerpo.user_id,
             "title": cuerpo.title, "scope": cuerpo.scope, "facility_id": None, "status": "abierta",
             "last_message_at": None, "created_at": ahora, "updated_at": ahora}
        est = e(request)
        est.conversaciones[c["id"]] = c
        est.mensajes[c["id"]] = []
        return c

    @app.get("/api/v1/support/chatbot/{conv_id}")
    def ver(request: Request, conv_id: str, authorization: str | None = Header(None),
            x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        return conversacion_propia(e(request), conv_id, ident["tenant"])

    @app.get("/api/v1/support/chatbot/{conv_id}/messages")
    def hilo(request: Request, conv_id: str, response: Response, skip: int = 0,
             limit: int = LIMITE_POR_DEFECTO, authorization: str | None = Header(None),
             x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        est = e(request)
        conversacion_propia(est, conv_id, ident["tenant"])
        filas = sorted(est.mensajes[conv_id], key=lambda m: m["id"])  # el ORDER BY que se arregló
        return paginar(response, copy.deepcopy(filas), skip, limit)

    @app.post("/api/v1/support/chatbot/{conv_id}/messages", status_code=201)
    def guardar(request: Request, conv_id: str, cuerpo: MensajeNuevo,
                authorization: str | None = Header(None), x_tenant_id: str | None = Header(None)):
        ident = identidad(request, authorization, x_tenant_id)
        exigir(ident, "chatbot.use")
        est = e(request)
        conversacion_propia(est, conv_id, ident["tenant"])
        m = {"id": next(est.ids_mensaje), "tenant_id": ident["tenant"], "conversation_id": conv_id,
             "role": cuerpo.role, "content": cuerpo.content, "citations": cuerpo.citations,
             "cited_norm_ids": cuerpo.cited_norm_ids, "model_name": cuerpo.model_name,
             "token_usage": cuerpo.token_usage, "feedback": {},
             "created_at": datetime.now(UTC).isoformat()}
        est.mensajes[conv_id].append(m)
        return m

    return app


app = crear_app()
