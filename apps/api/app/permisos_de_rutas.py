"""Que permiso exige cada ruta (RF-08).

Spec: `openspec/changes/sistema-actores-roles-rbac/specs/rbac/spec.md`.

## Por que se deriva de la ruta y no se escribe endpoint por endpoint

Son mas de 150 escrituras. Escribir `Depends(exigir_permiso("obligation.write"))`
en cada una es una decision que se puede olvidar, y olvidarla **no falla**: deja
el endpoint abierto y nadie se entera. El hueco se abre solo, igual que pasaba
con el 401 y el 404 del contrato OpenAPI antes de derivarlos.

El codigo del ejemplo de arriba es real a proposito: `test_permisos.py` recorre
tambien los ejemplos de los docstrings, para que nadie copie uno inventado.

Derivandolo, un endpoint nuevo queda protegido sin que nadie se acuerde, y
`test_permisos_de_rutas.py` falla si aparece uno cuya raiz no esta declarada.

## El metodo decide leer o escribir

`GET` pide `.read`; `POST`, `PATCH`, `PUT` y `DELETE` piden `.write`. Las
excepciones son las operaciones que **no son CRUD** —enviar una declaracion,
cerrar una no conformidad, evaluar un articulo— porque cada una tiene su propio
permiso: el analisis pidio separar "editar la evidencia" de "firmar que basta".

## Lo que esto NO hace

No reemplaza a RLS. Decide **si la operacion se permite**, no **que filas se
ven**. El aislamiento entre empresas lo sigue garantizando Row Level Security,
que es la unica barrera (CLAUDE.md §4).
"""
from __future__ import annotations

#: Raiz de la ruta -> familia de permiso. El sufijo lo pone el metodo.
#:
#: Una familia **con punto** ya es un permiso completo y no se le agrega sufijo:
#: hay capacidades que el catalogo no divide en leer y escribir. `chatbot.use` y
#: `notification.configure` son asi, y escribirlas como familia produciria
#: `chatbot.read` y `notification.write`, que **no existen** — o sea 403 para
#: siempre. Lo detecto `test_todo_permiso_derivado_existe_en_el_catalogo_sembrado`.
FAMILIA_POR_RAIZ: dict[str, str] = {
    "audits": "audit",
    "compliance": "legal_matrix",
    "contracts": "manager",
    # El CRM es el lado comercial del modulo de Gestores, y la epica #32 lo dice:
    # consolida `Tenant.contactoComercial` y lo que ya existia ahi. Reutiliza su
    # familia en vez de inventar `crm.read` / `crm.write`, **que nadie tendria
    # asignado**: un permiso nuevo sin rol que lo conceda es un 403 para todos,
    # y el sintoma —"la pantalla no carga"— no se parece en nada a la causa.
    # `manager.read` y `manager.write` los tienen hoy `admin_empresa` y
    # `servicio_lectura`, que es justo quien usa un CRM.
    "crm": "manager",
    # La cartera de un Gestor es su vista del modulo de Gestores, asi que
    # reutiliza `manager` por el mismo motivo que el CRM: un permiso nuevo sin
    # rol que lo conceda es un 403 para todos, y "la pantalla no carga" no se
    # parece en nada a la causa. `manager.read` ya lo tienen `admin_empresa` y
    # `servicio_lectura`.
    "gestor": "manager",
    "declarations": "obligation",
    "departments": "company_profile",
    "documents": "document",
    "facilities": "company_profile",
    "integrations": "company_profile",
    "iso14001": "environmental_aspect",
    "notifications": "notification.configure",
    "obligations": "obligation",
    "processes": "company_profile",
    "support": "chatbot.use",
    "tenants": "company_profile",
    "users": "user",
    # El catalogo de roles se lee para poder ofrecer un selector, y se
    # administra con el mismo permiso que los permisos.
    "roles": "role.manage",
}

