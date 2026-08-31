"""Asignar roles, que es lo que decide que puede hacer cada persona (#140).

## Lo que faltaba

`user_roles` es **lo unico** que `permisos_efectivos` lee para saber que puede
hacer alguien. Y no existia ni una sola ruta con `role` en su camino: la tabla
se llenaba en la migracion `09_roles_por_codigo.sql` y despues solo se podia
tocar con SQL a mano. El RBAC funcionaba y **no se podia administrar**.

## Lo que estas pruebas protegen

1. **Que asignar un rol cambie de verdad lo que la persona puede hacer.** Es la
   unica afirmacion que importa: escribir la fila y que `permisos_efectivos`
   siga diciendo lo mismo seria un endpoint decorativo.
2. **Que retirar un rol lo venza y no lo borre.** La clave primaria es
   `(user_id, role_id)`: si se borrara, se perderia hasta el ultimo periodo.
3. **Que un rol vencido no conceda nada.** Es la diferencia entre "fue
   encargado" y "es encargado".
4. **Que no se pueda dejar a la empresa sin quien administre usuarios**, que es
   el bloqueo de #141 por otra puerta — sin desactivar a nadie.

Van contra la base real: lo que se mide es el cruce de `user_roles` con
`role_permissions` y las excepciones individuales.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.organization import Department, Role, User, UserRole
from app.services import usuarios as svc
from app.services.permisos import permisos_efectivos, roles_vigentes

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
    fila = db.scalars(
        select(Department).where(
            Department.tenant_id == EMPRESA_A, Department.deleted_at.is_(None)
        )
    ).first()
    if fila is None:
        pytest.skip("El seed no dejo departamentos en esta empresa")
    return fila.id


def _persona(db: Session, nombre: str, *, rol: str | None = None) -> User:
    fila = User(
        tenant_id=EMPRESA_A,
        department_id=_departamento(db),
        email=f"{uuid.uuid4().hex[:12]}@prueba.cl",
        full_name=nombre,
        user_type="internal",
        status="active",
    )
    db.add(fila)
    db.flush()
    if rol:
        db.add(UserRole(user_id=fila.id, role_id=_rol(db, rol).id, tenant_id=EMPRESA_A))
        db.flush()
        # El rol se antedata **a proposito**: dentro de una transaccion `now()`
        # esta congelado, asi que un rol asignado aca tendria `valid_from`
        # exactamente igual a "ahora". Ese es el caso raro —asignar y retirar
        # sin que nadie lo vea— y tiene su propia prueba; lo normal es que el
        # rol venga de antes.
        db.execute(
            text(
                "UPDATE user_roles SET valid_from = now() - interval '1 day' "
                "WHERE user_id = :u"
            ),
            {"u": str(fila.id)},
        )
        db.expire_all()
    return fila


class TestAsignarUnRolCambiaLoQuePuedeHacer:
    def test_sin_rol_no_puede_nada(self, db: Session) -> None:
        """El punto de partida, y lo que hace significativas a las demas."""
        nadie = _persona(db, "Recien llegada")
        assert permisos_efectivos(db, nadie.id) == set()

    def test_asignar_un_rol_le_da_sus_permisos(self, db: Session) -> None:
        """La unica afirmacion que importa.

        Escribir la fila y que `permisos_efectivos` siga diciendo lo mismo
        seria un endpoint decorativo.
        """
        persona = _persona(db, "Nueva encargada")
        svc.fijar_roles(db, persona, EMPRESA_A, [_rol(db, "encargado_ambiental").id])

        permisos = permisos_efectivos(db, persona.id)
        assert "legal_matrix.read" in permisos
        assert "obligation.write" in permisos

    def test_retirar_el_rol_le_quita_los_permisos(self, db: Session) -> None:
        persona = _persona(db, "Ex encargada", rol="encargado_ambiental")
        assert "obligation.write" in permisos_efectivos(db, persona.id)

        svc.fijar_roles(db, persona, EMPRESA_A, [])

        assert permisos_efectivos(db, persona.id) == set()

    def test_cambiar_de_rol_reemplaza_y_no_acumula(self, db: Session) -> None:
        """`PUT` describe el estado final.

        Si acumulara, pasar a alguien de administradora a operadora le dejaria
        los permisos de administradora — que es exactamente lo contrario de lo
        que quiso quien hizo el cambio.
        """
        persona = _persona(db, "Baja de categoria", rol="admin_empresa")
        assert "user.write" in permisos_efectivos(db, persona.id)

        svc.fijar_roles(db, persona, EMPRESA_A, [_rol(db, "operador").id])

        assert roles_vigentes(db, persona.id) == ["operador"]
        assert "user.write" not in permisos_efectivos(db, persona.id)


class TestRetirarVenceYNoBorra:
    def test_la_fila_sigue_existiendo_con_fecha_de_termino(self, db: Session) -> None:
        """La clave primaria es `(user_id, role_id)`.

        Borrar la fila perderia hasta el ultimo periodo, y con el la unica
        pista de que esa persona tuvo ese rol.
        """
        persona = _persona(db, "Con historia", rol="encargado_ambiental")
        rol = _rol(db, "encargado_ambiental")

        svc.fijar_roles(db, persona, EMPRESA_A, [])

        fila = db.scalars(
            select(UserRole).where(
                UserRole.user_id == persona.id, UserRole.role_id == rol.id
            )
        ).first()
        assert fila is not None, "la asignacion se borro en vez de vencerse"
        assert fila.valid_to is not None

    def test_un_rol_vencido_no_concede_nada(self, db: Session) -> None:
        """Fue encargado no es es encargado."""
        persona = _persona(db, "Vencida", rol="encargado_ambiental")
        svc.fijar_roles(db, persona, EMPRESA_A, [])

        assert roles_vigentes(db, persona.id) == []
        assert permisos_efectivos(db, persona.id) == set()

    def test_volver_a_dar_el_rol_lo_REABRE(self, db: Session) -> None:
        """Y no falla por clave duplicada.

        Es el caso que rompe una implementacion ingenua: la PK impide insertar
        una segunda fila del mismo par, asi que reasignar tiene que reabrir la
        que ya esta.
        """
        persona = _persona(db, "Va y vuelve", rol="encargado_ambiental")
        rol = _rol(db, "encargado_ambiental")
        svc.fijar_roles(db, persona, EMPRESA_A, [])
        assert roles_vigentes(db, persona.id) == []

        svc.fijar_roles(db, persona, EMPRESA_A, [rol.id])

        assert roles_vigentes(db, persona.id) == ["encargado_ambiental"]
        assert "obligation.write" in permisos_efectivos(db, persona.id)

    def test_asignar_y_retirar_sin_que_nadie_lo_vea_BORRA_la_fila(
        self, db: Session
    ) -> None:
        """El unico caso donde no se vence: no hay periodo que registrar.

        Dentro de una transaccion `now()` esta congelado, asi que un rol
        asignado en ese mismo instante tendria `valid_from == now()`.
        `ck_user_roles_vigencia` exige `valid_to > valid_from`, y **cualquier**
        valor que lo cumpla queda en el futuro respecto de `now()` — o sea, el
        rol seguiria vigente. No se puede registrar un periodo de duracion cero.

        Un rol que nunca se vio desde fuera de la transaccion no tiene historia
        que conservar, asi que se borra. Escrito como prueba para que quede
        claro que es una decision y no un descuido.
        """
        persona = _persona(db, "Fugaz")
        rol = _rol(db, "operador")
        svc.fijar_roles(db, persona, EMPRESA_A, [rol.id])

        svc.fijar_roles(db, persona, EMPRESA_A, [])

        fila = db.scalars(
            select(UserRole).where(
                UserRole.user_id == persona.id, UserRole.role_id == rol.id
            )
        ).first()
        assert fila is None, "quedo una asignacion de duracion cero"
        assert roles_vigentes(db, persona.id) == []

    def test_retirar_un_rol_recien_asignado_no_viola_la_vigencia(
        self, db: Session
    ) -> None:
        """`ck_user_roles_vigencia` exige `valid_to > valid_from`.

        Asignar y retirar en el mismo instante daria los dos iguales y Postgres
        rechazaria la fila. Es el tipo de error que solo aparece cuando alguien
        se arrepiente rapido.
        """
        persona = _persona(db, "Arrepentida")
        rol = _rol(db, "operador")
        svc.fijar_roles(db, persona, EMPRESA_A, [rol.id])

        svc.fijar_roles(db, persona, EMPRESA_A, [])

        assert roles_vigentes(db, persona.id) == []


class TestNoDejarALaEmpresaSinAdministrador:
    def _dejar_sola(self, db: Session, persona: User) -> None:
        db.execute(
            text(
                "UPDATE users SET status = 'disabled' "
                "WHERE tenant_id = :t AND id <> :id AND deleted_at IS NULL"
            ),
            {"t": str(EMPRESA_A), "id": str(persona.id)},
        )
        db.expire_all()

    def test_quitarle_el_rol_a_la_unica_administradora_se_rechaza(
        self, db: Session
    ) -> None:
        """El bloqueo de #141 por otra puerta, y sin desactivar a nadie.

        Nadie queda para volver a dar acceso, y la salida es tocar la base.
        """
        sola = _persona(db, "La unica", rol="admin_empresa")
        self._dejar_sola(db, sola)

        with pytest.raises(svc.SinAdministradorTrasElCambio):
            svc.validar_cambio_de_roles(db, sola, EMPRESA_A, [_rol(db, "operador").id])

    def test_dejarla_SIN_ningun_rol_tambien_se_rechaza(self, db: Session) -> None:
        sola = _persona(db, "La unica", rol="admin_empresa")
        self._dejar_sola(db, sola)

        with pytest.raises(svc.SinAdministradorTrasElCambio):
            svc.validar_cambio_de_roles(db, sola, EMPRESA_A, [])

    def test_si_CONSERVA_el_permiso_se_permite(self, db: Session) -> None:
        """Y esto es lo que impide que la guarda rechace todo cambio.

        Cambiar a la unica administradora a otro rol que tambien administra
        usuarios no deja a nadie fuera.
        """
        sola = _persona(db, "La unica", rol="admin_empresa")
        self._dejar_sola(db, sola)

        # El mismo rol otra vez: conserva `user.write`.
        svc.validar_cambio_de_roles(db, sola, EMPRESA_A, [_rol(db, "admin_empresa").id])

    def test_con_otra_administradora_activa_se_permite(self, db: Session) -> None:
        primera = _persona(db, "Primera", rol="admin_empresa")
        segunda = _persona(db, "Segunda", rol="admin_empresa")
        db.execute(
            text(
                "UPDATE users SET status = 'disabled' WHERE tenant_id = :t "
                "AND id NOT IN (:a, :b) AND deleted_at IS NULL"
            ),
            {"t": str(EMPRESA_A), "a": str(primera.id), "b": str(segunda.id)},
        )
        db.expire_all()

        svc.validar_cambio_de_roles(db, primera, EMPRESA_A, [])

    def test_se_mira_el_permiso_EFECTIVO_y_no_solo_el_del_rol(
        self, db: Session
    ) -> None:
        """Una concesion individual tambien sostiene a la empresa.

        A alguien sin rol de administracion se le concede `user.write` a mano.
        Si la guarda mirara solo lo que dan los roles, diria que no queda nadie
        y bloquearia un cambio que es perfectamente seguro.
        """
        sola = _persona(db, "La unica", rol="admin_empresa")
        con_excepcion = _persona(db, "Con permiso a mano", rol="operador")
        db.execute(
            text(
                "INSERT INTO user_permissions (user_id, permission_id, tenant_id, granted) "
                "SELECT :u, id, :t, true FROM permissions WHERE code = 'user.write' "
                "ON CONFLICT (user_id, permission_id) DO UPDATE SET granted = true"
            ),
            {"u": str(con_excepcion.id), "t": str(EMPRESA_A)},
        )
        db.execute(
            text(
                "UPDATE users SET status = 'disabled' WHERE tenant_id = :t "
                "AND id NOT IN (:a, :b) AND deleted_at IS NULL"
            ),
            {"t": str(EMPRESA_A), "a": str(sola.id), "b": str(con_excepcion.id)},
        )
        db.expire_all()

        assert svc.tiene_el_permiso(db, con_excepcion) is True, (
            "la concesion individual no se aplico"
        )
        # No lanza: queda alguien que puede administrar, aunque sea por excepcion.
        svc.validar_cambio_de_roles(db, sola, EMPRESA_A, [])

    def test_una_CONCESION_individual_sobrevive_al_cambio_de_rol(
        self, db: Session
    ) -> None:
        """Esta prueba nacio de una mutacion que sobrevivio.

        Si `permisos_si_tuviera_estos_roles` devolviera solo lo que dan los
        roles —ignorando las excepciones individuales— quedaria **mas
        estricta** que la realidad: a quien administra usuarios por una
        concesion a mano, y no por su rol, se le impediria cualquier cambio de
        rol con un 409 que dice que la empresa quedaria sin administrador.
        Y es falso: la concesion individual no depende del rol y sigue ahi.

        Una guarda que rechaza de mas es tan mala como una que deja pasar: la
        primera se lee como un error del sistema, y quien la sufre no tiene
        forma de saber que hacer.
        """
        sola = _persona(db, "Administra por excepcion", rol="operador")
        db.execute(
            text(
                "INSERT INTO user_permissions (user_id, permission_id, tenant_id, granted) "
                "SELECT :u, id, :t, true FROM permissions WHERE code = 'user.write' "
                "ON CONFLICT (user_id, permission_id) DO UPDATE SET granted = true"
            ),
            {"u": str(sola.id), "t": str(EMPRESA_A)},
        )
        self._dejar_sola(db, sola)

        # Es la unica que puede administrar, y lo puede por la excepcion.
        assert svc.tiene_el_permiso(db, sola) is True
        assert svc.ultimo_que_administra(db, sola, EMPRESA_A) is True

        # Cambiarle el rol a otro que tampoco concede `user.write` **no** la
        # deja sin el permiso: la concesion individual sobrevive.
        svc.validar_cambio_de_roles(
            db, sola, EMPRESA_A, [_rol(db, "encargado_ambiental").id]
        )

    def test_una_DENEGACION_individual_le_gana_al_rol_nuevo(self, db: Session) -> None:
        """La hipotetica aplica la misma precedencia que la real.

        A la unica administradora se le niega `user.write` a mano. Aunque se le
        asigne el rol que lo concede, el permiso efectivo no vuelve.
        """
        sola = _persona(db, "La unica", rol="admin_empresa")
        self._dejar_sola(db, sola)
        db.execute(
            text(
                "INSERT INTO user_permissions (user_id, permission_id, tenant_id, granted) "
                "SELECT :u, id, :t, false FROM permissions WHERE code = 'user.write' "
                "ON CONFLICT (user_id, permission_id) DO UPDATE SET granted = false"
            ),
            {"u": str(sola.id), "t": str(EMPRESA_A)},
        )
        db.expire_all()

        assert svc.tiene_el_permiso(db, sola) is False
        # La guarda no se opone: el dano ya ocurrio y no lo causa este cambio.
        svc.validar_cambio_de_roles(db, sola, EMPRESA_A, [_rol(db, "admin_empresa").id])
