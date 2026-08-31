"""Que una empresa no pueda quedarse sin quien la administre (#141, RF-08).

Desactivar a una persona parece editar un campo, y es la operacion que puede
dejar a una empresa **sin camino de vuelta**: apagado quien administra
usuarios, no queda nadie que pueda volver a encenderlo. La salida es soporte
tocando la base a mano.

Hay dos caminos distintos hacia ese estado, y una sola regla no cubre los dos:

1. **Me apago a mi mismo.** Necesita saber quien pide la operacion.
2. **Apago al ultimo que puede administrar.** No necesita identidad.

La segunda importa mas de lo que parece: **sin Clerk configurado la API no
conoce la identidad** (`CurrentUser.user_id` llega vacio a proposito). Una
guarda que dependiera solo de quien pide estaria apagada en desarrollo sin que
nada lo dijera — y quien la probara ahi concluiria que funciona.

Las pruebas van contra la base real porque lo que decide es
`permisos_efectivos`, que cruza roles y excepciones individuales. Con una
sesion simulada se estaria comprobando el mock.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.organization import Department, Role, User, UserRole
from app.services import usuarios as svc

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
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


def _rol(db: Session, code: str) -> Role:
    fila = db.scalars(
        select(Role).where(Role.tenant_id == EMPRESA_A, Role.code == code)
    ).first()
    if fila is None:
        pytest.skip(f"El seed no dejo el rol {code}")
    return fila


def _departamento(db: Session) -> uuid.UUID:
    """`ck_users_interno_con_departamento` (migracion 13) lo exige.

    Un usuario `internal` sin departamento no se puede insertar: RF-11 pide que
    toda persona de la empresa pertenezca a una parte de ella.
    """
    fila = db.scalars(
        select(Department).where(
            Department.tenant_id == EMPRESA_A, Department.deleted_at.is_(None)
        )
    ).first()
    if fila is None:
        pytest.skip("El seed no dejo departamentos en esta empresa")
    return fila.id


def _persona(
    db: Session,
    nombre: str,
    *,
    rol: str | None = None,
    status: str = "active",
    clerk_id: str | None = None,
) -> User:
    fila = User(
        tenant_id=EMPRESA_A,
        department_id=_departamento(db),
        email=f"{uuid.uuid4().hex[:12]}@prueba.cl",
        full_name=nombre,
        user_type="internal",
        status=status,
        clerk_id=clerk_id,
    )
    db.add(fila)
    db.flush()
    if rol:
        db.add(UserRole(user_id=fila.id, role_id=_rol(db, rol).id, tenant_id=EMPRESA_A))
        db.flush()
    return fila


def _apagar_a_los_demas(db: Session, salvo: User) -> None:
    """Deja a `salvo` como la unica persona activa de la empresa.

    El seed trae usuarios propios, asi que sin esto las afirmaciones sobre "el
    ultimo que administra" dependerian de a quien sembro alguien mas — que es
    exactamente el tipo de prueba que se rompe sola meses despues.
    """
    db.execute(
        text(
            "UPDATE users SET status = 'disabled' "
            "WHERE tenant_id = :t AND id <> :id AND deleted_at IS NULL"
        ),
        {"t": str(EMPRESA_A), "id": str(salvo.id)},
    )
    db.expire_all()


class TestNadieSeDesactivaASiMismo:
    def test_la_propia_cuenta_se_rechaza(self, db: Session) -> None:
        yo = _persona(db, "Quien administra", rol="admin_empresa", clerk_id="user_yo")
        _persona(db, "Otro que administra", rol="admin_empresa")

        with pytest.raises(svc.NoPuedeDesactivarseSolo):
            svc.validar_desactivacion(db, yo, EMPRESA_A, clerk_id="user_yo")

    def test_desactivar_a_OTRO_si_se_permite(self, db: Session) -> None:
        """Y esto es lo que impide que la guarda rechace todo.

        Una regla que dice que no siempre no protege: bloquea el modulo.
        """
        yo = _persona(db, "Quien administra", rol="admin_empresa", clerk_id="user_yo")
        otro = _persona(db, "Otro que administra", rol="admin_empresa")
        assert yo.id != otro.id

        svc.validar_desactivacion(db, otro, EMPRESA_A, clerk_id="user_yo")

    def test_se_compara_por_CLERK_ID_y_no_por_nombre(self, db: Session) -> None:
        """Lo unico que trae el token es el `sub` de Clerk."""
        otro = _persona(db, "Otro", rol="admin_empresa", clerk_id="user_otro")
        _persona(db, "Mas gente", rol="admin_empresa")

        # Con la identidad de otra persona, no es "uno mismo".
        svc.validar_desactivacion(db, otro, EMPRESA_A, clerk_id="user_yo")

    def test_SIN_identidad_esta_regla_no_puede_sostenerse(self, db: Session) -> None:
        """La afirmacion incomoda, escrita a proposito.

        Sin Clerk configurado `CurrentUser.user_id` llega vacio, y entonces no
        hay forma de saber si alguien se esta apagando a si mismo. Esta prueba
        deja constancia de que en ese caso la guarda **no** es la que protege,
        para que nadie mire la de arriba y concluya que el sistema esta cubierto
        en desarrollo. La que sigue en pie es la del ultimo administrador.
        """
        yo = _persona(db, "Quien administra", rol="admin_empresa", clerk_id="user_yo")
        _persona(db, "Otro que administra", rol="admin_empresa")

        assert svc.es_uno_mismo(db, yo, "") is False
        assert svc.es_uno_mismo(db, yo, None) is False
        # Y no lanza: sin identidad, este camino deja pasar.
        svc.validar_desactivacion(db, yo, EMPRESA_A, clerk_id="")


class TestElUltimoQueAdministra:
    def test_apagar_al_unico_administrador_se_rechaza(self, db: Session) -> None:
        """El estado del que no se vuelve.

        Nadie queda para reactivar a nadie, y la unica salida es tocar la base.
        """
        solo = _persona(db, "La unica", rol="admin_empresa", clerk_id="user_sola")
        _apagar_a_los_demas(db, solo)

        with pytest.raises(svc.UltimoQueAdministra):
            # Sin identidad: es justo el caso donde la otra guarda no protege.
            svc.validar_desactivacion(db, solo, EMPRESA_A, clerk_id="")

    def test_con_DOS_administradores_activos_se_permite(self, db: Session) -> None:
        primero = _persona(db, "Primera", rol="admin_empresa")
        segundo = _persona(db, "Segunda", rol="admin_empresa")
        db.execute(
            text(
                "UPDATE users SET status = 'disabled' WHERE tenant_id = :t "
                "AND id NOT IN (:a, :b) AND deleted_at IS NULL"
            ),
            {"t": str(EMPRESA_A), "a": str(primero.id), "b": str(segundo.id)},
        )
        db.expire_all()

        svc.validar_desactivacion(db, primero, EMPRESA_A, clerk_id="")

    def test_un_administrador_DESACTIVADO_no_cuenta_como_respaldo(
        self, db: Session
    ) -> None:
        """La trampa: existe otro admin, pero apagado.

        Contar las filas en vez de las personas activas dejaria pasar la
        desactivacion, y la empresa quedaria con dos administradores y ninguno
        que pueda entrar.
        """
        activo = _persona(db, "Activa", rol="admin_empresa")
        _persona(db, "Apagada", rol="admin_empresa", status="disabled")
        db.execute(
            text(
                "UPDATE users SET status = 'disabled' WHERE tenant_id = :t "
                "AND id <> :id AND deleted_at IS NULL AND full_name <> 'Apagada'"
            ),
            {"t": str(EMPRESA_A), "id": str(activo.id)},
        )
        db.expire_all()

        with pytest.raises(svc.UltimoQueAdministra):
            svc.validar_desactivacion(db, activo, EMPRESA_A, clerk_id="")

    def test_quien_NO_administra_se_puede_desactivar_aunque_sea_el_ultimo(
        self, db: Session
    ) -> None:
        """La regla es sobre el permiso, no sobre ser el ultimo alguien.

        Sin esto, la ultima persona de la empresa seria indesactivable aunque
        no pudiera administrar nada — y el modulo quedaria bloqueado por una
        guarda que protege algo que no estaba en riesgo.
        """
        operador = _persona(db, "Quien opera", rol="operador")
        admin = _persona(db, "Quien administra", rol="admin_empresa")
        assert admin is not None

        svc.validar_desactivacion(db, operador, EMPRESA_A, clerk_id="")

    def test_sin_NINGUN_administrador_activo_igual_se_puede_desactivar_a_otro(
        self, db: Session
    ) -> None:
        """La regla es "soy el ultimo que administra", no "no queda ninguno".

        Esta prueba nacio de una mutacion que **sobrevivio**: quitar el atajo
        que deja pasar a quien no tiene el permiso no rompia nada. Sin ese
        atajo, la regla pasa a ser "no hay otro administrador activo", y
        entonces en una empresa que ya se quedo sin administradores —por
        cualquier via— dejaria de poder desactivarse a **nadie**, ni siquiera a
        un operador que no tiene nada que ver con el bloqueo.

        Es la diferencia entre una guarda que protege y una que se traba: el
        dano ya ocurrio, y negarse a tocar al resto de la nomina no lo repara.
        """
        operador = _persona(db, "Quien solo opera", rol="operador")
        _apagar_a_los_demas(db, operador)

        assert svc.tiene_el_permiso(db, operador) is False, (
            "el operador tiene user.write; la prueba no mide lo que dice"
        )
        # No queda un solo administrador activo en la empresa...
        assert svc.ultimo_que_administra(db, operador, EMPRESA_A) is False, (
            "se trato como 'el ultimo administrador' a quien no administra"
        )
        # ...y aun asi, desactivar a quien no administra se permite.
        svc.validar_desactivacion(db, operador, EMPRESA_A, clerk_id="")

    def test_el_criterio_es_el_PERMISO_y_no_el_nombre_del_rol(
        self, db: Session
    ) -> None:
        """Los roles son configurables por empresa: el nombre no garantiza nada.

        A quien se llama `admin_empresa` se le niega `user.write` con una
        excepcion individual —la denegacion le gana al rol— y deja de contar
        como respaldo. Si el criterio fuera el nombre del rol, este caso
        pasaria y la empresa quedaria sin nadie que pueda administrar.
        """
        activo = _persona(db, "Administra de verdad", rol="admin_empresa")
        de_nombre = _persona(db, "Administra solo de nombre", rol="admin_empresa")
        _apagar_a_los_demas(db, activo)
        db.execute(
            text("UPDATE users SET status = 'active' WHERE id = :id"),
            {"id": str(de_nombre.id)},
        )
        # Se le quita el permiso a quien conserva el nombre del rol.
        # `tenant_id` es obligatorio: `user_permissions` tiene RLS forzado, y
        # sin esa columna la fila la rechaza la politica, no la restriccion.
        db.execute(
            text(
                "INSERT INTO user_permissions (user_id, permission_id, tenant_id, granted) "
                "SELECT :u, id, :t, false FROM permissions WHERE code = 'user.write' "
                "ON CONFLICT (user_id, permission_id) DO UPDATE SET granted = false"
            ),
            {"u": str(de_nombre.id), "t": str(EMPRESA_A)},
        )
        db.expire_all()

        assert svc.tiene_el_permiso(db, de_nombre) is False, (
            "la denegacion individual no le gano al rol"
        )
        with pytest.raises(svc.UltimoQueAdministra):
            svc.validar_desactivacion(db, activo, EMPRESA_A, clerk_id="")


class TestQueCuentaComoDesactivar:
    @pytest.mark.parametrize(
        "anterior,nuevo,esperado",
        [
            ("active", "disabled", True),
            ("active", "blocked", True),
            ("invited", "disabled", True),
            # Ya estaba apagado: guardar lo mismo no apaga a nadie.
            ("disabled", "disabled", False),
            ("blocked", "disabled", False),
            # Encender no es apagar.
            ("disabled", "active", False),
            # `invited` no es un estado apagado: es alguien que aun no acepta.
            ("active", "invited", False),
            # Sin cambio de estado en el cuerpo.
            ("active", None, False),
        ],
    )
    def test_se_mira_la_TRANSICION_no_el_estado_destino(
        self, anterior: str, nuevo: str | None, esperado: bool
    ) -> None:
        """Rechazar por el estado destino romperia ediciones inocuas.

        Cambiarle el departamento a alguien ya desactivado manda `disabled` otra
        vez; si eso contara como desactivar, la operacion respondaria 409 sin
        que nadie este apagando nada.
        """
        assert svc.desactiva(anterior, nuevo) is esperado
