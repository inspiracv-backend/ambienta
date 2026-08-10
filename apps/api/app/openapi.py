"""Curado del contrato OpenAPI.

FastAPI genera el esquema solo, y lo que genera es correcto pero incompleto:
describe los caminos felices y calla los errores. Ninguna de las 91
operaciones declaraba el 401 que todas devuelven sin token, ni el 404 que
lanzan las que reciben un id. Un contrato que no dice como falla obliga a
descubrirlo probando, que es justo lo que el contrato existe para evitar.

Las respuestas de error no se escriben endpoint por endpoint: se derivan de la
propia ruta en `construir_esquema()`. Asi un endpoint nuevo las hereda sin que
nadie se acuerde de agregarlas.

Spec: CLAUDE.md §3 (API First + OpenAPI).
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

DESCRIPCION = """
API de gestion de cumplimiento ambiental para empresas industriales en Chile.

## Autenticacion

Todos los endpoints de negocio exigen un **JWT emitido por Clerk** en la
cabecera `Authorization: Bearer <token>`.

El token tiene que traer el claim **`tenant_id`**, que es lo que determina que
datos se ven. No viaja en el token de sesion estandar: hay que pedirlo por
plantilla (`getToken({ template: 'default' })`). Sin ese claim la API responde
401 en todos los endpoints, aunque la firma sea valida.

### Modo desarrollo

Si la API arranca **sin** `CLERK_JWKS_URL`, acepta la cabecera
`X-Tenant-Id: <uuid>` en lugar del token. Es lo que permite levantar el
proyecto sin cuenta del proveedor.

Con Clerk configurado esa cabecera **se ignora por completo**: un token de una
empresa con `X-Tenant-Id` de otra sigue devolviendo los datos de la primera.
No es un permiso que se pueda olvidar apagado — lo gobierna la misma variable
que hace falta para validar firmas.

## Aislamiento entre empresas

Cada consulta se ejecuta con el tenant de la sesion fijado en la conexion, y
PostgreSQL aplica Row Level Security sobre 38 tablas. Es una segunda barrera:
una consulta mal escrita no puede devolver datos de otra empresa.

## Convenciones

