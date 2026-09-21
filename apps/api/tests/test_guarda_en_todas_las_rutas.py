"""Toda ruta de la API pasa por la guarda, salvo las que declaran por que no.

## Lo que se midio el 21-sep

`crm`, `gestor` e `iso14001` se montaban **sin** `exigir_permiso_de_la_ruta`
desde la migracion a FastAPI (4-ago): 17 escrituras del CRM y 13 de ISO 14001
no pedian ningun permiso, el Admin Global podia editarlas y la suspension de
una empresa no las alcanzaba. `permisos_de_rutas.py` si les calculaba el
permiso —la web incluso ocultaba el CRM contando con esa guarda—, asi que el
barrido de reglas sin efecto (`test_registro_de_actividades.py`) no lo vio:
la regla existia; lo que faltaba era enchufarla.

Por eso esta prueba no mira que permiso se calcula sino **que dependencia
tiene montada cada ruta de verdad**.
"""
from __future__ import annotations

from app.deps import exigir_escritura_en_empresa_activa, exigir_permiso_de_la_ruta
from app.main import app

#: Raices sin la guarda de permisos, cada una con su motivo. Agregar una aca es
#: una decision: si no tiene motivo escrito, no va.
SIN_GUARDA_DE_LA_RUTA: dict[str, str] = {
    "webhooks": "quien llama es Clerk y firma con HMAC; no hay sesion de la cual sacar permisos",
    "me": "preguntar quien soy no puede exigir un permiso: la respuesta legitima puede ser 'ninguno'",
    "acceso-invitado": "el invitado no tiene rol; su token es de otro tipo que ningun endpoint de negocio lee",
    "comentarios": "el permiso sale de `entity_type` en el cuerpo y lo decide el handler",
    "historial": "igual que comentarios: el permiso depende de que registro se pide",
    "buscar": "el permiso depende de que se encuentra, y el handler decide que se busca",
}

#: Raices cuyas escrituras no pasan por la regla de solo lectura, con su motivo.
SIN_SOLO_LECTURA: dict[str, str] = {
    "webhooks": "sincroniza cuentas de Clerk; bloquearlo dejaria la base desalineada con Clerk",
    "acceso-invitado": "ya rechaza a las empresas suspendidas o cerradas al ingresar (acceso_invitado.py)",
    "me": "la clave local es de la cuenta de la persona y la guarda Clerk, no es un dato de la empresa",
}

_ESCRITURAS = {"POST", "PUT", "PATCH", "DELETE"}


def _rutas():
    for r in app.routes:
        camino = getattr(r, "path", "")
        if not camino.startswith("/api/v1/"):
            continue
        raiz = camino[len("/api/v1/") :].split("/")[0]
        dependencias = {getattr(d, "dependency", None) for d in getattr(r, "dependencies", [])}
        yield raiz, camino, set(getattr(r, "methods", None) or ()), dependencias


def test_el_barrido_ve_rutas() -> None:
    assert len(list(_rutas())) > 150, "la aplicacion no expone rutas: el barrido no mira nada"


def test_todas_las_rutas_pasan_por_la_guarda() -> None:
    sin_guarda = sorted(
        f"{sorted(m)} {c}"
        for raiz, c, m, deps in _rutas()
        if exigir_permiso_de_la_ruta not in deps and raiz not in SIN_GUARDA_DE_LA_RUTA
    )
    assert sin_guarda == [], (
        "Rutas sin `exigir_permiso_de_la_ruta` y sin motivo declarado. Montala en "
        "el `include_router`, o agregala a SIN_GUARDA_DE_LA_RUTA diciendo por que:\n  "
        + "\n  ".join(sin_guarda)
    )


def test_toda_escritura_respeta_la_solo_lectura() -> None:
    """Comentar, adjuntar, cualquier escritura: una empresa suspendida no escribe."""
    faltan = sorted(
        f"{sorted(m & _ESCRITURAS)} {c}"
        for raiz, c, m, deps in _rutas()
        if m & _ESCRITURAS
        and not deps & {exigir_permiso_de_la_ruta, exigir_escritura_en_empresa_activa}
        and raiz not in SIN_SOLO_LECTURA
    )
    assert faltan == [], "Escrituras que una empresa suspendida puede hacer:\n  " + "\n  ".join(faltan)


def test_las_excepciones_no_quedan_viejas() -> None:
    """Una excepcion que ya no exceptua nada es una puerta que alguien puede
    volver a abrir sin que se note. Si la raiz ya tiene la guarda, se saca de
    la lista."""
    sin_guarda = {raiz for raiz, _c, _m, deps in _rutas() if exigir_permiso_de_la_ruta not in deps}
    viejas = sorted(set(SIN_GUARDA_DE_LA_RUTA) - sin_guarda)
    assert viejas == [], f"Estas raices ya tienen la guarda; sacalas de la lista: {viejas}"

    escriben_sin_regla = {
        raiz
        for raiz, _c, m, deps in _rutas()
        if m & _ESCRITURAS and not deps & {exigir_permiso_de_la_ruta, exigir_escritura_en_empresa_activa}
    }
    viejas = sorted(set(SIN_SOLO_LECTURA) - escriben_sin_regla)
    assert viejas == [], f"Estas raices ya respetan la solo lectura; sacalas de la lista: {viejas}"
