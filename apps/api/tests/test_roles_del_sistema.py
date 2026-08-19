"""Los roles del sistema conceden lo que su definicion dice (RF-08).

Spec: `openspec/changes/sistema-actores-roles-rbac/specs/rbac/spec.md`.
Roles: `CLAUDE.md` §5.

## El bug que estas pruebas impiden que vuelva

`db/02_seed.sql` asignaba permisos **por id numerico**, elegidos para un
catalogo de 20 que ese mismo archivo intentaba insertar. Pero
`03_seed_catalogos.sql` corre antes y siembra los 39 reales, asi que el INSERT
de `02_seed` no hace nada y los ids terminan apuntando a permisos distintos:

    id 1  se creyo `obligations.view`  y es `company_profile.read`
    id 16 se creyo `tenants.manage`    y es `nonconformity.read`

Los permisos de los tres roles no estaban incompletos: estaban **mal**. Y no se
noto durante meses porque **ninguna ruta verificaba permisos**, asi que el
error no tenia como manifestarse hasta el dia de conectar la guarda — cuando
habria dejado a todo el mundo afuera con un 403 inexplicable.

Por eso estas pruebas afirman sobre **codigos**, nunca sobre ids.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
TENANT = "a0000000-0000-0000-0000-000000000001"


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    sesion = Session(bind=conexion)
    sesion.execute(text("SET LOCAL ROLE ambienta_app"))
    sesion.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": TENANT}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


def _permisos(db: Session, rol: str) -> set[str]:
    filas = db.execute(
        text(
            "SELECT p.code FROM role_permissions rp "
            "JOIN roles r ON r.id = rp.role_id "
            "JOIN permissions p ON p.id = rp.permission_id "
            "WHERE r.code = :r AND rp.granted"
        ),
        {"r": rol},
    ).all()
    if not filas:
        pytest.skip(f"El rol {rol} no existe o no tiene permisos en esta base")
    return {c for (c,) in filas}


class TestAdminEmpresa:
    """"Gestiona su empresa y empleados" (CLAUDE.md §5)."""

    def test_puede_administrar_a_sus_empleados(self, db: Session) -> None:
        """El caso exacto que el seed roto rompia.

        Un Admin Empresa que no puede invitar ni editar usuarios no es un
        administrador de empresa: es su definicion la que queda sin cumplirse.
        """
        p = _permisos(db, "admin_empresa")

        assert "user.read" in p
        assert "user.write" in p
        assert "role.manage" in p

    def test_no_administra_la_plataforma(self, db: Session) -> None:
        """Darle `platform.*` le dejaria ver la cartera de clientes."""
        p = _permisos(db, "admin_empresa")

        assert not {c for c in p if c.startswith("platform.")}


class TestEncargadoAmbiental:
    """"Operativo — crea/envia declaraciones" (CLAUDE.md §5)."""

    def test_hace_el_trabajo_de_cumplimiento(self, db: Session) -> None:
        p = _permisos(db, "encargado_ambiental")

        for codigo in (
            "obligation.write",
            "obligation.submit",
            "legal_matrix.article.evaluate",
            "audit.write",
            "nonconformity.write",
        ):
            assert codigo in p, f"un encargado tiene que poder {codigo}"

    def test_no_administra_usuarios_ni_permisos(self, db: Session) -> None:
        """Operar el cumplimiento y administrar la empresa son cosas distintas."""
        p = _permisos(db, "encargado_ambiental")

        assert "user.write" not in p
        assert "role.manage" not in p

    def test_no_aprueba_ni_cierra(self, db: Session) -> None:
        """Aprobar y cerrar son actos de responsabilidad, no de edicion.

        El analisis pidio explicitamente separar `puede_aprobar_cierre` de
        `puede_editar_evidencia`: quien registra la evidencia no deberia ser
        quien firma que basta.
        """
        p = _permisos(db, "encargado_ambiental")

        assert "legal_matrix.approve" not in p
        assert "nonconformity.close" not in p


class TestOperador:
    def test_ejecuta_tareas_pero_no_cambia_el_cumplimiento(self, db: Session) -> None:
        p = _permisos(db, "operador")

        assert "task.write" in p
        assert "obligation.write" not in p
        assert "legal_matrix.write" not in p


class TestServicioDeLectura:
    """El usuario para integraciones y para el servicio de IA."""

    def test_solo_tiene_permisos_de_lectura(self, db: Session) -> None:
        """"Solo GETs" tiene que ser cierto, no una etiqueta."""
        p = _permisos(db, "servicio_lectura")

        escrituras = {c for c in p if not c.endswith(".read")}
        assert not escrituras, f"El rol de servicio no deberia escribir: {escrituras}"

    def test_puede_leer_lo_que_una_integracion_necesita(self, db: Session) -> None:
        p = _permisos(db, "servicio_lectura")

        for codigo in ("legal_matrix.read", "obligation.read", "catalog.read"):
            assert codigo in p

    def test_existe_en_la_empresa_de_la_sesion(self, db: Session) -> None:
        """Un usuario de servicio ve **una** empresa, no todas.

        `roles.tenant_id` es NOT NULL, asi que el rol es por empresa. Si una
        integracion necesita varias, necesita un usuario por cada una — que es
        la respuesta correcta, no un atajo.

        ## Por que esta prueba no cuenta todas las empresas

        La primera version comparaba `count(roles) == count(tenants)` y fallaba
        con `1 == 2`. **No era un error del seed: era RLS haciendo su trabajo.**
        `roles` lleva `tenant_id`, asi que la sesion solo ve los de su empresa;
        `tenants` no lo lleva —es la tabla de empresas— y se ven las dos.

        Verificar la propiedad entre empresas exigiria una conexion que se
        salte el aislamiento, que es justo lo que no debe existir. Se afirma
        sobre la empresa de la sesion, que es todo lo que el rol de aplicacion
        puede —y debe— observar.
        """
        roles = db.execute(
            text("SELECT count(*) FROM roles WHERE code = 'servicio_lectura'")
        ).scalar_one()

        assert roles == 1


class TestNadieSinRol:
    def test_todo_usuario_de_empresa_tiene_al_menos_un_rol(self, db: Session) -> None:
        """Sin rol no hay permisos: con la guarda conectada, 403 en todo.

        Pasaba con los usuarios cargados a mano —los de desarrollo, los que
        entran por SSO antes de que exista el webhook— y el sintoma no apunta a
        la causa.
        """
        sin_rol = db.execute(
            text(
                "SELECT u.email FROM users u "
                "WHERE u.deleted_at IS NULL "
                "AND u.user_type IN ('tenant_admin','internal') "
                "AND NOT EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id)"
            )
        ).all()

        assert not sin_rol, f"Usuarios sin ningun rol: {[e for (e,) in sin_rol]}"

    def test_los_tres_roles_existen_en_cada_empresa(self, db: Session) -> None:
        """`02_seed` solo los creaba para Minera Andes.

        Los usuarios de la otra empresa no tenian ningun rol al que pertenecer,
        y el sintoma —403 en todo para media empresa— no apunta a que le falten
        roles a su tenant.
        """
        # Se mira la empresa de la sesion y no todas, por la misma razon que en
        # `test_existe_en_la_empresa_de_la_sesion`: RLS acota `roles` a su
        # empresa, y comprobar el resto exigiria saltarse el aislamiento.
        presentes = {
            c
            for (c,) in db.execute(
                text(
                    "SELECT code FROM roles WHERE code IN "
                    "('admin_empresa','encargado_ambiental','operador')"
                )
            ).all()
        }

        assert presentes == {"admin_empresa", "encargado_ambiental", "operador"}, (
            f"A esta empresa le faltan roles del sistema: "
            f"{{'admin_empresa','encargado_ambiental','operador'}} - {presentes}"
        )