#: Rutas que **no** pasan por esta guarda, con el motivo.
#:
#: No es una lista de conveniencia: cada entrada es una decision, y el test
#: exige que ninguna se quede sin explicar.
SIN_GUARDA_DE_PERMISO: dict[str, str] = {
    "catalog": (
        "catalogo compartido sin `tenant_id`. Leer es informacion de trabajo "
        "para cualquiera; escribir ya exige Admin Global, que es una barrera "
        "mas fuerte que un permiso de empresa"
    ),
    "templates": (
        "mismo caso que el catalogo: plantillas globales, escritura ya "
        "restringida a Admin Global"
    ),
    "permissions": (
        "el catalogo de permisos: una tabla global sin `tenant_id` que dice "
        "**que permisos existen**, no quien los tiene. Solo se lee. Exigir un "
        "permiso para leerlo seria ademas incomodo: la pantalla que administra "
        "permisos lo necesita para poder pintarse, y lo que importa —escribir "
        "una excepcion— ya exige `role.manage` en `/users/{id}/permissions`"
    ),
    "webhooks": (
        "quien llama es Clerk, no un usuario. No hay sesion de la cual sacar "
        "permisos; la autenticidad se comprueba con la firma HMAC"
    ),
    "dashboard": (
        "metricas agregadas de lo que la persona ya puede ver. RLS acota las "
        "filas, asi que no hay nada que un permiso agregue"
    ),
    "acceso-invitado": (
        "un invitado **no tiene rol ni permisos**: no es usuario del sistema "
        "(decision D2). Dos de sus tres rutas son publicas a proposito, porque "
        "RF-02 pide que alguien sin cuenta pueda abrir una solicitud. Lo que lo "
        "acota no es una lista de permisos sino que **esas cuatro rutas son todo "
        "lo que puede tocar**: ningun endpoint de negocio sabe leer su token, "
        "que es de un tipo distinto de `CurrentUser`"
    ),
    "system": "salud y diagnostico del esquema; no lee datos de negocio",
    "me": (
        "preguntar quien soy y que puedo hacer **no puede exigir un permiso**: "
        "seria circular, porque la respuesta legitima puede ser 'ninguno' y "
        "entonces nadie podria ni averiguarlo. Devuelve la fila propia y la de "
        "la empresa del token, que RLS ya acota; no expone nada que quien llama "
        "no pudiera leer por otro camino"
    ),
}

#: Operaciones que no son CRUD y tienen permiso propio.
#:
#: Se identifican por el ultimo segmento de la ruta. Cada una existe porque el
#: analisis pidio separarla de la edicion: quien registra la evidencia no
#: deberia ser quien firma que basta.
PERMISO_POR_ACCION: dict[str, str] = {
    "submit": "obligation.submit",
    "fulfill": "obligation.submit",
    "close": "nonconformity.close",
    "evaluate": "legal_matrix.article.evaluate",
    "verify": "nonconformity.close",
    "audit-log": "audit_log.read",
    "generate-notifications": "notification.configure",
}

#: Sub-rutas con familia propia, mas especifica que la de su raiz.
#:
#: `/audits/nonconformities` no es lo mismo que `/audits`: cerrar una no
#: conformidad y planificar una auditoria son responsabilidades distintas, y el
#: catalogo de permisos las separa.
FAMILIA_POR_SUBRUTA: dict[tuple[str, str], str] = {
    ("audits", "nonconformities"): "nonconformity",
    ("audits", "action-plans"): "action_plan",
    ("obligations", "tasks"): "task",
    ("iso14001", "risks"): "risk_opportunity",
    ("iso14001", "equipment"): "equipment",
    ("users", "permissions"): "role.manage",
    # Asignar un rol **es** decidir que puede hacer alguien, asi que exige el
    # mismo permiso que administrar permisos individuales y no `user.write`:
    # quien puede editar el nombre de una persona no deberia poder hacerla
    # administradora.
    ("users", "roles"): "role.manage",
}

_ESCRITURAS = frozenset({"POST", "PATCH", "PUT", "DELETE"})


def permiso_requerido(camino: str, metodo: str) -> str | None:
    """Que permiso exige esta ruta, o `None` si no pasa por la guarda.

    `camino` es la plantilla de la ruta (`/api/v1/obligations/{id}`), no la URL
    concreta: se compara por forma, no por valores.
    """
    if not camino.startswith("/api/v1/"):
        return None

    partes = [p for p in camino[len("/api/v1/") :].split("/") if p]
    if not partes:
        return None

    raiz = partes[0]
    if raiz in SIN_GUARDA_DE_PERMISO:
        return None

    # Las acciones ganan sobre todo lo demas: tienen permiso propio justamente
    # para no confundirse con editar el recurso.
    ultimo = partes[-1]
    if ultimo in PERMISO_POR_ACCION:
        return PERMISO_POR_ACCION[ultimo]

    familia = None
    for parte in partes[1:]:
        if (raiz, parte) in FAMILIA_POR_SUBRUTA:
            familia = FAMILIA_POR_SUBRUTA[(raiz, parte)]
            break
    if familia is None:
        familia = FAMILIA_POR_RAIZ.get(raiz)
    if familia is None:
        return None

    # Una familia con punto ya es un permiso completo: administrar permisos no
    # se divide en leer y escribir, es una sola capacidad.
    if "." in familia:
        return familia

    return f"{familia}.{'write' if metodo.upper() in _ESCRITURAS else 'read'}"
