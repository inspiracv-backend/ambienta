"""Acotar un rol a una planta **acota de verdad** (RF-12).

## Lo que estaba pasando, medido el 10-sep-2026

`user_roles.facility_id` y `department_id` existen desde el principio.
`services/permisos.py::alcance_del_usuario()` los resuelve. `GET /me` los
devuelve en `instalaciones`, `departamentos` y `acotado`, con un docstring que
explica que un alcance vacío significa «sin acotar» y no «ninguno».

**Y esa función tenía un solo llamador: `/me`, que lo informaba.** Ninguna
consulta filtraba por él:

| `GET /compliance/article-compliance` con el rol acotado a una planta | filas |
|---|---|
| de su planta | 92 |
| **de las otras dos** | **172** |

No era una fuga entre empresas —RLS es la única barrera entre tenants y sigue
firme— pero el acotamiento *dentro* de la empresa era decorativo, y eso se
promete en una venta y se contesta en una auditoría de accesos.

**La primera versión de este archivo fijaba el hueco** y decía que debía fallar
el día que alguien lo implementara. Ese día fue el mismo: se decidió que el
alcance entra en la 1.0 y `app/alcance.py` lo aplica en `CRUDBase._visibles()`,
junto al filtro de borrado lógico y por el mismo motivo.

## Lo que estas pruebas fijan

Las tres reglas que hacen que el filtro sea correcto y no sólo estricto:

1. **Sin acotamiento no se filtra nada** — vacío es «toda la empresa».
2. **Una fila sin instalación se ve igual** — no es «de otra planta».
3. **Escribir fuera del alcance se rechaza** — filtrar sólo la lectura dejaría
   filas que existen, cuentan en los totales de la planta ajena y son
   invisibles para quien las escribió.
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
def plantas():
    with SessionLocal() as db:
        declarar(db, EMPRESA)
        filas = db.execute(
            text("SELECT id FROM facilities WHERE deleted_at IS NULL ORDER BY name")
        ).scalars().all()
    if len(filas) < 2:  # pragma: no cover - seed de una sola planta
        pytest.skip("hace falta mas de una planta para medir el acotamiento")
    return filas


def _obligacion(db, facility_id) -> None:
    """Una obligacion `[QA]` en esa planta, o de toda la empresa con `None`.

    **Las pruebas siembran lo que miden.** La primera version confiaba en los
    datos de `sembrar_demo` —evaluaciones en varias plantas, obligaciones sin
    planta— y en CI, que parte de una base recien creada, fallaban tres: la
    premisa no se cumplia y el mensaje acusaba al filtro.
    """
    db.execute(
        text(
            "INSERT INTO obligations (tenant_id, code, title, status, due_at, facility_id) "
            "VALUES (:t, :c, '[QA] alcance', 'open', now() + interval '30 days', :f)"
        ),
        {"t": EMPRESA, "c": f"PRB-{os.urandom(4).hex().upper()}", "f": facility_id},
    )


@pytest.fixture
def sesion_acotada(plantas):
    """Una sesión de base con el alcance puesto a mano, sin pasar por Clerk.

    **Se inyecta el contexto en `db.info` en vez de simular un login.** El
    alcance se resuelve del `clerk_id` que deja `get_tenant_db`, y montar un
    Clerk falso para medir un filtro de SQL sería probar otra cosa.
    """
    from app.alcance import ALCANCE

    with SessionLocal() as db:
        declarar(db, EMPRESA)
        db.info[ALCANCE] = frozenset({plantas[0]})
        yield db, plantas[0], plantas[1]


class TestLaLecturaSeAcota:
    def test_no_devuelve_filas_de_otra_planta(self, sesion_acotada) -> None:
        """El caso que motiva todo: antes devolvía 172 filas de las otras dos."""
        from app.crud.compliance import crud_article_compliance

        db, suya, _otra = sesion_acotada
        filas = crud_article_compliance.get_multi(db, skip=0, limit=500)
        por_planta = Counter(f.facility_id for f in filas)

        ajenas = {p: n for p, n in por_planta.items() if p is not None and p != suya}
        assert not ajenas, (
            f"devolvio filas de plantas fuera del alcance: {ajenas}. El rol esta "
            "acotado a una sola instalacion."
        )

    def test_una_fila_sin_planta_sigue_visible(self, sesion_acotada) -> None:
        """**Regla 2.** `facility_id IS NULL` no es «de otra planta».

        36 de las 41 obligaciones del seed no tienen instalación: son de la
        empresa entera. Esconderlas le ocultaría a un encargado de planta las
        obligaciones corporativas que también le aplican — y ese error se vería
        como «no tengo obligaciones», que es lo contrario de la verdad.
        """
        from app.crud.obligations import crud_obligation

        db, _suya, _otra = sesion_acotada
        _obligacion(db, None)
        filas = crud_obligation.get_multi(db, skip=0, limit=500)
        assert any(f.facility_id is None for f in filas), (
            "las obligaciones de la empresa entera desaparecieron para un rol "
            "acotado a una planta"
        )

    def test_pedir_por_id_una_fila_ajena_no_la_devuelve(self, sesion_acotada) -> None:
        """Filtrar el listado y no el `get` dejaría la puerta abierta al id."""
        from app.crud.compliance import crud_article_compliance

        db, _suya, otra = sesion_acotada
        ajena = db.execute(
            text(
                "SELECT id FROM article_compliance "
                "WHERE facility_id = :f AND deleted_at IS NULL LIMIT 1"
            ),
            {"f": otra},
        ).scalar()
        if ajena is None:  # pragma: no cover - seed sin evaluaciones en esa planta
            pytest.skip("no hay evaluaciones en la otra planta")

        assert crud_article_compliance.get(db, ajena) is None


class TestSinAcotamientoNoSeFiltra:
    def test_un_rol_sin_planta_ve_todo(self, plantas) -> None:
        """**Regla 1.** Vacío significa «toda la empresa», no «ninguna».

        Confundirlo dejaría a los administradores viendo una pantalla en blanco
        — es lo que el docstring de `/me` ya advertía sobre el campo `acotado`.
        """
        from app.alcance import ALCANCE
        from app.crud.obligations import crud_obligation

        with SessionLocal() as db:
            declarar(db, EMPRESA)
            _obligacion(db, plantas[0])
            _obligacion(db, plantas[1])
            db.info[ALCANCE] = None  # resuelto y sin acotamiento
            filas = crud_obligation.get_multi(db, skip=0, limit=500)
            plantas_vistas = {f.facility_id for f in filas if f.facility_id}
            db.rollback()

        assert len(plantas_vistas) > 1, (
            "un rol SIN acotar dejo de ver todas las plantas: el filtro se esta "
            "aplicando cuando no corresponde"
        )

    def test_sin_sesion_identificada_tampoco(self, cliente, plantas) -> None:
        """El modo `X-Tenant-Id` no tiene usuario del cual sacar roles.

        Es el mismo criterio que el resto de las guardas, y lo que permite
        trabajar en local sin Clerk.
        """
        # Por HTTP la fila tiene que estar confirmada: se siembra, se mide y se
        # borra, marcada `[QA]` por si la limpieza no llegara a correr.
        with SessionLocal() as db:
            declarar(db, EMPRESA)
            _obligacion(db, plantas[0])
            _obligacion(db, plantas[1])
            db.commit()
        try:
            filas = cliente.get("/api/v1/obligations/?limit=500").json()
            plantas_vistas = {f["facility_id"] for f in filas if f.get("facility_id")}
            assert len(plantas_vistas) > 1
        finally:
            with SessionLocal() as db:
                declarar(db, EMPRESA)
                db.execute(text("DELETE FROM obligations WHERE title = '[QA] alcance'"))
                db.commit()


class TestLaEscrituraTambien:
    """**Regla 3.** Filtrar sólo la lectura sería peor que no filtrar.

    Una fila creada fuera del alcance existe, cuenta en los totales de la planta
    ajena y es invisible para quien la escribió. Es la lección de la guarda que
    sólo miraba el `DELETE` de las etapas del CRM.
    """

    def test_no_se_puede_crear_en_una_planta_ajena(self, sesion_acotada) -> None:
        from fastapi import HTTPException

        from app.crud.iso14001 import crud_regulated_equipment
        from app.schemas.iso14001 import RegulatedEquipmentCreate

        db, _suya, otra = sesion_acotada
        with pytest.raises(HTTPException) as e:
            crud_regulated_equipment.create(
                db,
                obj_in=RegulatedEquipmentCreate(
                    facility_id=otra,
                    name="Caldera fuera de alcance",
                    equipment_type="caldera",
                ),
                tenant_id=EMPRESA,
            )
        assert e.value.status_code == 403
        db.rollback()

    def test_en_la_propia_si(self, sesion_acotada) -> None:
        """El control positivo: sin esto, la prueba anterior pasaría con el
        alta rota por cualquier motivo."""
        from app.crud.iso14001 import crud_regulated_equipment
        from app.schemas.iso14001 import RegulatedEquipmentCreate

        db, suya, _otra = sesion_acotada
        creado = crud_regulated_equipment.create(
            db,
            obj_in=RegulatedEquipmentCreate(
                facility_id=suya,
                name="[QA] Caldera dentro de alcance",
                equipment_type="caldera",
            ),
            tenant_id=EMPRESA,
        )
        assert creado.id is not None
        db.rollback()

    def test_sin_planta_se_permite(self, sesion_acotada) -> None:
        """Regla 2 aplicada a la escritura: `None` nunca está fuera."""
        from app.alcance import fuera_de_alcance
        from app.models.iso14001 import RegulatedEquipment

        db, _suya, _otra = sesion_acotada
        assert fuera_de_alcance(db, RegulatedEquipment, None) is False

    def test_un_patch_no_puede_mover_la_fila_a_otra_planta(
        self, sesion_acotada
    ) -> None:
        """La puerta trasera: guardar el alta y dejar libre el `PATCH`.

        **Se usa un departamento y no un equipo**, y eso lo decidió medirlo: de
        todos los esquemas de la API, **`DepartmentUpdate` es el único que
        expone `facility_id`**. Un equipo regulado no se puede mover de planta
        por `PATCH` en absoluto, así que la primera versión de esta prueba
        fallaba con «DID NOT RAISE» acusando a la guarda cuando el problema era
        el caso elegido.

        La puerta es de una sola hoja, y por eso conviene que la guarda sea
        genérica: vive en `CRUDBase.update`, así que el día que alguien agregue
        `facility_id` a otro `Update` ya está cubierto sin acordarse.
        """
        from fastapi import HTTPException

        from app.crud.organization import crud_department
        from app.schemas.organization import DepartmentCreate, DepartmentUpdate

        db, suya, otra = sesion_acotada
        propio = crud_department.create(
            db,
            obj_in=DepartmentCreate(
                facility_id=suya, code="QA-ALC", name="[QA] Depto a mover"
            ),
            tenant_id=EMPRESA,
        )
        with pytest.raises(HTTPException) as e:
            crud_department.update(
                db, db_obj=propio, obj_in=DepartmentUpdate(facility_id=otra)
            )
        assert e.value.status_code == 403
        db.rollback()

    def test_un_solo_esquema_deja_mover_de_planta(self) -> None:
        """El barrido que explica por qué la prueba de arriba usa un departamento.

        Si mañana aparece un segundo, la guarda ya lo cubre —vive en
        `CRUDBase.update`, no en cada router— pero conviene enterarse: mover una
        fila entre plantas es la operación que más se parece a saltarse el
        acotamiento.

        **Dos correcciones que costó llegar acá, las dos mías:**

        1. Un `grep` de `facility_id` cerca de `class ...Update` dio **tres**, y
           dos eran **menciones en el docstring**, no campos. Un medidor que
           cuenta prosa como código es de los que mienten hacia arriba.
        2. La primera versión del barrido miraba `dir(schemas)`, que devuelve lo
           que ya está importado y no lo que existe: encontraba uno de tres por
           el motivo equivocado. Ahora importa cada módulo del paquete.
        """
        import importlib
        import pathlib
        import pkgutil

        from app import schemas

        con_facility = set()
        raiz = pathlib.Path(schemas.__file__).parent
        for info in pkgutil.iter_modules([str(raiz)]):
            modulo = importlib.import_module(f"app.schemas.{info.name}")
            for nombre in dir(modulo):
                clase = getattr(modulo, nombre)
                campos = getattr(clase, "model_fields", None)
                if campos and nombre.endswith("Update") and "facility_id" in campos:
                    con_facility.add(nombre)

        assert con_facility == {"DepartmentUpdate"}, (
            f"cambio que se puede mover de planta por PATCH: {sorted(con_facility)}. "
            "La guarda de `CRUDBase.update` ya lo cubre; esta prueba solo avisa."
        )
