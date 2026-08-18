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
PostgreSQL aplica Row Level Security sobre 38 tablas.

**RLS no es la segunda barrera: es la unica.** Ninguna consulta de la
aplicacion filtra por `tenant_id`. La API se conecta con un rol que **no puede
saltarse RLS**, asi que la separacion entre empresas la garantiza enteramente
PostgreSQL. La consecuencia practica para quien integra: un endpoint mal
escrito devuelve **cero filas**, nunca datos de otra empresa. Una respuesta
vacia inesperada es el sintoma de esa falla, no una fuga.

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
        "name": "departments",
        "description": (
            "Departamentos de la empresa. `facility_id` es opcional: hay "
            "departamentos transversales que no cuelgan de ninguna planta."
        ),
    },
    {
        "name": "processes",
        "description": (
            "Mapa de procesos. Es de donde cuelgan los aspectos ambientales: "
            "sin procesos no hay donde registrar que impacto genera cada "
            "actividad."
        ),
    },
    {
        "name": "integrations",
        "description": (
            "Cuentas de integracion con sistemas externos. Guardan con quien "
            "esta conectada la empresa y con que alcance, **no** la "
            "credencial: el puntero al secreto nunca se devuelve."
        ),
    },
    {
        "name": "contracts",
        "description": (
            "Contratos entre una consultora y su empresa cliente. La gestora "
            "la fija el servidor con el tenant de la sesion; el "
            "consentimiento de la contraparte todavia no se modela."
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
        "name": "templates",
        "description": (
            "Plantillas de obligacion y declaracion. Son catalogo **global**, "
            "sin `tenant_id`: lo que se cree aca lo ven todas las empresas. "
            "Leer, cualquiera; escribir, solo Admin Global."
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
        "name": "declarations",
        "description": (
            "Declaraciones enviadas a la autoridad. Es lo que cierra una "
            "obligacion: el envio concreto, con su folio y su comprobante."
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


_RESPUESTA_422 = {
    "description": (
        "El cuerpo no cumple el esquema: falta un campo obligatorio, un tipo "
        "no calza, o un identificador referenciado no existe en la empresa "
        "de la sesion. `detail` viene como **lista**, un elemento por campo."
    ),
    "content": {
        "application/json": {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "name"],
                        "msg": "Field required",
                        "type": "missing",
                    }
                ]
            }
        }
    },
}

# Recurso -> (singular con articulo, plural con articulo).
#
# Se escribe a mano a proposito: "facilities" no se traduce solo a
# "instalaciones", y un plural mal formado en 206 operaciones se nota mas que
# la ausencia de texto. Lo que NO se escribe a mano es que operacion lleva que
# frase — eso se deriva del metodo y de la forma de la ruta.
_RECURSOS: dict[str, tuple[str, str]] = {
    "action-plans": ("el plan de accion", "los planes de accion"),
    "article-compliance": ("el cumplimiento del articulo", "el cumplimiento por articulo"),
    "articles": ("el articulo", "los articulos"),
    "aspects": ("el aspecto ambiental", "los aspectos ambientales"),
    "audits": ("la auditoria", "las auditorias"),
    "chatbot": ("la conversacion con el asistente", "las conversaciones con el asistente"),
    "compliance": ("la evaluacion de cumplimiento", "las evaluaciones de cumplimiento"),
    "contracts": ("el contrato", "los contratos"),
    "countries": ("el pais", "los paises"),
    "declarations": ("la declaracion", "las declaraciones"),
    "departments": ("el departamento", "los departamentos"),
    "documents": ("el documento", "los documentos"),
    "entities": ("la entidad fiscalizadora", "las entidades fiscalizadoras"),
    "equipment": ("el equipo regulado", "los equipos regulados"),
    "facilities": ("la instalacion", "las instalaciones"),
    "integrations": ("la cuenta de integracion", "las cuentas de integracion"),
    "items": ("el item del checklist", "los items del checklist"),
    "matrices": ("la matriz", "las matrices"),
    "matrix-norms": ("la norma de la matriz", "las normas de la matriz"),
    "messages": ("el mensaje", "los mensajes"),
    "nonconformities": ("la no conformidad", "las no conformidades"),
    "norms": ("la norma", "las normas"),
    "notifications": ("la notificacion", "las notificaciones"),
    "obligations": ("la obligacion", "las obligaciones"),
    "operators": ("el operador", "los operadores"),
    "participants": ("el participante", "los participantes"),
    "permissions": ("el permiso", "los permisos"),
    "processes": ("el proceso", "los procesos"),
    "risks": ("el riesgo y oportunidad", "los riesgos y oportunidades"),
    "rules": ("la regla", "las reglas"),
    "sectors": ("el sector economico", "los sectores economicos"),
    "sources": ("la fuente normativa", "las fuentes normativas"),
    "tasks": ("la tarea", "las tareas"),
    "templates": ("la plantilla", "las plantillas"),
    "tenants": ("la empresa", "las empresas"),
    "tickets": ("el ticket de soporte", "los tickets de soporte"),
    "users": ("el usuario", "los usuarios"),
    "versions": ("la version del documento", "las versiones del documento"),
}

