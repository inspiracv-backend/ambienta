"""El registro de actividades exige su permiso, respeta el alcance y va en orden.

## Lo que se midio el 21-sep

`GET /system/audit-log` **no pedia ningun permiso**. `permisos_de_rutas.py`
declaraba `"audit-log": "audit_log.read"` en `PERMISO_POR_ACCION`, pero la raiz
`system` figura entre las exentas y `permiso_requerido` salia antes de llegar a
esa linea. Una guarda escrita y sin efecto: el patron de `bcn.sincronizar()`.

Y el registro trae el antes y el despues de cada cambio de la empresa, de todas
las plantas. El spec de RBAC dice que un rol acotado a una planta no ve datos de
otra, y que el permiso se verifica en el servidor; las dos cosas fallaban aca.

Ademas no tenia orden: con el tope de la pagina se veian siempre las filas mas
viejas, que es lo contrario de lo que se busca en un registro.

## Por que hay un barrido

El defecto no era la falta de una linea sino **una linea que no alcanzaba**.
`test_ninguna_regla_queda_sin_efecto` recorre las rutas reales y exige que cada
entrada de las tablas de permisos cambie de verdad lo que pide alguna ruta.

**Las pruebas por HTTP simulan Clerk**, como `test_admin_global_no_edita.py`:
la guarda vive detras de `if not clerk_configured`, y el resto de la suite
corre sin Clerk. Crean personas `[QA]` propias y las borran al terminar.
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
from sqlalchemy import select, text  # noqa: E402

from app.auth import CurrentUser  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.deps import CODIGO_SIN_PERMISO, declarar, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.organization import Department, Facility, Role, User, UserRole  # noqa: E402
from app.permisos_de_rutas import (  # noqa: E402
    PERMISO_POR_ACCION,
    PERMISO_POR_RUTA,
    permiso_requerido,
)
from app.routers.system import CODIGO_REGISTRO_ACOTADO  # noqa: E402

EMPRESA = "a0000000-0000-0000-0000-000000000001"
RUTA = "/api/v1/system/audit-log"


# ── La regla, sin base ───────────────────────────────────────────────────────


def test_el_registro_pide_su_permiso() -> None:
    assert permiso_requerido(RUTA, "GET") == "audit_log.read"


def test_la_salud_del_esquema_sigue_sin_guarda() -> None:
    """Lo exento de `system` sigue exento: un monitor la consulta sin sesion."""
    assert permiso_requerido("/api/v1/system/health", "GET") is None


def test_evaluar_un_aspecto_pide_escribir_el_aspecto() -> None:
    """No el permiso de la matriz legal, que es lo que pedia por terminar en
    `evaluate`: una excepcion individual caia en el permiso equivocado."""
    assert (
        permiso_requerido("/api/v1/iso14001/aspects/{aspect_id}/evaluate", "POST")
        == "environmental_aspect.write"
    )
    # Y evaluar un articulo sigue siendo lo de siempre.
    assert (
        permiso_requerido("/api/v1/compliance/article-compliance/{ac_id}/evaluate", "POST")
        == "legal_matrix.article.evaluate"
    )


def _rutas() -> list[tuple[str, str]]:
    return [
        (r.path, m)
        for r in app.routes
        if getattr(r, "path", "").startswith("/api/v1/")
        for m in (getattr(r, "methods", None) or ())
    ]


def test_el_barrido_ve_rutas() -> None:
    assert len(_rutas()) > 150, "la aplicacion no expone rutas: el barrido no mira nada"


def test_ninguna_regla_queda_sin_efecto() -> None:
    """Cada entrada de las tablas tiene que decidir el permiso de alguna ruta.

    Es la forma del defecto de hoy: `"audit-log": "audit_log.read"` existia y
    ninguna ruta lo recibia. Una regla que no alcanza a nadie no falla: se lee
    como si protegiera.
    """
    rutas = _rutas()
    muertas: list[str] = []
    for segmento, permiso in PERMISO_POR_ACCION.items():
        if not any(
            c.rstrip("/").split("/")[-1] == segmento and permiso_requerido(c, m) == permiso
            for c, m in rutas
        ):
            muertas.append(f"PERMISO_POR_ACCION[{segmento!r}] = {permiso!r}")
    for (raiz, segmento), permiso in PERMISO_POR_RUTA.items():
        if not any(
            c.startswith(f"/api/v1/{raiz}/")
            and c.rstrip("/").split("/")[-1] == segmento
            and permiso_requerido(c, m) == permiso
            for c, m in rutas
        ):
            muertas.append(f"PERMISO_POR_RUTA[{(raiz, segmento)!r}] = {permiso!r}")
    assert muertas == [], "Reglas que no llegan a ninguna ruta:\n  " + "\n  ".join(muertas)


# ── Por la API, sin Clerk: el orden ─────────────────────────────────────────


def _hay_base() -> None:
    import psycopg

    try:
        psycopg.connect(os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")).close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Sin base de datos disponible ({exc}).")


def test_va_del_mas_reciente_al_mas_antiguo() -> None:
    _hay_base()
    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    get_settings.cache_clear()
    with TestClient(app) as c:
        r = c.get(f"{RUTA}?limit=20", headers={"X-Tenant-Id": EMPRESA})
    assert r.status_code == 200, r.text
    filas = r.json()
    if len(filas) < 2:  # pragma: no cover
        pytest.skip("el registro de la empresa tiene menos de dos filas")
    claves = [(f["occurred_at"], f["id"]) for f in filas]
    assert claves == sorted(claves, reverse=True)


# ── Por la API, con Clerk simulado: permiso y alcance ───────────────────────


@pytest.fixture
def como():
    """Devuelve una funcion que arma un cliente como una persona `[QA]` con ese
    rol, acotada o no a una planta. Todo lo que crea se borra al final."""
    _hay_base()
    ajustes = get_settings()
    jwks_previo = ajustes.clerk_jwks_url
    creadas: list[uuid.UUID] = []
    clientes: list[TestClient] = []

    def armar(rol: str, *, acotada: bool = False) -> TestClient:
        clerk_id = f"user_qa_{uuid.uuid4().hex[:10]}"
        with SessionLocal() as db:
            declarar(db, uuid.UUID(EMPRESA))
            depto = db.scalar(select(Department.id).where(Department.deleted_at.is_(None)))
            planta = db.scalar(select(Facility.id).where(Facility.deleted_at.is_(None)))
            role_id = db.scalar(select(Role.id).where(Role.code == rol))
            if depto is None or planta is None or role_id is None:  # pragma: no cover
                pytest.skip("al seed le faltan departamento, planta o el rol")
            persona = User(
                tenant_id=uuid.UUID(EMPRESA),
                department_id=depto,
                email=f"qa-{uuid.uuid4().hex[:10]}@prueba.cl",
                full_name="[QA] Registro de actividades",
                user_type="internal",
                status="active",
                clerk_id=clerk_id,
            )
            db.add(persona)
            db.flush()
            db.add(
                UserRole(
                    user_id=persona.id,
                    role_id=role_id,
                    tenant_id=uuid.UUID(EMPRESA),
                    facility_id=planta if acotada else None,
                )
            )
            db.flush()
            db.execute(
                text("UPDATE user_roles SET valid_from = now() - interval '1 day' WHERE user_id = :u"),
                {"u": str(persona.id)},
            )
            creadas.append(persona.id)
            db.commit()
        ajustes.clerk_jwks_url = "https://prueba.clerk/jwks"
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id=clerk_id, tenant_id=EMPRESA
        )
        c = TestClient(app)
        clientes.append(c)
        return c

    try:
        yield armar
    finally:
        # `dependency_overrides` es global: se limpia pase lo que pase.
        app.dependency_overrides.pop(get_current_user, None)
        ajustes.clerk_jwks_url = jwks_previo
        for c in clientes:
            c.close()
        with SessionLocal() as db:
            declarar(db, uuid.UUID(EMPRESA))
            for uid in creadas:
                db.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": str(uid)})
                db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(uid)})
            db.commit()


def test_sin_el_permiso_responde_403(como) -> None:
    """`operador` no tiene `audit_log.read`. Hasta hoy leia el registro entero."""
    r = como("operador").get(f"{RUTA}?limit=1")

    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == CODIGO_SIN_PERMISO
    assert r.json()["detail"]["permiso"] == "audit_log.read"


def test_con_el_permiso_y_sin_acotar_lo_lee(como) -> None:
    """La otra mitad: una guarda que niega a todos tambien pasaria la de arriba."""
    r = como("admin_empresa").get(f"{RUTA}?limit=1")

    assert r.status_code == 200, r.text


def test_acotada_a_una_planta_no_lee_el_registro_completo(como) -> None:
    """`servicio_lectura` tiene el permiso; acotada a una planta, igual no.

    El registro no dice de que planta es cada cambio, asi que no se puede
    recortar: mostrarlo entero le daria lo de las otras plantas."""
    r = como("servicio_lectura", acotada=True).get(f"{RUTA}?limit=1")

    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == CODIGO_REGISTRO_ACOTADO
