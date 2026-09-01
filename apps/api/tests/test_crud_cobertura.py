"""Cada recurso de negocio expone el CRUD completo, y las excepciones estan dichas.

Se empezo con 0 de 26 recursos completos y ningun DELETE en toda la API. El
hueco no era visible: hay que cruzar 60 rutas contra los metodos de cada una
para notarlo, y nadie hace eso leyendo un router.

Esta prueba lo cuenta sola. Si alguien agrega un recurso a medias, falla y dice
que le falta. Si decide a proposito no exponer una operacion, la agrega a
`SIN_CRUD_COMPLETO` con su motivo — que es la diferencia entre una decision y
un olvido.
"""
from __future__ import annotations

import re

import pytest

from app.main import app

# Operaciones que cambian de estado, no CRUD. Se excluyen del conteo porque
# `/audits/{id}/advance` no es "leer una auditoria".
SUFIJOS_DE_ACCION = (
    "/verify", "/advance", "/close", "/evaluate", "/fulfill", "/submit",
    # Las dos mitades que le faltaban al flujo de RF-31. Van aca y no en
    # SIN_CRUD_COMPLETO porque son transiciones de estado, igual que /submit:
    # "aprobar una declaracion" no es "leer una declaracion".
    "/approve", "/reject",
    # Pedir un enlace firmado no es leer ni crear un recurso: es un permiso
    # temporal que ni siquiera se guarda. Y `confirm-upload` **si crea** una
    # revision, pero no es el CRUD de `/versions` — es el cierre de una
    # subida que empezo en otro endpoint.
    "/upload-url", "/confirm-upload", "/download-url",
    # El ciclo de vida de una revision documental. Son transiciones de
    # estado, no CRUD: "aprobar una revision" no es "leer una revision".
    "/submit-review", "/return-to-draft", "/publish", "/obsolete",
    # Mover normas de la matriz a su texto vigente. Es una operacion
    # sobre las que ya estan, no un recurso: no hay una "actualizacion"
    # que listar, leer ni borrar.
    "/actualizar-versiones",
    # Una vista derivada, no un recurso: son los aspectos ya significativos a
    # los que **nadie enlazo un riesgo** (ISO 14001 §6.1.4). No se crea ni se
    # borra un "aspecto sin tratar" — se trata, y entonces sale solo.
    "/significant-untreated",
    # Tampoco un recurso: lo que vence son la inscripcion del equipo y la
    # certificacion de su operador, y las dos se editan en su propia ficha.
    # Esto es la consulta que las junta.
    "/expiring",
    # Mover un trato de columna no es editar un campo: cierra el trato, exige
    # motivo al perder o lo reabre. Y el pipeline es una vista compuesta —el
    # kanban entero— no un recurso que se cree ni se borre.
    "/stage", "/pipeline",
    # Promover un trato ganado a contrato tampoco es CRUD: enlaza dos cosas que
    # ya existen y pasa la ficha de prospecto a cliente. No crea el contrato
    # —eso exige que el cliente ya sea un tenant— ni hay nada que listar.
    "/promover",
    # Invitar no es crear un recurso "invitacion": la emite Clerk y vive en
    # su lado. Nosotros no la guardamos —duplicarla seria un segundo
    # registro de la misma cosa que se desincroniza— asi que no hay nada
    # que listar, leer ni borrar de este lado.
    "/invitacion",
    # Cuanto de lo aplicable miro una auditoria: una medicion derivada del
    # checklist, no un recurso. No se crea ni se borra una "cobertura" —
    # cambia sola al responder preguntas.
    "/coverage",
    "/stats", "/summary", "/metrics", "/audit-log", "/clerk", "/upcoming",
    "/overdue", "/generate-notifications",
)