# Endpoints que no son CRUD: cambian de estado o calculan algo. La frase no se
# puede derivar del recurso, asi que va escrita.
_ACCIONES: dict[str, tuple[str, str]] = {
    "advance": (
        "Avanzar la etapa",
        "Mueve el registro a la etapa siguiente de su ciclo. La etapa no se "
        "elige: se avanza en orden, y el salto lo decide el servidor.",
    ),
    "close": ("Cerrar", "Da por terminado el registro. Un registro cerrado ya no admite cambios."),
    "verify": (
        "Verificar la eficacia",
        "Registra si la accion tomada resolvio el problema. Es tri-estado: "
        "eficaz, no eficaz, o todavia sin verificar.",
    ),
    "evaluate": (
        "Evaluar el cumplimiento",
        "Registra la respuesta de cumplimiento sobre el articulo y deja "
        "constancia de quien la respondio y cuando.",
    ),
    "fulfill": ("Marcar como cumplida", "Deja la obligacion como cumplida en el periodo vigente."),
    "submit": (
        "Enviar la declaracion",
        "Envia la declaracion a la autoridad. Es el paso que la vuelve "
        "oficial; despues de enviarla no se edita.",
    ),
    "stats": ("Obtener estadisticas", "Conteos agregados, calculados en la base y no en el cliente."),
    "summary": ("Obtener el resumen", "Vista agregada del estado actual, lista para mostrar."),
    "metrics": (
        "Obtener las metricas del tablero",
        "Cumplimiento global, incumplimientos, no conformidades abiertas y "
        "vencimientos proximos. Se calculan en la base.",
    ),
    "audit-log": (
        "Consultar la bitacora",
        "Registro de cambios, solo lectura. La bitacora no se edita ni se "
        "borra: es la evidencia de que paso.",
    ),
    "upcoming": ("Listar los vencimientos proximos", "Lo que vence dentro de la ventana consultada."),
    "overdue": ("Listar lo vencido", "Lo que ya paso su plazo y sigue sin cumplirse."),
    "generate-notifications": (
        "Generar las notificaciones pendientes",
        "Recorre los vencimientos y crea los avisos que falten. Es "
        "idempotente: llamarlo dos veces no duplica avisos.",
    ),
    "clerk": (
        "Recibir eventos de Clerk",
        "Entrada del proveedor de identidad. **No lleva Bearer**: la "
        "autenticidad se comprueba con la firma HMAC del payload.",
    ),
}

_VERBOS = {
    ("get", False): "Listar",
    ("get", True): "Obtener",
    ("post", False): "Crear",
    ("patch", True): "Actualizar",
    ("put", True): "Reemplazar",
    ("delete", True): "Eliminar",
}


def _recibe_un_id(ruta: str) -> bool:
    """Si la ruta lleva `{algo}`, ese algo puede no existir."""
    return "{" in ruta


def _segmentos(ruta: str) -> list[str]:
    """Los segmentos de la ruta sin el prefijo de version."""
    partes = [p for p in ruta.strip("/").split("/") if p]
    if partes[:2] == ["api", "v1"]:
        partes = partes[2:]
    return partes


def _summaries_por_defecto(app: FastAPI) -> dict[tuple[str, str], str]:
    """Que `summary` habria puesto FastAPI solo, por ruta y metodo.

    Hace falta para no pisar el texto que alguien escribio a mano. FastAPI
    nunca deja el campo vacio —lo arma con el nombre de la funcion, `list_audits`
    a "List Audits"—, asi que preguntar `if not operacion.get("summary")` no
    distingue lo generado de lo deliberado. Reconstruir el valor por defecto
    desde `app.routes` si lo distingue.

    Se recorre en profundidad **a proposito**: esta version de FastAPI no
    aplana los routers incluidos, los deja envueltos en un nodo intermedio.
    Mirar solo `app.routes` encuentra 3 rutas de 209 y hace creer que todo el
    resto ya estaba documentado a mano.
    """
    por_defecto: dict[tuple[str, str], str] = {}

    def recorrer(rutas, prefijo: str = "") -> None:
        for ruta in rutas:
            # Router incluido: el nodo no tiene ruta propia. El camino real es
            # el prefijo con el que se incluyo mas el de cada hija.
            interno = getattr(ruta, "original_router", None)
            if interno is not None:
                contexto = getattr(ruta, "include_context", None)
                recorrer(interno.routes, prefijo + getattr(contexto, "prefix", ""))
                continue
            hijas = getattr(ruta, "routes", None)
            if hijas:
                recorrer(hijas, prefijo)
                continue
            nombre = getattr(ruta, "name", None)
            camino = getattr(ruta, "path", None)
            if not nombre or not camino:
                continue
            for metodo in getattr(ruta, "methods", ()) or ():
                por_defecto[(prefijo + camino, metodo.lower())] = (
                    nombre.replace("_", " ").title()
                )

    recorrer(app.routes)
    return por_defecto


