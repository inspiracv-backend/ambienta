"""Acotar un rol a una planta **no acota nada**, y estas pruebas lo fijan.

## Qué se midió, el 10-sep-2026

`user_roles.facility_id` y `department_id` existen desde el principio.
`services/permisos.py::alcance_del_usuario()` los resuelve. `GET /me` los
devuelve en `instalaciones`, `departamentos` y `acotado`, con un docstring que
explica que un alcance vacío significa «sin acotar» y no «ninguno».

**Y `alcance_del_usuario()` tiene un solo llamador: `/me`.** Ninguna consulta de
negocio filtra por instalación. Medido por la API con el rol acotado a una
planta:

| `GET /compliance/article-compliance` | filas |
|---|---|
| de su planta | 92 |
| **de las otras dos** | **172** |

## Por qué estas pruebas afirman lo que está mal

Son del mismo tipo que las del catálogo RETC incompleto: **fijan el estado real
y deben fallar el día que alguien lo arregle**. El motivo es que el hueco no se
ve — el sistema *dice* que el rol está acotado, la pantalla lo muestra, y lo que
no ocurre es el filtrado. Sin algo que lo sostenga por escrito, la próxima
persona que lea `/me` va a concluir que el acotamiento funciona.

**No es una fuga entre empresas.** RLS sigue siendo la única barrera entre
tenants y sigue firme: esto es acotamiento *dentro* de una empresa. El daño está
en lo que se puede prometer —«el encargado de Calama sólo ve Calama»— y en una
auditoría de accesos.

Es el requisito «El alcance de un rol puede acotarse» del cambio
`sistema-actores-roles-rbac`, y por eso ese cambio no se puede archivar.
"""
from __future__ import annotations

import os
from collections import Counter

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.deps import declarar  # noqa: E402
from app.main import app  # noqa: E402
from app.services.permisos import alcance_del_usuario  # noqa: E402

EMPRESA = "a0000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def cliente():
    import psycopg

    try:
        psycopg.connect(
            os.environ["DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
        ).close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible ({exc}). Hace falta docker compose.")

    for var in ("CLERK_JWKS_URL", "CLERK_ISSUER"):
        os.environ.pop(var, None)
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as c:
        c.headers["X-Tenant-Id"] = EMPRESA
        yield c


@pytest.fixture
def acotado_a_una_planta(cliente):
    """Acota los roles de una persona a la primera planta, y lo deshace.

    Se restaura el valor **por rol** y no a `NULL`: poner NULL a todos sería
    perder el acotamiento que el seed pudiera traer, y esta prueba no debe
    cambiar el estado del sistema.
    """
    with SessionLocal() as db:
        declarar(db, EMPRESA)
        plantas = db.execute(
            text(
                "SELECT id FROM facilities WHERE deleted_at IS NULL ORDER BY name"
            )
        ).scalars().all()
        if len(plantas) < 2:  # pragma: no cover - seed de una sola planta
            pytest.skip("hace falta mas de una planta para medir el acotamiento")

        uid = db.execute(
            text(
                "SELECT id FROM users WHERE deleted_at IS NULL "
                "ORDER BY created_at, id LIMIT 1"
            )
        ).scalar()
        previo = db.execute(
            text("SELECT role_id, facility_id FROM user_roles WHERE user_id = :u"),
            {"u": uid},
        ).all()

        db.execute(
            text("UPDATE user_roles SET facility_id = :f WHERE user_id = :u"),
            {"f": plantas[0], "u": uid},
        )
        db.commit()

    yield {"usuario": uid, "suya": plantas[0], "otras": plantas[1:]}

    with SessionLocal() as db:
        declarar(db, EMPRESA)
        for role_id, facility_id in previo:
            db.execute(
                text(
                    "UPDATE user_roles SET facility_id = :f "
                    "WHERE user_id = :u AND role_id = :r"
                ),
                {"f": facility_id, "u": uid, "r": role_id},
            )
        db.commit()


class TestElAlcanceSeDeclaraYSeInforma:
    """Esta mitad sí funciona, y es lo que hace creíble la otra."""

    def test_el_alcance_se_resuelve(self, acotado_a_una_planta) -> None:
        with SessionLocal() as db:
            declarar(db, EMPRESA)
            instalaciones, _ = alcance_del_usuario(db, acotado_a_una_planta["usuario"])
        assert acotado_a_una_planta["suya"] in instalaciones
        for otra in acotado_a_una_planta["otras"]:
            assert otra not in instalaciones

    def test_solo_lo_llama_identidad(self) -> None:
        """**Un llamador, y es el que informa.** Es todo el defecto.

        Se barre el código en vez de confiar en la memoria: el día que aparezca
        un segundo llamador —que sería el que filtra— esta prueba falla y hay
        que venir a leer este archivo.
        """
        import pathlib

        raiz = pathlib.Path(__file__).resolve().parents[1] / "app"
        llamadores = {
            ruta.relative_to(raiz).as_posix()
            for ruta in raiz.rglob("*.py")
            if "alcance_del_usuario(" in ruta.read_text(encoding="utf-8")
            and ruta.name != "permisos.py"
        }
        assert llamadores == {"routers/identidad.py"}, (
            f"cambio quien usa el alcance: {sorted(llamadores)}. Si alguien lo "
            "empezo a APLICAR, este archivo entero quedo obsoleto y hay que "
            "borrarlo — junto con la entrada de CLAUDE.md que lo documenta."
        )


class TestYNoSeAplica:
    """**Estas pruebas deben fallar el día que se implemente el filtrado.**

    Afirman el estado real, no el deseado. Son del mismo tipo que las del
    catálogo RETC incompleto.
    """

    def test_la_api_devuelve_filas_de_plantas_fuera_del_alcance(
        self, cliente, acotado_a_una_planta
    ) -> None:
        filas = cliente.get(
            "/api/v1/compliance/article-compliance?limit=500"
        ).json()
        por_planta = Counter(str(f.get("facility_id")) for f in filas)

        fuera = sum(
            n
            for planta, n in por_planta.items()
            if planta != str(acotado_a_una_planta["suya"])
            and planta not in ("None", "")
        )
        assert fuera > 0, (
            "La API dejo de devolver filas de plantas fuera del alcance del "
            "rol. Si eso es porque **se implemento el filtrado**, felicidades: "
            "borra este archivo, la entrada de CLAUDE.md sobre el alcance, y "
            "marca el requisito 'El alcance de un rol puede acotarse' del "
            "cambio `sistema-actores-roles-rbac`, que hoy lo bloquea. Si es "
            "porque el seed cambio, arregla la prueba."
        )

    def test_ninguna_consulta_de_negocio_menciona_el_alcance(self) -> None:
        """El barrido que explica por qué: no hay filtro que quitar.

        Si mañana alguien filtra por instalación, lo hará nombrando el alcance
        en algún servicio o router de negocio. Hoy no lo nombra ninguno.
        """
        import pathlib

        raiz = pathlib.Path(__file__).resolve().parents[1] / "app"
        sospechosos = {
            ruta.relative_to(raiz).as_posix()
            for carpeta in ("routers", "services", "crud")
            for ruta in (raiz / carpeta).rglob("*.py")
            if "alcance_del_usuario" in ruta.read_text(encoding="utf-8")
        }
        assert sospechosos == {"routers/identidad.py", "services/permisos.py"}, (
            f"el alcance empezo a usarse en {sorted(sospechosos)} — revisar si "
            "ya se aplica y este archivo sobra"
        )
