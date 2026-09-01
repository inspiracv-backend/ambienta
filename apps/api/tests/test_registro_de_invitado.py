"""Registrar de forma permanente a un Cliente Invitado (#142, RF-03).

## Lo que el diseno decia y el modelo no permite

RBAC lo describia como `POST /admin/invitados/:userId/registrar-permanente`, o
sea cambiarle el rol a un usuario que ya existe. **Ese usuario no existe.**

Medido: cero filas en `users` con `user_type = 'guest'`. Un invitado vive en
`guest_credentials` —RUT, clave, vigencia— y es el segundo emisor de identidad
del sistema, con su propio tipo de token. Registrarlo no es promover a nadie:
es **crear a la persona** y llevarse consigo lo que ya hizo.

Y la credencial **no guarda ni nombre ni correo**, que es justo lo que `users`
exige. Salen de las solicitudes que abrio.

## Lo que estas pruebas protegen

1. **Que la persona no pierda su historial.** Sus solicitudes tienen que quedar
   ligadas a la cuenta nueva: si no, entra y no ve lo que ella misma abrio.
2. **Que deje de ser invitada.** Conservar la credencial dejaria dos caminos de
   entrada para la misma persona, uno con un token que ningun endpoint de
   negocio sabe leer.
3. **Que no se invente un usuario.** Sin nombre ni correo no hay a quien
   registrar, y rellenarlos con cualquier cosa crea una cuenta que no es de
   nadie.
4. **Que una empresa no registre al invitado de otra.**

Van contra la base real: `guest_credentials` no tiene modelo ORM y lo que
protege el aislamiento es RLS, no un `if`.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.organization import Department, User
from app.models.support import SupportTicket
from app.services import registro_de_invitado as svc

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


def _como(db: Session, tenant: uuid.UUID) -> None:
    db.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(tenant)}
    )


def _departamento(db: Session, tenant: uuid.UUID = EMPRESA_A) -> uuid.UUID:
    fila = db.scalars(
        select(Department).where(
            Department.tenant_id == tenant, Department.deleted_at.is_(None)
        )
    ).first()
    if fila is None:
        pytest.skip(f"El seed no dejo departamentos en {tenant}")
    return fila.id


def _credencial(
    db: Session, tenant: uuid.UUID = EMPRESA_A, *, revocada: bool = False
) -> uuid.UUID:
    """Una credencial de invitado. SQL crudo: no tiene modelo ORM."""
    rut = f"9{uuid.uuid4().int % 9999999}-K"
    fila = db.execute(
        text(
            "INSERT INTO guest_credentials "
            "  (tenant_id, rut, password_hash, valid_until, revoked_at) "
            "VALUES (:t, :r, 'x', :v, :rev) RETURNING id"
        ),
        {
            "t": str(tenant),
            "r": rut,
            "v": datetime.now(timezone.utc) + timedelta(days=30),
            "rev": datetime.now(timezone.utc) if revocada else None,
        },
    ).scalar_one()
    db.flush()
    return fila


def _ticket(
    db: Session,
    credencial_id: uuid.UUID,
    *,
    nombre: str | None = "Carla Rojas",
    correo: str | None = None,
    tenant: uuid.UUID = EMPRESA_A,
) -> SupportTicket:
    fila = SupportTicket(
        tenant_id=tenant,
        guest_credential_id=credencial_id,
        guest_name=nombre,
        guest_email=correo or f"{uuid.uuid4().hex[:10]}@externo.cl",
        category="other",
        subject="Necesito una copia de mi declaracion",
        description="Solicitud de prueba",
    )
    db.add(fila)
    db.flush()
    return fila


class TestRegistrarloDeVerdad:
    def test_se_crea_la_cuenta_con_los_datos_de_su_solicitud(
        self, db: Session
    ) -> None:
        """La credencial solo guarda el RUT; el nombre y el correo salen de ahi."""
        cred = _credencial(db)
        ticket = _ticket(db, cred, nombre="Carla Rojas")

        usuario, _ = svc.registrar_permanente(
            db, EMPRESA_A, cred, _departamento(db)
        )

        assert usuario.full_name == "Carla Rojas"
        assert usuario.email == ticket.guest_email
        assert usuario.tenant_id == EMPRESA_A

    def test_se_conserva_su_RUT(self, db: Session) -> None:
        """Es el unico dato de identidad que la credencial si tiene, y es el
        que la persona usa para entrar despues (RF-06)."""
        cred = _credencial(db)
        _ticket(db, cred)
        rut = db.execute(
            text("SELECT rut FROM guest_credentials WHERE id = :c"), {"c": str(cred)}
        ).scalar_one()

        usuario, _ = svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

        assert usuario.rut_tax_id == rut

    def test_la_cuenta_nace_INVITADA_y_no_activa(self, db: Session) -> None:
        """Existe, pero la persona todavia no entro por ella.

        Marcarla activa afirmaria un ingreso que no ocurrio, y ese dato se usa
        despues para saber quien esta usando el sistema.
        """
        cred = _credencial(db)
        _ticket(db, cred)

        usuario, _ = svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

        assert usuario.status == "invited"

    def test_sus_solicitudes_pasan_a_ser_SUYAS(self, db: Session) -> None:
        """Sin esto entra como usuaria y **no ve lo que ella misma abrio**.

        Su historial quedaria colgando de una credencial que ya no puede usar.
        """
        cred = _credencial(db)
        ticket = _ticket(db, cred)
        assert ticket.created_by_user_id is None

        usuario, efectos = svc.registrar_permanente(
            db, EMPRESA_A, cred, _departamento(db)
        )
        db.expire_all()

        assert db.get(SupportTicket, ticket.id).created_by_user_id == usuario.id
        assert any("solicitud" in e for e in efectos)

    def test_el_rastro_de_que_entro_como_invitada_se_conserva(
        self, db: Session
    ) -> None:
        """`guest_credential_id` no se borra: reescribiria la historia."""
        cred = _credencial(db)
        ticket = _ticket(db, cred)

        svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))
        db.expire_all()

        assert db.get(SupportTicket, ticket.id).guest_credential_id == cred

    def test_se_revoca_su_acceso_de_invitada(self, db: Session) -> None:
        """El sentido de "registro permanente" es dejar de ser invitado.

        Conservar la credencial dejaria dos caminos de entrada para la misma
        persona, uno con un token que ningun endpoint de negocio sabe leer.
        """
        cred = _credencial(db)
        _ticket(db, cred)

        _, efectos = svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

        revocada = db.execute(
            text("SELECT revoked_at FROM guest_credentials WHERE id = :c"),
            {"c": str(cred)},
        ).scalar_one()
        assert revocada is not None
        assert any("invitado" in e for e in efectos)

    def test_se_dicen_las_TRES_cosas_que_pasaron(self, db: Session) -> None:
        """Crear la cuenta, mover sus solicitudes y revocar el acceso.

        Si la revocacion ocurriera en silencio, la persona descubriria que
        perdio el enlace cuando intente usarlo.
        """
        cred = _credencial(db)
        _ticket(db, cred)

        _, efectos = svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

        assert len(efectos) == 3, efectos


class TestDeDondeSalenElNombreYElCorreo:
    def test_sin_solicitudes_y_sin_datos_se_RECHAZA(self, db: Session) -> None:
        """No hay a quien registrar.

        Rellenar el nombre con el RUT o dejar el correo vacio crearia una
        cuenta que no es de nadie — y `users.email` es la llave con la que
        despues se la busca.
        """
        cred = _credencial(db)

        with pytest.raises(svc.SinNombreNiCorreo):
            svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

    def test_una_solicitud_a_medias_no_alcanza(self, db: Session) -> None:
        """Se exige que la MISMA fila traiga los dos.

        Mezclar el nombre de un ticket con el correo de otro puede juntar a dos
        personas que usaron la misma credencial, y crear un usuario que no es
        ninguna de las dos.
        """
        cred = _credencial(db)
        _ticket(db, cred, nombre=None)

        with pytest.raises(svc.SinNombreNiCorreo):
            svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

    def test_se_pueden_indicar_a_mano(self, db: Session) -> None:
        """Quien administra corrige el dato.

        La persona pudo escribir mal su correo al abrir la solicitud, y
        obligarla a arrastrar ese error seria absurdo.
        """
        cred = _credencial(db)
        _ticket(db, cred, nombre="Nombre viejo", correo="viejo@externo.cl")

        usuario, _ = svc.registrar_permanente(
            db,
            EMPRESA_A,
            cred,
            _departamento(db),
            full_name="Carla Rojas Diaz",
            email="carla@externo.cl",
        )

        assert usuario.full_name == "Carla Rojas Diaz"
        assert usuario.email == "carla@externo.cl"

    def test_se_toma_la_solicitud_MAS_RECIENTE(self, db: Session) -> None:
        """Si corrigio su correo en una solicitud posterior, el bueno es el
        ultimo que dio."""
        cred = _credencial(db)
        _ticket(db, cred, nombre="Antiguo", correo="antiguo@externo.cl")
        db.flush()
        db.execute(
            text(
                "UPDATE support_tickets SET created_at = now() - interval '2 days' "
                "WHERE guest_credential_id = :c"
            ),
            {"c": str(cred)},
        )
        _ticket(db, cred, nombre="Reciente", correo="reciente@externo.cl")
        db.expire_all()

        usuario, _ = svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

        assert usuario.full_name == "Reciente"


class TestLoQueSeNiegaAHacer:
    def test_una_credencial_YA_REVOCADA_se_rechaza(self, db: Session) -> None:
        """Ya se registro, o alguien le quito el acceso.

        Registrarla otra vez crearia una segunda cuenta para la misma persona.
        """
        cred = _credencial(db, revocada=True)
        _ticket(db, cred)

        with pytest.raises(svc.CredencialYaRevocada):
            svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

    def test_un_correo_YA_REGISTRADO_se_rechaza(self, db: Session) -> None:
        """`users.email` es unico en **todo el sistema**, no por empresa.

        Se comprueba antes para responder algo legible en vez de un error de
        restriccion, que se lee como una falla del sistema.
        """
        existente = db.scalars(
            select(User).where(User.tenant_id == EMPRESA_A, User.deleted_at.is_(None))
        ).first()
        if existente is None:
            pytest.skip("El seed no dejo usuarios")
        cred = _credencial(db)
        _ticket(db, cred, correo=existente.email)

        with pytest.raises(svc.CorreoYaRegistrado):
            svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

    def test_registrar_DOS_VECES_no_crea_dos_cuentas(self, db: Session) -> None:
        """La segunda vez la credencial ya esta revocada.

        Es lo que convierte el doble clic en un rechazo claro en vez de en dos
        personas donde hay una.
        """
        cred = _credencial(db)
        _ticket(db, cred)
        svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))

        with pytest.raises(svc.CredencialYaRevocada):
            svc.registrar_permanente(db, EMPRESA_A, cred, _departamento(db))


class TestAislamientoEntreEmpresas:
    def test_la_empresa_B_no_puede_registrar_al_invitado_de_la_A(
        self, db: Session
    ) -> None:
        """La credencial se lee con la sesion del tenant: si RLS no la ve, para
        esa empresa no existe."""
        cred_de_a = _credencial(db, EMPRESA_A)
        _ticket(db, cred_de_a)
        db.flush()

        _como(db, EMPRESA_B)
        with pytest.raises(svc.InvitadoDesconocido):
            svc.registrar_permanente(
                db, EMPRESA_B, cred_de_a, _departamento(db, EMPRESA_B)
            )

    def test_una_credencial_INVENTADA_responde_lo_mismo(self, db: Session) -> None:
        """Respuestas distintas permitirian distinguir "no existe" de "existe
        pero es de otro", y con eso enumerar identificadores ajenos."""
        _como(db, EMPRESA_B)

        with pytest.raises(svc.InvitadoDesconocido):
            svc.registrar_permanente(
                db, EMPRESA_B, uuid.uuid4(), _departamento(db, EMPRESA_B)
            )

    def test_con_SU_PROPIO_invitado_la_empresa_B_si_puede(self, db: Session) -> None:
        """La otra mitad: sin esto, la guarda podria rechazar siempre y las dos
        pruebas de arriba pasarian igual."""
        _como(db, EMPRESA_B)
        cred = _credencial(db, EMPRESA_B)
        _ticket(db, cred, tenant=EMPRESA_B)

        usuario, _ = svc.registrar_permanente(
            db, EMPRESA_B, cred, _departamento(db, EMPRESA_B)
        )

        assert usuario.tenant_id == EMPRESA_B