def _contraer(frase: str) -> str:
    """`de el` es `del`, y `a el` es `al`.

    Sale de concatenar la preposicion con el articulo que ya trae el glosario.
    Un titulo que dice "Listar las versiones de el documento" se lee como un
    texto generado por una maquina, que es justo lo que hay que evitar cuando
    el objetivo es que /docs se pueda leer sin esfuerzo.
    """
    return frase.replace(" de el ", " del ").replace(" a el ", " al ")


def _describir(ruta: str, metodo: str) -> tuple[str, str] | None:
    """Arma el titulo y la explicacion de una operacion desde su ruta.

    Devuelve `None` cuando la ruta no cae en ningun patron conocido, y en ese
    caso se respeta lo que traiga el codigo. Preferimos un hueco a una frase
    inventada: un texto generado que describe mal es peor que ninguno, porque
    quien lo lee no tiene como saber que no es de fiar.
    """
    partes = _segmentos(ruta)
    if not partes:
        return None

    ultimo = partes[-1]
    if ultimo in _ACCIONES:
        return _ACCIONES[ultimo]

    apunta_a_uno = ultimo.startswith("{")
    # El recurso es el ultimo segmento que no es un parametro.
    concretos = [p for p in partes if not p.startswith("{")]
    if not concretos:
        return None
    recurso = concretos[-1]
    if recurso not in _RECURSOS:
        return None
    singular, plural = _RECURSOS[recurso]

    # Anidado: `/audits/{audit_id}/participants` habla de los participantes
    # *de esa auditoria*, y decirlo cambia como se lee la operacion.
    padre = padre_sing = ""
    if len(concretos) > 1 and "{" in ruta.split(recurso)[0]:
        anterior = concretos[-2]
        if anterior in _RECURSOS:
            padre_sing = _RECURSOS[anterior][0]
            padre = _contraer(f" de {padre_sing}")

    # `POST /audits/{id}/participants/{user_id}` no crea nada: vincula dos
    # cosas que ya existen. Tratarlo como alta diria que se esta creando un
    # usuario, que es justo lo contrario de lo que pasa.
    if padre_sing and apunta_a_uno and metodo in ("post", "delete"):
        if metodo == "post":
            return (
                _contraer(f"Vincular {singular} a {padre_sing}"),
                _contraer(
                    f"Asocia {singular} —que ya existe— a {padre_sing}. No crea "
                    "el registro: ambos extremos tienen que existir antes."
                ),
            )
        return (
            _contraer(f"Desvincular {singular} de {padre_sing}"),
            f"Quita la asociacion entre {singular} y {padre_sing}. Ninguno "
            "de los dos se borra: solo deja de existir el vinculo.",
        )

    verbo = _VERBOS.get((metodo, apunta_a_uno))
    if verbo is None:
        return None

    sustantivo = singular if apunta_a_uno or metodo in ("post", "patch", "put", "delete") else plural
    titulo = f"{verbo} {sustantivo}{padre}"

    detalle = {
        "get": (
            f"Devuelve {sustantivo}{padre} de la empresa de la sesion."
            + ("" if apunta_a_uno else " Paginado con `skip` y `limit`.")
        ),
        "post": (
            f"Crea {singular}{padre}. El `tenant_id` **no se manda en el "
            "cuerpo**: se toma de la sesion, asi que no se puede crear a "
            "nombre de otra empresa."
        ),
        "patch": (
            f"Actualiza {singular}{padre}. Solo se aplican los campos "
            "presentes en el cuerpo; los omitidos quedan como estaban."
        ),
        "put": f"Reemplaza {singular}{padre} por completo.",
        "delete": (
            f"Da de baja {singular}{padre}. El borrado es **logico**: la fila "
            "se marca con `deleted_at` y deja de aparecer en los listados, "
            "pero se conserva para no dejar sin sustento a lo que la cita."
        ),
    }[metodo]

    return titulo[0].upper() + titulo[1:], detalle


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

    por_defecto = _summaries_por_defecto(app)

    for ruta, metodos in esquema["paths"].items():
        for metodo, operacion in metodos.items():
            if metodo not in ("get", "post", "patch", "put", "delete"):
                continue
            respuestas = operacion.setdefault("responses", {})
            if operacion.get("security"):
                respuestas.setdefault("401", _RESPUESTA_401)
            if _recibe_un_id(ruta):
                respuestas.setdefault("404", _RESPUESTA_404)
            if operacion.get("requestBody"):
                respuestas["422"] = _RESPUESTA_422

            # El texto derivado no pisa al escrito a mano: si alguien se tomo
            # el trabajo de explicar un endpoint, sabe mas que esta regla.
            derivado = _describir(ruta, metodo)
            if derivado is None:
                continue
            titulo, detalle = derivado
            # FastAPI siempre pone un `summary` sacado del nombre de la
            # funcion ("List Audits"), asi que no sirve preguntar si existe:
            # hay que comparar contra ese valor por defecto.
            if operacion.get("summary", "") == por_defecto.get((ruta, metodo)):
                operacion["summary"] = titulo
            if not operacion.get("description"):
                operacion["description"] = detalle

    app.openapi_schema = esquema
    return esquema
