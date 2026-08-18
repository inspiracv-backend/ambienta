"""Cada endpoint de empresa declara la conexion que acota sus datos.

Cierra #98. `test_aislamiento.py` prueba que la base aisla; esta prueba cubre
el hueco de al lado: que **cada ruta pida la dependencia correcta**.

Son cosas distintas. Row Level Security solo actua si la transaccion declaro
su empresa, y quien la declara es `get_tenant_db`. Un endpoint escrito con
`get_db` no lanza ninguna excepcion: **devuelve cero filas**. Da una pantalla
vacia inexplicable, y nadie lo relaciona con la dependencia equivocada.

Revisar esto a mano exige cruzar 98 rutas contra la firma de cada funcion.
Nadie hace eso leyendo un router, asi que el hueco se abre solo: alguien copia
un endpoint del catalogo global para un recurso de empresa y se lleva el
`get_db` puesto.

Las excepciones estan declaradas con su motivo — que es la diferencia entre
una decision y un olvido.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.deps import get_admin_db, get_tenant_db
from app.main import app

# Prefijo -> por que NO usa `get_tenant_db`. El motivo es la parte importante.
SIN_ALCANCE_DE_EMPRESA = {
    "/api/v1/catalog": (
        "catalogo normativo global: la ley es la misma para todas las empresas, "
        "y sus tablas no llevan tenant_id"
    ),
    "/api/v1/templates": (
        "plantillas del catalogo global. Leer, cualquiera autenticado; escribir, "
        "solo Admin Global: una empresa no puede cambiarle el catalogo a las demas"
    ),
    "/api/v1/tenants": (
        "es la tabla de empresas: no se referencia a si misma, asi que no lleva "
        "tenant_id sobre el cual acotar"
    ),
    "/api/v1/webhooks": (
        "quien llama es Clerk, no un usuario. Un `user.deleted` llega sin metadatos "
        "y hay que poder buscarlo en todas las empresas"
    ),
    "/health": "sonda de vida y de esquema; no lee datos de negocio",
}

# Rutas exactas, no prefijos. `/api/v1` va aca y **no** arriba: como prefijo se
# come todas las rutas de la API —empiezan todas por el— y dejaria esta prueba
# aprobando sin revisar ninguna. Paso exactamente eso al escribirla.
CAMINOS_SIN_ALCANCE = {
    "/api/v1": "raiz de la version; no lee datos",
}


def _rutas():
    """Todas las rutas, entrando en los routers incluidos.

    Se recorre en profundidad **a proposito**: esta version de FastAPI no
    aplana los routers incluidos, los envuelve en un nodo intermedio. Mirar
    solo `app.routes` encuentra 3 rutas de 98 y esta prueba pasaria sin
    revisar nada.
    """
    encontradas: list[tuple[str, APIRoute]] = []

    def recorrer(rutas, prefijo: str = "") -> None:
        for ruta in rutas:
            interno = getattr(ruta, "original_router", None)
            if interno is not None:
                contexto = getattr(ruta, "include_context", None)
                recorrer(interno.routes, prefijo + getattr(contexto, "prefix", ""))
                continue
            hijas = getattr(ruta, "routes", None)
            if hijas:
                recorrer(hijas, prefijo)
                continue
            if isinstance(ruta, APIRoute):
                encontradas.append((prefijo + ruta.path, ruta))

    recorrer(app.routes)
    return encontradas


def _dependencias(dependant) -> set:
    """Los invocables de los que depende una ruta, incluidos los anidados.

    `get_tenant_db` cuelga de `get_current_user`, asi que mirar solo el primer
    nivel no alcanza.
    """
    vistos = set()

    def bajar(d) -> None:
        for sub in d.dependencies:
            if sub.call is not None and sub.call not in vistos:
                vistos.add(sub.call)
                bajar(sub)

    bajar(dependant)
    return vistos


@pytest.fixture(scope="module")
def alcance() -> list[tuple[str, str, set]]:
    return [
        (camino, metodo, _dependencias(ruta.dependant))
        for camino, ruta in _rutas()
        for metodo in ruta.methods
        if metodo in ("GET", "POST", "PATCH", "PUT", "DELETE")
    ]


def _exceptuada(camino: str) -> bool:
    """Un prefijo cubre lo que cuelga de el, no lo que apenas comparte texto.

    Se compara contra `prefijo + "/"` en vez de `startswith(prefijo)`: si
    manana existiera `/api/v1/catalogos-privados`, el prefijo `/catalog` lo
    taparia sin que nadie lo note.
    """
    if camino in CAMINOS_SIN_ALCANCE:
        return True
    return any(
        camino == p or camino.startswith(p + "/") for p in SIN_ALCANCE_DE_EMPRESA
    )


def test_todo_endpoint_de_empresa_usa_get_tenant_db(alcance) -> None:
    """Sin `get_tenant_db` la transaccion no declara empresa y RLS no filtra nada."""
    sin_alcance = [
        f"{metodo} {camino}"
        for camino, metodo, deps in alcance
        if not _exceptuada(camino) and get_tenant_db not in deps
    ]
    assert not sin_alcance, (
        "Endpoints de datos de empresa sin `get_tenant_db`: "
        f"{sin_alcance}. Devuelven cero filas en silencio. Cambia la dependencia, "
        "o agrega el prefijo a SIN_ALCANCE_DE_EMPRESA explicando por que no lleva."
    )


def test_ningun_endpoint_publico_usa_la_conexion_administradora(alcance) -> None:
    """`get_admin_db` cruza empresas. Solo el webhook y el health lo justifican."""
    permitidos = ("/api/v1/webhooks", "/health")
    indebidos = [
        f"{metodo} {camino}"
        for camino, metodo, deps in alcance
        if get_admin_db in deps and not camino.startswith(permitidos)
    ]
    assert not indebidos, (
        f"Usan la conexion que se salta el aislamiento: {indebidos}. "
        "Cualquier uso nuevo de `get_admin_db` hay que justificarlo."
    )


def test_las_excepciones_declaradas_siguen_existiendo(alcance) -> None:
    """Una excepcion sobre un prefijo que ya no existe es ruido que confunde."""
    caminos = {camino for camino, _, _ in alcance}
    fantasmas = [
        prefijo
        for prefijo in {**SIN_ALCANCE_DE_EMPRESA, **CAMINOS_SIN_ALCANCE}
        if not any(c == prefijo or c.startswith(prefijo + "/") for c in caminos)
    ]
    assert not fantasmas, f"Excepciones que sobran: {fantasmas}"


def test_ninguna_excepcion_se_quedo_sin_motivo() -> None:
    todas = {**SIN_ALCANCE_DE_EMPRESA, **CAMINOS_SIN_ALCANCE}
    vacias = [p for p, motivo in todas.items() if not motivo.strip()]
    assert not vacias, f"Excepciones sin explicar: {vacias}"


def test_las_rutas_exceptuadas_no_leen_datos_de_empresa(alcance) -> None:
    """Que un prefijo este exceptuado no lo vuelve tierra de nadie.

    Si manana alguien cuelga `/catalog/mis-normas` —datos de una empresa— bajo
    un prefijo declarado global, la excepcion lo taparia. Aca se comprueba que
    ninguna ruta exceptuada pida ademas el tenant: si lo pide, es que si trabaja
    con datos acotados y no deberia estar en la lista.
    """
    from app.deps import get_tenant_id

    contradictorias = [
        f"{metodo} {camino}"
        for camino, metodo, deps in alcance
        if _exceptuada(camino) and get_tenant_id in deps and get_tenant_db not in deps
    ]
    assert not contradictorias, (
        f"Exceptuadas pero piden el tenant: {contradictorias}. "
        "O usan `get_tenant_db`, o no deberian estar exceptuadas."
    )
