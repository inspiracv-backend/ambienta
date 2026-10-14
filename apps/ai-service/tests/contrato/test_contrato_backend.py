"""
SPEC-01 · Los modelos y las rutas del cliente coinciden con el contrato real del backend.

Contra `backend_openapi_2026-09-08.json`, el `docs/integracion-agente/openapi.json` del commit
a02e872 (el del handoff). Esta prueba es la que faltaba el 20/09: el backend simulado repetía
nuestros supuestos, así que no podía detectar que la normativa propia no trae `updated_at` ni
que el estado de una revisión se llama `lifecycle_status`.

Cuando el backend publique un contrato nuevo, se reemplaza el JSON y se corre esto.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from ambienta_ia.backend import modelos as m

SPEC = json.loads((pathlib.Path(__file__).parent / "backend_openapi_2026-09-08.json").read_text())
ESQUEMAS = SPEC["components"]["schemas"]

# nuestro modelo → su esquema
CORRESPONDENCIA = {
    m.Me: "IdentidadRead",
    m.Usuario: "UsuarioDeLaSesion",
    m.Empresa: "EmpresaDeLaSesion",
    m.Norma: "LegalNormRead",
    m.NormaPropia: "NormaPropiaRead",
    m.VersionNorma: "LegalNormVersionRead",
    m.Articulo: "LegalArticleRead",
    m.Obligacion: "ObligationRead",
    m.Instalacion: "FacilityRead",
    m.NormaDeMatriz: "MatrixNormRead",
    m.Notificacion: "NotificationRead",
    m.NotificacionNueva: "NotificationCreate",
    m.TicketNuevo: "SupportTicketCreate",
    m.Ticket: "SupportTicketRead",
    m.EmpresaDeCartera: "TenantRead",
    m.Documento: "DocumentRead",
    m.VersionDocumento: "DocumentVersionRead",
    m.EnlaceDescarga: "EnlaceDeDescarga",
    m.ResultadoBusqueda: "ResultadoRead",
    m.GrupoBusqueda: "GrupoRead",
    m.Historial: "HistoriaRead",
    m.Comentario: "ComentarioRead",
    m.Conversacion: "ChatbotConversationRead",
    m.Mensaje: "ChatbotMessageRead",
    m.MensajeNuevo: "ChatbotMessageCreate",
}

# Campos que leemos a la defensiva y que el esquema no declara, con el motivo.
DEFENSIVOS = {
    (m.Norma, "tenant_id"): "si una norma de empresa se colara en el catálogo público, se omite",
    (m.NormaPropia, "official_url"): "opcional; una RCA no tiene enlace a Ley Chile",
    (m.Comentario, "cuerpo"): "alias defensivo de body",
}

# Rutas que llama el cliente
RUTAS = [
    ("get", "/api/v1/me"),
    ("get", "/api/v1/catalog/norms"),
    ("get", "/api/v1/catalog/norms/{norm_id}"),
    ("get", "/api/v1/catalog/norms/{norm_id}/versions"),
    ("get", "/api/v1/catalog/norms/{norm_id}/articles"),
    ("get", "/api/v1/compliance/normativa-propia/"),
    ("get", "/api/v1/obligations/"),
    ("get", "/api/v1/facilities/"),
    ("get", "/api/v1/compliance/matrix-norms"),
    ("get", "/api/v1/notifications/"),
    ("post", "/api/v1/notifications/"),
    ("get", "/api/v1/support/tickets"),
    ("post", "/api/v1/support/tickets"),
    ("get", "/api/v1/tenants/"),
    ("get", "/api/v1/documents/"),
    ("get", "/api/v1/documents/vinculados"),
    ("get", "/api/v1/documents/{document_id}/versions"),
    ("get", "/api/v1/documents/{document_id}/versions/{version_id}/download-url"),
    ("get", "/api/v1/buscar/"),
    ("get", "/api/v1/historial/"),
    ("get", "/api/v1/comentarios/"),
    ("post", "/api/v1/support/chatbot"),
    ("get", "/api/v1/support/chatbot/{conversation_id}"),
    ("get", "/api/v1/support/chatbot/{conversation_id}/messages"),
    ("post", "/api/v1/support/chatbot/{conversation_id}/messages"),
]

# Posteriores al contrato del 08/09 (rama feat/cierre-con-eficacia, sin regenerar el JSON).
RUTAS_POSTERIORES = {("get", "/api/v1/compliance/normativa-propia/{norma_id}/articulos"),
                     ("get", "/api/v1/catalog/sync-runs")}


@pytest.mark.parametrize("modelo,esquema", CORRESPONDENCIA.items(), ids=lambda x: getattr(x, "__name__", x))
def test_los_campos_que_leemos_existen(modelo, esquema):
    propiedades = set(ESQUEMAS[esquema].get("properties", {}))
    faltan = {
        c for c in modelo.model_fields
        if c not in propiedades and (modelo, c) not in DEFENSIVOS
    }
    assert not faltan, f"{modelo.__name__} lee {sorted(faltan)}, que {esquema} no declara"


@pytest.mark.parametrize("modelo,esquema", CORRESPONDENCIA.items(), ids=lambda x: getattr(x, "__name__", x))
def test_lo_que_exigimos_el_backend_lo_garantiza(modelo, esquema):
    requeridos = set(ESQUEMAS[esquema].get("required", []))
    exigidos = {c for c, f in modelo.model_fields.items() if f.is_required()}
    if modelo in (m.MensajeNuevo, m.NotificacionNueva, m.TicketNuevo):
        return  # es lo que mandamos, no lo que leemos
    sobran = exigidos - requeridos
    assert not sobran, f"{modelo.__name__} exige {sorted(sobran)}, que {esquema} no garantiza"


@pytest.mark.parametrize("metodo,ruta", RUTAS)
def test_las_rutas_que_llamamos_existen(metodo, ruta):
    assert metodo in SPEC["paths"].get(ruta, {}), f"{metodo.upper()} {ruta} no está en el contrato"


def test_las_rutas_posteriores_al_contrato_estan_anotadas():
    for metodo, ruta in RUTAS_POSTERIORES:
        assert metodo not in SPEC["paths"].get(ruta, {}), (
            f"{ruta} ya está en el contrato: pasarla a RUTAS")