# Recurso -> por que no tiene el CRUD entero. El motivo es la parte importante.
SIN_CRUD_COMPLETO = {
    "/permissions": "es el catalogo de permisos que la API sabe verificar: la lista de capacidades que el sistema define, no datos de una empresa. Crearlos o borrarlos desde la API seria inventar permisos que ninguna guarda consulta — el codigo tiene que existir tambien en el codigo, no solo en la tabla. Crecen con una migracion, cuando se agrega una capacidad. Lo que si se administra es a quien se le conceden, y eso vive en `/users/{id}/permissions`",
    "/me/clave-local": "no es un recurso, es una accion sobre la propia cuenta: fijar la clave local. La clave la guarda Clerk, asi que aca no hay fila que leer ni editar; volver a fijarla es llamar de nuevo al mismo POST",
    "/catalog/retc-systems": "es el catalogo de portales del Estado: se consulta, no se administra desde la API. Crearlos o editarlos a mano invitaria a inventar sistemas, y el problema real es el contrario — la lista viene de una resolucion y hay que poder rastrear de donde salio cada fila (columna `fuente`). Se siembra con migracion, como el resto del catalogo normativo",
    "/facilities/reportabilidad": "no es un recurso con id propio: es el estado de un sistema PARA una instalacion, y la pareja (instalacion, sistema) ya lo identifica. Por eso se declara con PUT sobre esa pareja en vez de POST, y por eso no hay `GET` de uno solo: la lista de la instalacion es la vista util. Leer un sistema aislado sin su contexto no le sirve a ninguna pantalla",
    "/acceso-invitado/credenciales": "no es un recurso que se administre, es una accion: se genera un acceso. Listarlos le mostraria a cualquiera los invitados de la empresa desde una ruta publica, y editarlos o borrarlos son operaciones que corresponden al Admin Empresa desde el sistema, no al invitado desde su link",
    "/acceso-invitado/sesion": "entrar no es un recurso. La sesion vive en el token que se devuelve; no hay fila que leer, editar ni borrar",
    "/acceso-invitado/solicitudes": "el invitado abre y consulta; editar y borrar una solicitud son del lado de quien la atiende, y eso ya vive en `/support/tickets` con su RBAC. Darle al invitado un `DELETE` sobre su ticket dejaria a la empresa sin el registro de un reclamo",
    "/acceso-invitado/mis-solicitudes": "es la vista de lectura del invitado sobre sus propios tickets. Crear y editar solicitudes ya vive en `/support/tickets`; duplicarlo aca serian dos caminos que mantener coherentes",
    "/catalog/countries": "la lista de paises viene dada: se consulta, no se administra. Exponerla como editable invitaria a inventar paises y a que dos empresas apuntaran a filas distintas del mismo lugar",
    "/catalog/norms": "la ley no se borra ni se edita a mano: se sincroniza desde la BCN",
    "/catalog/norms/articles": "el articulado es el texto de la ley: se sincroniza desde la BCN y se lee, no se administra",
    "/roles": "hoy es de solo lectura, y el motivo es que falta la otra mitad: `role_permissions` no tiene API. Un endpoint para crear roles produciria roles que **no conceden nada** —filas con nombre y sin permisos— y quien los asignara dejaria gente sin poder trabajar sin entender por que. Los tres roles del sistema los siembra `09_roles_por_codigo.sql`; crear roles propios (#78 pide lo mismo para las etapas del CRM) entra junto con poder darles permisos",
    "/catalog/sectors": "catalogo de referencia, compartido y de solo lectura",
    "/catalog/sources": "catalogo de referencia, compartido y de solo lectura",
    "/documents/versions": "es la evidencia que respalda el cumplimiento; borrarla dejaria sin sustento a las evaluaciones que la citan",
    "/support/chatbot/messages": "borrar un mensaje suelto vuelve enganosa la conversacion",
    "/support/tickets/messages": "borrar un mensaje suelto vuelve enganosa la conversacion",
    "/tenants": "sin resolver que significa dar de baja una empresa: marcarla no impide entrar a sus usuarios, asi que hoy seria una baja que miente",
    "/support/chatbot": "una conversacion no se edita; se cierra o se retira entera",
    "/obligations/matrix-link": "no es un recurso: es el vinculo de una obligacion con el articulo que la origina (RF-14). Se pone con PUT y se suelta con DELETE sobre la propia obligacion, que es donde vive el dato. No hay `POST` porque el vinculo no se crea aparte, ni `GET` porque ya viaja en la obligacion",
    "/compliance/article-compliance/obligations": "es la relacion leida desde el lado de la matriz (RF-09): las obligaciones que nacieron de un articulo. Editarlas o borrarlas se hace en `/obligations`, que es donde son un recurso; duplicar ahi el CRUD serian dos caminos que mantener coherentes",
    "/dashboard/incumplimientos": "no es un recurso: es una **vista** sobre dos que ya existen. Cada fila es un `article_compliance` o una `obligation`, y ahi es donde se crean, editan y borran. Darle CRUD propio serian dos caminos para escribir lo mismo, y el dia que uno valide algo que el otro no, la matriz legal y esta pantalla dirian cosas distintas sobre la misma empresa",
    "/obligations/tasks": "las tareas se listan dentro de su obligacion, no sueltas",
    "/documents": "las versiones se listan dentro de su documento",
    "/me": (
        "no es un recurso: es la identidad de quien llama, derivada del token. "
        "No hay nada que crear ni borrar — se cambia editando el usuario, no el "
        "reflejo de la sesion"
    ),
    "/catalog/clasificacion/cobertura": (
        "no es un recurso: es el conteo de que normas estan clasificadas contra "
        "que sectores. Se deriva de `norm_sectors`, y se cambia clasificando "
        "normas, no editando el conteo"
    ),
    "/compliance/resumen": (
        "no es un recurso: es el mismo conteo que "
        "`/compliance/matrices/{id}/resumen`, resuelto sobre la matriz del "
        "periodo vigente para que ningun cliente tenga que averiguar cual es"
    ),
    "/compliance/matrices/resumen": (
        "no es un recurso: es el conteo de la matriz desglosado por norma y por "
        "instalacion. Se calcula al leerlo, asi que no hay nada que crear ni "
        "borrar — cambia evaluando articulos, no editando el resumen"
    ),
    "/compliance/matrices/desactualizadas": (
        "no es un recurso: es una consulta derivada de comparar la version "
        "evaluada de cada norma contra la vigente. No hay nada que crear ni "
        "borrar — se resuelve publicando una version nueva o reevaluando"
    ),
    "/compliance/matrices/sincronizar": (
        "no es un recurso: es una operacion sobre la matriz. No hay una "
        "sincronizacion que listar, leer o borrar — lo que queda es su efecto "
        "sobre las normas de esa matriz"
    ),
    "/compliance/normativa-aplicable": (
        "no es un recurso: es un calculo derivado del perfil de la empresa y de "
        "la clasificacion del catalogo. No hay nada que crear, editar ni borrar "
        "— lo que se modifica son sus dos entradas"
    ),
    "/catalog/norms/sectors": (
        "una clasificacion no se crea aparte de la norma y el sector que la "
        "identifican, asi que el PUT idempotente cubre alta y edicion. Leer una "
        "suelta tampoco aplica: lo util es toda la clasificacion de esa norma, "
        "que sale del listado"
    ),
    "/users/roles": (
        "no es el CRUD de un recurso 'rol de usuario': el PUT describe el "
        "**estado final** de los roles de esa persona, asi que alta y edicion "
        "son la misma operacion y no hay un id de asignacion suelto que leer ni "
        "borrar. Quitar un rol es mandar la lista sin el; la lista **es** el "
        "estado. Mismo criterio que `/users/permissions`"
    ),
    "/users/desde-invitado": (
        "no es un recurso: es la accion de registrar de forma permanente a un "
        "Cliente Invitado (RF-03). Lo que crea es un usuario, que ya tiene su "
        "CRUD completo en `/users`; aca solo esta el camino desde una credencial "
        "de invitado. No hay un 'registro desde invitado' que listar ni borrar — "
        "deshacerlo es desactivar al usuario y emitir una credencial nueva"
    ),
    "/users/permissions": (
        "no se crea un permiso: existen en el catalogo global. Lo que se administra "
        "es la excepcion de una persona, y el PUT es idempotente, asi que alta y "
        "edicion son la misma operacion. Leer uno suelto tampoco aplica: lo que "
        "importa es el conjunto efectivo, que sale del listado"
    ),
}


