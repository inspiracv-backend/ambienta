"""El catalogo de permisos es el vocabulario unico del RBAC (#217, RF-12).

## Lo que estas pruebas impiden que vuelva a pasar

Medido el 1-sep-2026, la pantalla y la API **no compartian ni una clave**:

    packages/shared -> CATALOGO_PERMISOS   13 claves escritas a mano
    base de datos   -> permissions.code    39 codigos que la guarda verifica
    en comun                                0

Y lo unico que habia evitado el dano es que la pantalla nunca llegaba a
guardar. Un Admin Empresa podia marcar trece casillas que el servidor no
consulta nunca, y quedarse creyendo que restringio a alguien que seguia
pudiendo todo. Eso no falla: responde bien y miente.

La decision (#217, opcion 3) fue que **manda la base**, y que el texto legible
salga de `permissions.description` en vez de una segunda lista. Estas pruebas
son lo que sostiene esa decision:

- `TestElCatalogoEsLaBase` — lo que se sirve es exactamente lo que hay en la
  tabla, sin filtrar ni renombrar.
- `TestNoNaceUnaSegundaLista` — si a alguien le faltara texto para pintar la
  pantalla, volveria a escribirlo en el frontend. Por eso ninguna fila puede
  quedarse sin `module` ni sin `description`.
- `TestSoloSeAceptaElVocabularioReal` — la API rechaza las claves viejas del
  frontend. Es la prueba que se pone roja si el vocabulario muerto vuelve.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")

#: Tres claves de la lista que la pantalla mantenia a mano. Ninguna existe en
#: `permissions`, y por eso estan aca: son el canario de que el vocabulario
#: muerto no volvio por la ventana.
CLAVES_MUERTAS = ["matriz_legal.evaluar", "obligaciones.crear", "usuarios.gestionar_permisos"]


@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import SessionLocal
    from app.main import app

    monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)
    original = SessionLocal.kw.get("bind")
    motor = create_engine(URL)
    SessionLocal.configure(bind=motor)
    try:
        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original)
        motor.dispose()


@pytest.fixture
def catalogo_en_la_base():
    """Lo que la tabla `permissions` dice, leido por fuera de la API."""
    motor = create_engine(URL)
    try:
        with motor.connect() as c:
            filas = c.execute(
                text("SELECT code, module, description FROM permissions ORDER BY module, code")
            ).all()
    finally:
        motor.dispose()
    if not filas:
        pytest.skip("la base no tiene el catalogo de permisos sembrado")
    return filas


@pytest.fixture
def un_usuario():
    """El id de alguien de la empresa A, para probar las escrituras."""
    motor = create_engine(URL)
    try:
        with motor.connect() as c:
            # Dos trampas juntas: `SET` no admite parametros vinculados (hay que
            # usar `set_config`), y el nombre del ajuste es **`ambienta.tenant_id`**
            # y no `app.tenant_id` — asi lo lee `current_tenant_id()`, que es de
            # quien depende la politica RLS. Con el nombre equivocado la consulta
            # no falla: devuelve cero filas, y el `skip` que habia aca lo tapaba.
            c.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, false)"),
                {"t": str(EMPRESA_A)},
            )
            fila = c.execute(
                text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
            ).scalar()
    finally:
        motor.dispose()
    assert fila is not None, (
        "La empresa A no tiene usuarios visibles. Si la base esta sembrada, "
        "revisa el nombre del ajuste de sesion antes que la siembra: con uno "
        "equivocado RLS devuelve cero filas sin error."
    )
    return fila


CABECERA = {"X-Tenant-Id": str(EMPRESA_A)}


class TestElCatalogoEsLaBase:
    """Lo que se sirve tiene que ser la tabla, no una version curada de ella."""

    def test_devuelve_todas_las_filas(self, cliente, catalogo_en_la_base) -> None:
        r = cliente.get("/api/v1/permissions/", headers=CABECERA)
        assert r.status_code == 200
        assert len(r.json()) == len(catalogo_en_la_base)

    def test_los_codigos_son_LOS_MISMOS(self, cliente, catalogo_en_la_base) -> None:
        """Ni uno de menos ni uno renombrado.

        Un filtro bienintencionado —"estos permisos no se muestran"— deja
        casillas invisibles que el rol sigue concediendo, y entonces la
        pantalla vuelve a decir algo distinto de lo que hace la API.
        """
        servidos = {p["codigo"] for p in cliente.get("/api/v1/permissions/", headers=CABECERA).json()}
        en_la_base = {f.code for f in catalogo_en_la_base}
        assert servidos == en_la_base

    def test_el_texto_sale_de_la_misma_fila(self, cliente, catalogo_en_la_base) -> None:
        servidos = {p["codigo"]: p for p in cliente.get("/api/v1/permissions/", headers=CABECERA).json()}
        for fila in catalogo_en_la_base:
            assert servidos[fila.code]["modulo"] == fila.module
            assert servidos[fila.code]["descripcion"] == fila.description

    def test_viene_ordenado_por_modulo_y_codigo(self, cliente) -> None:
        """La pantalla agrupa por modulo: si llega desordenado, tiene que
        reordenar, y ahi empieza a tener criterio propio."""
        servidos = cliente.get("/api/v1/permissions/", headers=CABECERA).json()
        pares = [(p["modulo"], p["codigo"]) for p in servidos]
        assert pares == sorted(pares)

    def test_se_lee_SIN_role_manage(self, cliente) -> None:
        """Leer el catalogo no puede exigir permiso de administrar permisos.

        Seria circular: la pantalla que administra permisos necesita el
        catalogo para poder dibujarse. Lo que importa —escribir la excepcion—
        sigue exigiendo `role.manage` en `/users/{id}/permissions/{codigo}`.
        """
        assert cliente.get("/api/v1/permissions/", headers=CABECERA).status_code == 200


class TestNoNaceUnaSegundaLista:
    """Toda fila tiene que traer con que pintarse.

    Este es el mecanismo por el que nacio el problema: si el catalogo no
    alcanza para dibujar la pantalla, alguien escribe los nombres bonitos en el
    frontend, y a los dos meses hay dos listas otra vez.
    """

    def test_ninguna_fila_llega_sin_modulo_ni_descripcion(self, cliente) -> None:
        servidos = cliente.get("/api/v1/permissions/", headers=CABECERA).json()
        sin_texto = [
            p["codigo"] for p in servidos if not p["modulo"].strip() or not p["descripcion"].strip()
        ]
        assert sin_texto == [], (
            f"Estos permisos no traen con que pintarse: {sin_texto}. "
            "Sin texto, la pantalla tendria que inventarlo, y ahi vuelve a "
            "nacer la segunda lista que #217 elimino."
        )

    def test_hay_mas_de_un_modulo(self, cliente) -> None:
        """Si todo cayera en un modulo, la pantalla dejaria de poder agrupar y
        volveria a inventar su propio agrupamiento."""
        servidos = cliente.get("/api/v1/permissions/", headers=CABECERA).json()
        assert len({p["modulo"] for p in servidos}) > 1


class TestSoloSeAceptaElVocabularioReal:
    """La API rechaza las claves que la pantalla mantenia a mano."""

    @pytest.mark.parametrize("clave", CLAVES_MUERTAS)
    def test_una_clave_del_frontend_viejo_no_existe(self, cliente, clave) -> None:
        servidos = {p["codigo"] for p in cliente.get("/api/v1/permissions/", headers=CABECERA).json()}
        assert clave not in servidos

    @pytest.mark.parametrize("clave", CLAVES_MUERTAS)
    def test_escribirla_responde_404_y_no_la_guarda_igual(
        self, cliente, un_usuario, clave
    ) -> None:
        """**La que importa.**

        Guardar un permiso inventado no falla al escribirlo: falla al usarlo,
        meses despues, cuando alguien se pregunta por que la restriccion no
        tuvo efecto. Tiene que rebotar aca.
        """
        r = cliente.put(
            f"/api/v1/users/{un_usuario}/permissions/{clave}",
            headers=CABECERA,
            json={"codigo": clave, "granted": True, "reason": "prueba de vocabulario"},
        )
        assert r.status_code == 404
        assert clave in r.json()["detail"]

    def test_un_codigo_del_catalogo_SI_es_aceptado(self, cliente, un_usuario) -> None:
        """El contrapeso: si todo rebotara, la prueba de arriba pasaria por el
        motivo equivocado y la pantalla no podria guardar nada."""
        servidos = cliente.get("/api/v1/permissions/", headers=CABECERA).json()
        codigo = servidos[0]["codigo"]

        r = cliente.put(
            f"/api/v1/users/{un_usuario}/permissions/{codigo}",
            headers=CABECERA,
            json={"codigo": codigo, "granted": True, "reason": "prueba de vocabulario"},
        )
        try:
            assert r.status_code == 200
            assert codigo in {p["codigo"] for p in r.json()["permisos"]}
        finally:
            cliente.delete(
                f"/api/v1/users/{un_usuario}/permissions/{codigo}", headers=CABECERA
            )


class TestElCommitNoSeLlevaElTenant:
    """El viaje completo de una excepcion individual, ida y vuelta.

    ## El defecto que esto impide

    `_declarar` usa `SET LOCAL` y `set_config(..., true)`: los dos mueren con la
    transaccion. Estos dos endpoints hacen `db.commit()` y **despues** releen
    para devolver el conjunto entero, asi que la relectura corria sin tenant
    declarado y RLS le devolvia cero filas.

    Medido antes del arreglo: la fila de `user_permissions` quedaba **escrita**
    y el endpoint respondia **404 "User not found"**. No es un fallo, es peor:
    quien llama concluye que no paso nada, y paso. La pantalla habria mostrado
    un error mientras el permiso ya estaba concedido.

    Es la misma familia que `db.refresh()` despues de `db.commit()`: el commit
    se lleva puesto el contexto de la sesion.
    """

    def _codigo(self, cliente) -> str:
        return cliente.get("/api/v1/permissions/", headers=CABECERA).json()[0]["codigo"]

    def test_conceder_responde_200_y_no_404(self, cliente, un_usuario) -> None:
        codigo = self._codigo(cliente)
        try:
            r = cliente.put(
                f"/api/v1/users/{un_usuario}/permissions/{codigo}",
                headers=CABECERA,
                json={"codigo": codigo, "granted": True, "reason": "vuelta completa"},
            )
            assert r.status_code == 200, (
                f"Respondio {r.status_code}. Si es 404 'User not found', falta "
                "`volver_a_declarar(db)` despues del commit: la escritura entro "
                "igual y la respuesta miente."
            )
        finally:
            cliente.delete(
                f"/api/v1/users/{un_usuario}/permissions/{codigo}", headers=CABECERA
            )

    def test_lo_concedido_se_ve_en_la_siguiente_lectura(self, cliente, un_usuario) -> None:
        codigo = self._codigo(cliente)
        try:
            cliente.put(
                f"/api/v1/users/{un_usuario}/permissions/{codigo}",
                headers=CABECERA,
                json={"codigo": codigo, "granted": True, "reason": "vuelta completa"},
            )
            visto = cliente.get(
                f"/api/v1/users/{un_usuario}/permissions", headers=CABECERA
            ).json()
            assert codigo in {p["codigo"] for p in visto["permisos"]}
        finally:
            cliente.delete(
                f"/api/v1/users/{un_usuario}/permissions/{codigo}", headers=CABECERA
            )

    def test_denegar_deja_el_codigo_en_denegados(self, cliente, un_usuario) -> None:
        """Denegar no es lo mismo que no conceder, y tiene que verse aparte."""
        codigo = self._codigo(cliente)
        try:
            r = cliente.put(
                f"/api/v1/users/{un_usuario}/permissions/{codigo}",
                headers=CABECERA,
                json={"codigo": codigo, "granted": False, "reason": "vuelta completa"},
            )
            assert r.status_code == 200
            assert codigo in r.json()["denegados"]
        finally:
            cliente.delete(
                f"/api/v1/users/{un_usuario}/permissions/{codigo}", headers=CABECERA
            )

    def test_quitar_la_excepcion_responde_200_y_la_quita(self, cliente, un_usuario) -> None:
        codigo = self._codigo(cliente)
        cliente.put(
            f"/api/v1/users/{un_usuario}/permissions/{codigo}",
            headers=CABECERA,
            json={"codigo": codigo, "granted": False, "reason": "vuelta completa"},
        )

        r = cliente.delete(
            f"/api/v1/users/{un_usuario}/permissions/{codigo}", headers=CABECERA
        )

        assert r.status_code == 200, (
            f"Respondio {r.status_code}. Mismo defecto que en el PUT: la fila se "
            "borra y la respuesta dice que no se encontro."
        )
        assert codigo not in r.json()["denegados"]
