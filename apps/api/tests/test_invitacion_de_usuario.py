"""Invitar por correo a alguien de la empresa (#139, RF-03).

## Lo que se prueba y lo que no

La llamada a Clerk va **simulada**. No es por comodidad: una prueba que sale a
la red falla cuando el proveedor tiene mantenimiento, y ademas mandaria correos
de verdad cada vez que alguien corre la suite.

Lo que si se comprueba es **que se le manda lo correcto**, que es donde vive el
defecto que importa.

## El detalle que decide si la persona puede trabajar

`public_metadata.tenant_id`. El claim de empresa sale de ahi: el JWT Template lo
inyecta, y sin el la persona acepta la invitacion, se crea la cuenta, entra... y
recibe `403 sesion_sin_empresa` **en todo el sistema**.

Clerk copia `public_metadata` al usuario al aceptar, asi que la invitacion es el
unico momento en que se puede dejar puesto sin entrar a su consola a mano — que
es justo lo que CLAUDE.md describe como paso manual.

Es un fallo que **no se ve al invitar**: el correo llega, el enlace funciona, la
cuenta se crea. Se descubre despues, cuando la persona no puede hacer nada y
nadie sabe por que.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.organization import Department, User
from app.services import invitacion_de_usuario as svc
from app.services.clave_local import ClerkNoDisponible, ErrorDeClaveLocal

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EMPRESA_B = uuid.UUID("a0000000-0000-0000-0000-000000000002")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    s = Session(bind=conexion)
    s.execute(text("SET LOCAL ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(EMPRESA_A)}
    )
    try:
        yield s
    finally:
        s.rollback()
        s.close()
        conexion.close()
        engine.dispose()


@pytest.fixture
def clerk(monkeypatch):
    """Registra lo que se le manda a Clerk, sin salir a la red.

    Se parchea el nombre **en el modulo que lo usa**, no en `clave_local`: la
    importacion `from .clave_local import _clerk` ya copio la referencia, asi
    que parchear el origen no cambiaria nada — y la prueba pasaria creyendo que
    simulo algo.
    """
    llamadas: list[tuple[str, str, dict]] = []

    def falso(metodo, ruta, cuerpo=None):
        llamadas.append((metodo, ruta, cuerpo or {}))
        return {"id": "inv_prueba", "status": "pending"}

    monkeypatch.setattr(svc, "_clerk", falso)
    return llamadas


def _persona(
    db: Session, *, status: str = "invited", tenant: uuid.UUID = EMPRESA_A
) -> User:
    depto = db.scalars(
        select(Department).where(
            Department.tenant_id == tenant, Department.deleted_at.is_(None)
        )
    ).first()
    if depto is None:
        pytest.skip(f"El seed no dejo departamentos en {tenant}")
    fila = User(
        tenant_id=tenant,
        department_id=depto.id,
        email=f"{uuid.uuid4().hex[:12]}@prueba.cl",
        full_name="Persona invitada",
        user_type="internal",
        status=status,
    )
    db.add(fila)
    db.flush()
    return fila


class TestLoQueSeLeMandaAClerk:
    def test_la_invitacion_LLEVA_el_tenant_id(self, db: Session, clerk) -> None:
        """La afirmacion central de #139.

        Sin esto la persona acepta, entra y recibe 403 en todo el sistema. Y no
        se ve al invitar: el correo llega y el enlace funciona.
        """
        usuario = _persona(db)

        svc.invitar(usuario)

        _, _, cuerpo = clerk[0]
        assert cuerpo["public_metadata"]["tenant_id"] == str(EMPRESA_A)

    def test_se_invita_al_correo_de_esa_persona(self, db: Session, clerk) -> None:
        usuario = _persona(db)

        svc.invitar(usuario)

        assert clerk[0][2]["email_address"] == usuario.email

    def test_va_al_endpoint_de_invitaciones_de_Clerk(
        self, db: Session, clerk
    ) -> None:
        svc.invitar(_persona(db))

        metodo, ruta, _ = clerk[0]
        assert (metodo, ruta) == ("POST", "/invitations")

    def test_se_pide_que_Clerk_mande_el_correo(self, db: Session, clerk) -> None:
        """Sin `notify`, Clerk crea la invitacion y **no avisa a nadie**: la
        persona nunca se entera y quien invito cree que si."""
        svc.invitar(_persona(db))

        assert clerk[0][2]["notify"] is True


class TestAQuienNoSeInvita:
    def test_a_alguien_ACTIVO_no(self, db: Session, clerk) -> None:
        """Ya le funciona su cuenta.

        Mandarle un enlace que no necesita siembra la duda de si su acceso dejo
        de servir.
        """
        usuario = _persona(db, status="active")

        with pytest.raises(svc.NoCorrespondeInvitar):
            svc.invitar(usuario)

        assert clerk == [], "se llamo a Clerk igual"

    @pytest.mark.parametrize("estado", ["blocked", "disabled"])
    def test_a_alguien_APAGADO_tampoco(
        self, db: Session, clerk, estado: str
    ) -> None:
        """Invitarlo seria devolverle el acceso por la puerta de atras, sin
        pasar por la decision de reactivarlo."""
        usuario = _persona(db, status=estado)

        with pytest.raises(svc.NoCorrespondeInvitar):
            svc.invitar(usuario)

        assert clerk == []

    def test_a_quien_SI_corresponde_se_invita(self, db: Session, clerk) -> None:
        """La otra mitad: sin esto la guarda podria rechazar siempre y las de
        arriba pasarian igual."""
        svc.invitar(_persona(db, status="invited"))

        assert len(clerk) == 1


class TestCuandoClerkResponde:
    def test_una_invitacion_DUPLICADA_se_distingue(
        self, db: Session, monkeypatch
    ) -> None:
        """Se arregla distinto: no hay nada que corregir, ya esta invitada.

        Confundirla con un error de datos haria que quien administra buscara
        que corrigio mal.
        """
        def duplicada(metodo, ruta, cuerpo=None):
            raise ErrorDeClaveLocal("duplicate invitation for this email address")

        monkeypatch.setattr(svc, "_clerk", duplicada)

        with pytest.raises(svc.YaInvitado):
            svc.invitar(_persona(db))

    def test_otro_rechazo_de_Clerk_llega_como_error_de_invitacion(
        self, db: Session, monkeypatch
    ) -> None:
        def rechaza(metodo, ruta, cuerpo=None):
            raise ErrorDeClaveLocal("el correo no tiene un formato valido")

        monkeypatch.setattr(svc, "_clerk", rechaza)

        with pytest.raises(svc.ErrorDeInvitacion) as e:
            svc.invitar(_persona(db))
        assert not isinstance(e.value, svc.YaInvitado)

    def test_sin_CLERK_SECRET_KEY_sube_tal_cual(
        self, db: Session, monkeypatch
    ) -> None:
        """No es un problema del dato que se mando.

        El router lo traduce a 503; tratarlo como error de la peticion diria que
        quien invita hizo algo mal.
        """
        def sin_clave(metodo, ruta, cuerpo=None):
            raise ClerkNoDisponible("Falta CLERK_SECRET_KEY")

        monkeypatch.setattr(svc, "_clerk", sin_clave)

        with pytest.raises(ClerkNoDisponible):
            svc.invitar(_persona(db))


class TestAislamientoEntreEmpresas:
    def test_no_se_puede_invitar_a_alguien_de_otra_empresa(
        self, db: Session, clerk
    ) -> None:
        """Se busca con la sesion del tenant: si RLS no lo ve, no existe.

        Sin esto, una empresa podria mandarle una invitacion a la gente de otra
        —con **su propio** `tenant_id` en los metadatos— y quedarse con esa
        persona dentro.
        """
        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"),
            {"t": str(EMPRESA_B)},
        )
        de_b = _persona(db, tenant=EMPRESA_B)
        db.flush()
        ajeno = de_b.id

        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"),
            {"t": str(EMPRESA_A)},
        )
        db.expire_all()

        with pytest.raises(svc.NoCorrespondeInvitar):
            svc.invitar_por_id(db, ajeno)

        assert clerk == [], "se le mando una invitacion a alguien de otra empresa"

    def test_alguien_INVENTADO_responde_lo_mismo(self, db: Session, clerk) -> None:
        with pytest.raises(svc.NoCorrespondeInvitar):
            svc.invitar_por_id(db, uuid.uuid4())

    def test_con_alguien_PROPIO_si_funciona(self, db: Session, clerk) -> None:
        usuario = _persona(db)

        devuelto, _ = svc.invitar_por_id(db, usuario.id)

        assert devuelto.id == usuario.id
        assert len(clerk) == 1
