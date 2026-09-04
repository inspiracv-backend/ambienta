"""Cada endpoint del CRM, ejecutado de verdad al menos una vez.

## Por que existe este archivo

`test_crm.py` prueba el **servicio** y lo prueba bien: mover de columna, cerrar,
reabrir, exigir motivo, el aislamiento entre empresas. Lo que ninguna prueba
hacia era **llamar a los endpoints**, y ahi habia 26 llamadas escritas con la
firma equivocada:

| Lo que decia `crm.py` | Lo que aceptan las funciones |
|---|---|
| `obtener_o_404(crud, db, id, "Empresa")` | `recurso` es **solo por nombre** |
| `borrar_o_404(crud, db, id, "Empresa")` | idem |
| `crud.create(db, data, tenant_id)` | `obj_in` y `tenant_id` son **solo por nombre** |
| `crud.update(db, fila, data)` | `db_obj` y `obj_in` son **solo por nombre** |

Cada una levanta `TypeError` en la primera linea de su handler, o sea **HTTP
500**. Afectaba a todo lo direccionado por id: ver, editar y retirar empresas,
contactos, oportunidades, etapas y actividades, **mover una tarjeta del kanban**
y promover un trato a contrato.

Ninguna prueba fallaba, el `tsc` del frontend tampoco, y Swagger las documentaba
como si funcionaran. Es la misma familia que el resto del repositorio: algo que
se ve completo y no se ejecuto nunca.

La leccion no es "escribir bien las llamadas": es que **el modulo entero se
escribio sin ejecutar un solo endpoint**. Este archivo lo impide de la unica
forma que sirve — recorriendolos.

## Como estan escritas

Se llama a la funcion del router directo, con una sesion real sobre la base y
todo dentro de una transaccion que se revierte. No se usa `TestClient` porque
haria falta montar Clerk, y lo que se quiere comprobar es el handler, no la
autenticacion — de eso se encarga `test_tenants_scope.py`.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.organization import Tenant
from app.routers import crm as r
from app.schemas.crm import (
    CrmActivityCreate,
    CrmActivityUpdate,
    CrmCompanyCreate,
    CrmCompanyUpdate,
    CrmContactCreate,
    CrmContactUpdate,
    CrmDealCreate,
    CrmDealUpdate,
    CrmStageCreate,
    CrmStageUpdate,
    MoverDeEtapa,
)
from app.services import crm as svc

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


class RespuestaFalsa:
    """`recortar` escribe las cabeceras de paginacion en la respuesta."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        con = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(
            f"Sin base de datos disponible ({exc}). Esto NO comprueba que los "
            "endpoints del CRM se ejecuten: hace falta `docker compose up -d`."
        )
    trans = con.begin()
    s = Session(bind=con, join_transaction_mode="create_savepoint")
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        con.close()


@pytest.fixture
def tenant_id(db: Session) -> uuid.UUID:
    tenant = Tenant(
        country_id=1,
        tenant_type="company",
        rut_tax_id=f"95{uuid.uuid4().int % 1_000_000:06d}-4",
        legal_name="Empresa de prueba SpA",
    )
    db.add(tenant)
    db.flush()
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(tenant.id)}
    )
    svc.sembrar_etapas_por_defecto(db, tenant.id)
    return tenant.id


@pytest.fixture
def pagina():
    from app.routers._paginacion import Pagina

    return Pagina(skip=0, limit=100)


# ── Empresas ──────────────────────────────────────────────────────────────