def _cobertura(esquema: dict) -> dict[str, set[str]]:
    recursos: dict[str, set[str]] = {}
    for ruta, metodos in esquema["paths"].items():
        if not ruta.startswith("/api/v1/") or ruta == "/api/v1":
            continue
        base = re.sub(r"/\{[^}]+\}", "/{id}", ruta)
        clave = base.replace("/{id}", "").rstrip("/")[len("/api/v1"):]
        if clave.endswith(SUFIJOS_DE_ACCION):
            continue
        # Cuenta como "leer uno" solo si el ULTIMO segmento es el parametro.
        # Un recurso anidado como `/audits/{id}/participants` lleva parametro
        # del PADRE y aun asi es un listado; mirar si el path contiene `{id}`
        # en cualquier posicion los clasificaba mal a todos.
        tiene_id = base.rstrip("/").endswith("{id}")
        for metodo in metodos:
            letra = {
                "get": "R" if tiene_id else "L",
                "post": "C",
                "patch": "U",
                "put": "U",
                "delete": "D",
            }.get(metodo)
            if letra:
                recursos.setdefault(clave, set()).add(letra)
    return recursos


@pytest.fixture(scope="module")
def cobertura() -> dict[str, set[str]]:
    app.openapi_schema = None
    return _cobertura(app.openapi())


def test_los_recursos_de_negocio_tienen_crud_completo(cobertura) -> None:
    incompletos = {
        recurso: "".join(sorted({"C", "L", "R", "U", "D"} - ops))
        for recurso, ops in cobertura.items()
        if ops != {"C", "L", "R", "U", "D"} and recurso not in SIN_CRUD_COMPLETO
    }
    assert not incompletos, (
        "Recursos a medias sin motivo declarado (letra = operacion que falta; "
        f"C crear, L listar, R leer, U actualizar, D borrar): {incompletos}. "
        "Completalos, o agregalos a SIN_CRUD_COMPLETO explicando por que no."
    )


def test_las_excepciones_declaradas_siguen_existiendo(cobertura) -> None:
    """Una excepcion sobre un recurso que ya no existe es ruido que confunde."""
    fantasmas = set(SIN_CRUD_COMPLETO) - set(cobertura)
    assert not fantasmas, f"Excepciones que sobran en SIN_CRUD_COMPLETO: {fantasmas}"


def test_ninguna_excepcion_se_quedo_sin_motivo() -> None:
    vacias = [r for r, motivo in SIN_CRUD_COMPLETO.items() if not motivo.strip()]
    assert not vacias, f"Excepciones sin explicar: {vacias}"