- Fechas y horas en **ISO 8601 con zona** (`timestamptz`).
- Identificadores de negocio en **UUID**.
- Listados paginados con `skip` y `limit`.
- Los errores devuelven `{"detail": "..."}`.
"""

TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "health",
        "description": (
            "Sondas de vida y de disponibilidad. `/health` no toca la base; "
            "`/health/db` comprueba que responda y que el esquema este cargado."
        ),
    },
    {
        "name": "dashboard",
        "description": (
            "Metricas agregadas del tablero: cumplimiento global, "
            "incumplimientos, no conformidades abiertas y vencimientos "
            "proximos. Calculadas en la base, no en el cliente."
        ),
    },
    {
        "name": "tenants",
        "description": (
            "Empresas cliente. Es la unica entidad sin `tenant_id`: es la "
            "tabla de empresas, no se referencia a si misma."
        ),
    },
    {
        "name": "facilities",
        "description": "Instalaciones, plantas y faenas de una empresa.",
    },
    {
        "name": "users",
        "description": (
            "Usuarios de la empresa. La identidad la administra Clerk; aca "
            "vive a que empresa pertenece cada uno y que puede hacer."
        ),
    },
    {
        "name": "catalog",
        "description": (
            "Catalogo normativo **compartido entre todas las empresas**: "
            "fuentes, sectores, normas y articulado. No lleva `tenant_id` "
            "porque la ley es la misma para todos. Solo lectura: se "
            "sincroniza desde la fuente oficial, no se edita a mano."
        ),
    },
    {
        "name": "compliance",
        "description": (
            "Matriz legal por empresa: que normas le aplican y como cumple "
            "cada articulo. Es la bisagra entre el catalogo compartido y el "
            "cumplimiento propio de cada cliente."
        ),
    },
    {
        "name": "obligations",
        "description": (
            "Obligaciones con vencimiento, sus tareas y las declaraciones "
            "que las cumplen."
        ),
    },
    {
        "name": "audits",
        "description": (
            "Auditorias, hallazgos, no conformidades y planes de accion."
        ),
    },
    {
        "name": "nonconformities",
        "description": (
            "No conformidades detectadas en una auditoria. Cuelgan de "
            "`audits` pero tienen tag propio porque viven mas alla de la "
            "auditoria que las origino."
        ),
    },
    {
        "name": "action-plans",
        "description": (
            "Planes de accion. Nacen de una no conformidad o de un hallazgo "
            "de la matriz legal, y son el vinculo entre detectar y corregir."
        ),
    },
    {
        "name": "business-logic",
        "description": (
            "Operaciones que **cambian de estado**, no CRUD: avanzar una "
            "auditoria, cerrar una no conformidad, verificar un plan, "
            "evaluar un articulo. Van aparte a proposito — un PATCH deja "
            "poner cualquier valor; estas aplican las reglas que decide el "
            "backend."
        ),
    },
    {
        "name": "iso14001",
        "description": (
            "Aspectos e impactos ambientales, riesgos y oportunidades, y "
            "equipos regulados con su certificacion."
        ),
    },
    {
        "name": "documents",
        "description": (
            "Documentos y evidencia, con versionado. La evidencia se asocia "
            "a la entidad que la respalda, no al reves."
        ),
    },
    {
        "name": "notifications",
        "description": "Avisos, sus plantillas y las reglas que los disparan.",
    },
    {
        "name": "support",
        "description": (
            "Tickets de soporte y conversaciones del asistente. Es la via de "
            "entrada del Cliente Invitado, que accede sin cuenta."
        ),
    },
    {
        "name": "system",
        "description": (
            "Registro de auditoria. Es **inmutable**: la base rechaza UPDATE "
            "y DELETE sobre el (RNF-25)."
        ),
    },
    {
        "name": "webhooks",
        "description": (
            "Entrada de eventos de Clerk. **No usa Bearer**: quien llama es "
            "el proveedor, no un usuario, y la autenticidad se comprueba con "
            "la firma HMAC del payload."
        ),
    },
    {
        "name": "meta",
        "description": "Raiz de la API versionada.",
    },
]

_RESPUESTA_401 = {
    "description": (
        "Falta el token, es invalido, o no trae el claim `tenant_id`. "
        "Revisar que se pida el token por plantilla."
    ),
    "content": {
        "application/json": {
            "schema": {"$ref": "#/components/schemas/DetalleError"},
            "example": {"detail": "Falta el token de autenticacion."},
        }
    },
}

_RESPUESTA_404 = {
    "description": (
        "No existe un recurso con ese identificador **en la empresa de la "
        "sesion**. Un recurso de otra empresa tambien responde 404, no 403: "
        "la API no confirma que exista."
    ),
    "content": {
        "application/json": {
            "schema": {"$ref": "#/components/schemas/DetalleError"},
            "example": {"detail": "Not found"},
        }
    },
}

_ESQUEMA_ERROR = {
    "title": "DetalleError",
    "type": "object",
    "properties": {
        "detail": {
            "type": "string",
            "title": "Detalle",
            "description": "Que fallo, en lenguaje entendible.",
        }
    },
    "required": ["detail"],
}


def _recibe_un_id(ruta: str) -> bool:
    """Si la ruta lleva `{algo}`, ese algo puede no existir."""
    return "{" in ruta


def construir_esquema(app: FastAPI) -> dict:
    """Genera el OpenAPI y le agrega lo que FastAPI no puede inferir.

    Las dos reglas se derivan de la ruta, no de una lista que haya que
    mantener:

    - **401** en toda operacion que declare seguridad. Si exige token, puede
      rechazarlo.
    - **404** en toda operacion con parametro de ruta. Si recibe un id, ese id
      puede no existir.

    Se cachea en `app.openapi_schema` como hace FastAPI: el esquema se arma una
    vez, no en cada visita a `/docs`.
    """
    if app.openapi_schema:
        return app.openapi_schema

    esquema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )

    esquema.setdefault("components", {}).setdefault("schemas", {})[
        "DetalleError"
    ] = _ESQUEMA_ERROR

    for ruta, metodos in esquema["paths"].items():
        for metodo, operacion in metodos.items():
            if metodo not in ("get", "post", "patch", "put", "delete"):
                continue
            respuestas = operacion.setdefault("responses", {})
            if operacion.get("security"):
                respuestas.setdefault("401", _RESPUESTA_401)
            if _recibe_un_id(ruta):
                respuestas.setdefault("404", _RESPUESTA_404)

    app.openapi_schema = esquema
    return esquema