class TestEmpresas:
    def test_el_ciclo_completo_se_ejecuta(self, db, tenant_id, pagina) -> None:
        """Crear, listar, ver, editar y retirar. Las cinco operaciones.

        Las cinco respondian 500 salvo el listado.
        """
        creada = r.create_company(
            CrmCompanyCreate(name="Constructora del Sur SpA", rut="76.543.210-K"),
            db=db,
            tenant_id=tenant_id,
        )
        assert creada.name == "Constructora del Sur SpA"

        listadas = r.list_companies(RespuestaFalsa(), pagina=pagina, db=db)
        assert creada.id in {c.id for c in listadas}

        vista = r.get_company(creada.id, db=db)
        assert vista.id == creada.id

        editada = r.update_company(
            creada.id, CrmCompanyUpdate(industry="Construcción"), db=db
        )
        assert editada.industry == "Construcción"

        r.delete_company(creada.id, db=db)
        assert creada.id not in {
            c.id for c in r.list_companies(RespuestaFalsa(), pagina=pagina, db=db)
        }

    def test_una_empresa_que_no_existe_da_404(self, db, tenant_id) -> None:
        """Y **404, no 500**, que es lo que daba: un `TypeError` en la primera
        linea del handler no distingue "no existe" de "el sistema esta roto"."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            r.get_company(uuid.uuid4(), db=db)

        assert exc.value.status_code == 404


# ── Contactos ─────────────────────────────────────────────────────────────


class TestContactos:
    def test_el_ciclo_completo_se_ejecuta(self, db, tenant_id, pagina) -> None:
        empresa = r.create_company(
            CrmCompanyCreate(name="Cliente"), db=db, tenant_id=tenant_id
        )

        creado = r.create_contact(
            CrmContactCreate(crm_company_id=empresa.id, full_name="Carla Miranda"),
            db=db,
            tenant_id=tenant_id,
        )
        assert r.get_contact(creado.id, db=db).full_name == "Carla Miranda"

        editado = r.update_contact(
            creado.id, CrmContactUpdate(role_title="Jefa de Medio Ambiente"), db=db
        )
        assert editado.role_title == "Jefa de Medio Ambiente"

        r.delete_contact(creado.id, db=db)
        assert creado.id not in {
            c.id for c in r.list_contacts(RespuestaFalsa(), pagina=pagina, db=db)
        }

    def test_un_contacto_de_una_empresa_ajena_se_rechaza(self, db, tenant_id) -> None:
        """`crm_company_id` viene del cuerpo y **las FK no pasan por RLS**."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            r.create_contact(
                CrmContactCreate(crm_company_id=uuid.uuid4(), full_name="Ajeno"),
                db=db,
                tenant_id=tenant_id,
            )

        assert exc.value.status_code == 422


# ── Oportunidades ─────────────────────────────────────────────────────────


class TestOportunidades:
    def test_el_ciclo_completo_se_ejecuta(self, db, tenant_id, pagina) -> None:
        empresa = r.create_company(
            CrmCompanyCreate(name="Cliente"), db=db, tenant_id=tenant_id
        )

        creado = r.create_deal(
            CrmDealCreate(crm_company_id=empresa.id, title="Implantación"),
            db=db,
            tenant_id=tenant_id,
        )
        assert r.get_deal(creado.id, db=db).title == "Implantación"

        editado = r.update_deal(creado.id, CrmDealUpdate(currency="USD"), db=db)
        assert editado.currency == "USD"

        r.delete_deal(creado.id, db=db)
        assert creado.id not in {
            d.id for d in r.list_deals(RespuestaFalsa(), pagina=pagina, db=db)
        }

    def test_MOVER_UNA_TARJETA_DEL_KANBAN_se_ejecuta(self, db, tenant_id) -> None:
        """La operacion que la unica pantalla del CRM llamaba, y respondia 500.

        Arrastrar una tarjeta era lo unico que el modulo dejaba hacer, y no
        funcionaba desde que se escribio.
        """
        empresa = r.create_company(
            CrmCompanyCreate(name="Cliente"), db=db, tenant_id=tenant_id
        )
        deal = r.create_deal(
            CrmDealCreate(crm_company_id=empresa.id, title="Implantación"),
            db=db,
            tenant_id=tenant_id,
        )
        ganada = next(e for e in svc.etapas_de(db, tenant_id) if e.kind == "won")

        resultado = r.mover_de_etapa(deal.id, MoverDeEtapa(stage_id=ganada.id), db=db)

        assert resultado.deal.stage_id == ganada.id
        assert resultado.deal.closed_at is not None
        assert resultado.efectos  # la pantalla los muestra

    def test_perder_sin_motivo_da_422_y_no_500(self, db, tenant_id) -> None:
        from fastapi import HTTPException

        empresa = r.create_company(
            CrmCompanyCreate(name="Cliente"), db=db, tenant_id=tenant_id
        )
        deal = r.create_deal(
            CrmDealCreate(crm_company_id=empresa.id, title="Implantación"),
            db=db,
            tenant_id=tenant_id,
        )
        perdida = next(e for e in svc.etapas_de(db, tenant_id) if e.kind == "lost")

        with pytest.raises(HTTPException) as exc:
            r.mover_de_etapa(deal.id, MoverDeEtapa(stage_id=perdida.id), db=db)

        assert exc.value.status_code == 422


