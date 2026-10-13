"""El Admin Global mira y no toca el contenido de una empresa (RF-12).

## La regla estaba escrita en dos lugares y no la aplicaba ninguno

`CLAUDE.md` §4 la declara entre las no negociables — *"Admin Global NO puede
editar contenido de tenants"*— y el spec de `sistema-actores-roles-rbac` tiene su
escenario: *"un administrador global intenta modificar una obligación de una
empresa; el sistema lo rechaza, aunque pueda ver la empresa para
administrarla"*.

Medido el 10-sep: **no había ninguna guarda.** `users.tenant_id` es `NOT NULL`,
así que un `platform_admin` pertenece a una empresa y su sesión la declara — RLS
lo deja escribir ahí como a cualquiera. Lo único parecido era
`_es_admin_global()` en `routers/tenants.py`, y sirve para lo contrario: gatear
lo que **sólo** el Admin Global puede hacer.

## Por qué hacen falta estas pruebas y no basta la suite

La guarda vive detrás de `if not clerk_configured: return user`, y **el resto de
la suite corre en modo desarrollo**, donde no hay usuario del cual leer
`user_type`. Sin estas pruebas la guarda estaría escrita, en verde, y sin
ejecutarse nunca — el patrón que este repositorio ya sufrió con
`bcn.sincronizar()` y con `control_documental.py`.

## El límite es una constante, a propósito

`RAICES_DE_PLATAFORMA` son hoy `tenants` y `users`: dar de alta empresas y
administrar cuentas. Si mañana el Admin Global tiene que poder crear una planta
durante el onboarding, se agrega ahí y se entiende por qué — en vez de
descubrirlo repartido por los routers.
"""
from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.auth import CurrentUser  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.deps import (  # noqa: E402
    CODIGO_PLATAFORMA_NO_EDITA,
    declarar,
    get_current_user,
)
from app.main import app  # noqa: E402
from app.permisos_de_rutas import escritura_vedada_al_admin_global as vedada  # noqa: E402

EMPRESA = "a0000000-0000-0000-0000-000000000001"


class TestElLimite:
    """La función pura. Rápida, y fija dónde está la línea."""

    @pytest.mark.parametrize(
        "camino,metodo",
        [
            ("/api/v1/obligations/", "POST"),
            ("/api/v1/obligations/{id}", "PATCH"),
            ("/api/v1/documents/{id}", "DELETE"),
            ("/api/v1/compliance/article-compliance", "POST"),
            ("/api/v1/audits/", "POST"),
            ("/api/v1/iso14001/aspects", "POST"),
        ],
    )
    def test_el_contenido_de_una_empresa_le_esta_vedado(self, camino, metodo) -> None:
        assert vedada(camino, metodo) is True

    @pytest.mark.parametrize(
        "camino,metodo",
        [
            ("/api/v1/obligations/", "GET"),
            ("/api/v1/documents/{id}", "GET"),
            ("/api/v1/audits/{id}/informe", "GET"),
        ],
    )
    def test_leer_nunca_esta_vedado(self, camino, metodo) -> None:
        """**"Aunque pueda ver la empresa para administrarla"**, dice el spec.

        Un Admin Global que no pueda mirar no puede dar soporte, y el escenario
        lo declara explícito.
        """
        assert vedada(camino, metodo) is False

    @pytest.mark.parametrize(
        "camino,metodo",
        [
            ("/api/v1/tenants/", "POST"),
            ("/api/v1/tenants/{id}", "PATCH"),
            ("/api/v1/users/", "POST"),
            ("/api/v1/users/{id}", "PATCH"),
        ],
    )
    def test_su_propia_superficie_no(self, camino, metodo) -> None:
        """Dar de alta empresas y administrar cuentas **es** su trabajo."""
        assert vedada(camino, metodo) is False


@pytest.fixture
def como_admin_global():
    """Una sesión de Admin Global, con Clerk simulado como configurado.

    **`dependency_overrides` es global**, así que se limpia en el `finally`
    pase lo que pase: una prueba anterior de este repositorio dejó a un cliente
    actuando como el usuario de otra empresa por olvidarlo.
    """
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible ({exc}). Hace falta docker compose.")

    ajustes = get_settings()
    jwks_previo = ajustes.clerk_jwks_url

    with SessionLocal() as db:
        declarar(db, EMPRESA)
        fila = db.execute(
            text(
                "SELECT id, clerk_id, user_type FROM users "
                "WHERE deleted_at IS NULL ORDER BY created_at, id LIMIT 1"
            )
        ).first()
        if fila is None:  # pragma: no cover - seed sin usuarios
            pytest.skip("el seed no tiene usuarios")
        uid, clerk_previo, tipo_previo = fila
        clerk_id = clerk_previo or f"user_prueba_{uuid.uuid4().hex[:10]}"
        db.execute(
            text(
                "UPDATE users SET clerk_id = :c, user_type = 'platform_admin' "
                "WHERE id = :u"
            ),
            {"c": clerk_id, "u": uid},
        )
        db.commit()

    ajustes.clerk_jwks_url = "https://prueba.clerk/jwks"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=clerk_id, tenant_id=EMPRESA
    )
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        ajustes.clerk_jwks_url = jwks_previo
        with SessionLocal() as db:
            declarar(db, EMPRESA)
            db.execute(
                text(
                    "UPDATE users SET clerk_id = :c, user_type = :t WHERE id = :u"
                ),
                {"c": clerk_previo, "t": tipo_previo, "u": uid},
            )
            db.commit()


class TestPorLaApiDeVerdad:
    """La función pura puede estar bien y la guarda desconectada."""

    def test_escribir_una_obligacion_responde_403_con_su_codigo(
        self, como_admin_global
    ) -> None:
        r = como_admin_global.post(
            "/api/v1/obligations/",
            json={"title": "Inventada por la plataforma", "obligation_type": "reporte"},
        )
        assert r.status_code == 403, r.text
        detalle = r.json()["detail"]
        assert detalle["codigo"] == CODIGO_PLATAFORMA_NO_EDITA, (
            "responde 403 pero con el codigo de permiso insuficiente: la "
            "pantalla mandaria a pedir un permiso que no lo va a destrabar"
        )

    def test_leer_sigue_funcionando(self, como_admin_global) -> None:
        """Sin esto la guarda dejaría al Admin Global sin poder dar soporte."""
        r = como_admin_global.get("/api/v1/obligations/?limit=1")
        assert r.status_code == 200, r.text


def test_la_guarda_esta_conectada_a_la_ruta() -> None:
    """Barrido: que nadie la borre de `exigir_permiso_de_la_ruta` sin notarlo.

    Es el mismo criterio que la prueba que lee los Dockerfile por el flag de
    uvicorn: lo que se puede desconectar en una línea necesita algo que lo
    sostenga.
    """
    import pathlib

    fuente = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "deps.py"
    ).read_text(encoding="utf-8")
    assert "escritura_vedada_al_admin_global" in fuente, (
        "la guarda del Admin Global salio de deps.py: CLAUDE.md §4 y el spec de "
        "RBAC la exigen"
    )