# ── Actividades ───────────────────────────────────────────────────────────


class TestActividades:
    def test_el_ciclo_completo_se_ejecuta(self, db, tenant_id) -> None:
        empresa = r.create_company(
            CrmCompanyCreate(name="Cliente"), db=db, tenant_id=tenant_id
        )

        creada = r.create_activity(
            CrmActivityCreate(
                kind="call", subject="Llamada inicial", crm_company_id=empresa.id
            ),
            db=db,
            tenant_id=tenant_id,
        )
        assert r.get_activity(creada.id, db=db).subject == "Llamada inicial"

        editada = r.update_activity(
            creada.id, CrmActivityUpdate(body="Quedaron de mandar el alcance"), db=db
        )
        assert editada.body == "Quedaron de mandar el alcance"

        r.delete_activity(creada.id, db=db)
        assert creada.id not in {
            a.id
            # `limit` se pasa explicito: llamada directa, el valor por defecto
            # sigue siendo el objeto `Query` que FastAPI resolveria por su
            # cuenta en un request de verdad.
            for a in r.list_activities(
                company_id=empresa.id, limit=100, db=db, tenant_id=tenant_id
            )
        }

    def test_sin_padre_da_422_y_no_un_error_de_restriccion(self, db, tenant_id) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            r.create_activity(
                CrmActivityCreate(kind="note", subject="Huerfana"),
                db=db,
                tenant_id=tenant_id,
            )

        assert exc.value.status_code == 422


# ── Etapas ────────────────────────────────────────────────────────────────


class TestEtapas:
    def test_el_ciclo_completo_se_ejecuta(self, db, tenant_id) -> None:
        creada = r.create_stage(
            CrmStageCreate(code="calificado", name="Calificado", position=1),
            db=db,
            tenant_id=tenant_id,
        )
        assert r.get_stage(creada.id, db=db).name == "Calificado"

        editada = r.update_stage(creada.id, CrmStageUpdate(name="Ya calificado"), db=db)
        assert editada.name == "Ya calificado"

        r.delete_stage(creada.id, db=db)
        assert creada.id not in {e.id for e in r.list_stages(db=db, tenant_id=tenant_id)}


# ── El tablero ────────────────────────────────────────────────────────────


class TestElPipeline:
    def test_se_dibuja_con_las_etapas_de_la_empresa(self, db, tenant_id) -> None:
        empresa = r.create_company(
            CrmCompanyCreate(name="Cliente"), db=db, tenant_id=tenant_id
        )
        r.create_deal(
            CrmDealCreate(crm_company_id=empresa.id, title="Implantación", amount=1000),
            db=db,
            tenant_id=tenant_id,
        )

        tablero = r.ver_pipeline(db=db, tenant_id=tenant_id)

        assert len(tablero.columnas) == 6
        assert sum(c.total_deals for c in tablero.columnas) == 1


# ── La guarda de clase ────────────────────────────────────────────────────


class TestNadieVuelveAEscribirlasPosicionales:
    """Un barrido sobre el codigo, ademas de ejecutarlo.

    Las pruebas de arriba cazan el error donde pasan; esta lo caza en el
    endpoint que alguien agregue manana y se olvide de probar. Es barata y
    cubre exactamente la clase de defecto que costo 26 llamadas.
    """

    @pytest.mark.parametrize(
        "patron",
        [
            r'obtener_o_404\([^)]*, "',
            r'borrar_o_404\([^)]*, "',
            r'\.create\(db, [a-z_]+, [a-z_]+\)',
            r'\.update\(db, [a-z_]+, [a-z_]+\)',
        ],
    )
    def test_ningun_router_las_llama_por_posicion(self, patron: str) -> None:
        import re
        from pathlib import Path

        routers = Path(__file__).resolve().parents[1] / "app" / "routers"
        culpables = [
            f"{ruta.name}:{n}"
            for ruta in sorted(routers.glob("*.py"))
            for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(patron, linea)
        ]

        assert culpables == [], (
            f"Estas llamadas pasan por posicion un argumento que es solo por "
            f"nombre, asi que el endpoint responde 500 en su primera linea: "
            f"{culpables}"
        )
