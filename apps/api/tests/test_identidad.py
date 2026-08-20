"""`GET /me`: quien llama, de que empresa y que puede hacer.

Es la primera llamada de cualquier integracion, asi que lo que se rompa aca se
rompe antes que todo lo demas — y de las formas mas dificiles de diagnosticar:

- **Devolver el id equivocado.** El JWT trae el id del proveedor de identidad y
  los demas endpoints esperan el UUID interno. Confundirlos da 404 en cualquier
  consulta por usuario, y el 404 se lee como "ese usuario no existe" en vez de
  "estas usando el id de otro sistema".
- **Inventar un usuario en modo desarrollo.** Un cliente que reciba una
  identidad falsa la va a mostrar como verdadera.
- **Un alcance vacio leido como "ninguno".** Significa lo contrario: sin acotar.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.routers.identidad import quien_soy

URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)
TENANT = uuid.UUID("a0000000-0000-0000-0000-000000000001")


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
        text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": str(TENANT)}
    )
    try:
        yield sesion
    finally:
        sesion.rollback()
        sesion.close()
        conexion.close()
        engine.dispose()


class _Sesion:
    """Lo que la API sabe del token: solo estos dos claims."""

    def __init__(self, user_id: str, tenant_id=TENANT) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id


def _con_clerk(monkeypatch) -> None:
    """Enciende el modo con proveedor de identidad."""
    from app.config import get_settings

    monkeypatch.setenv("CLERK_JWKS_URL", "https://clerk.test/jwks.json")
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.test")
    get_settings.cache_clear()


def _sin_clerk(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    monkeypatch.delenv("CLERK_ISSUER", raising=False)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _limpiar_settings():
    from app.config import get_settings

    yield
    get_settings.cache_clear()


def _usuario_con_clerk(db: Session, clerk_id: str) -> uuid.UUID:
    """Le pone `clerk_id` a un usuario real de la empresa y devuelve su UUID."""
    uid = db.execute(
        text(
            "SELECT id FROM users WHERE tenant_id = :t AND deleted_at IS NULL LIMIT 1"
        ),
        {"t": TENANT},
    ).scalar()
    if uid is None:
        pytest.skip("Sin usuarios sembrados en la empresa de prueba")
    db.execute(
        text("UPDATE users SET clerk_id = :c WHERE id = :i"), {"c": clerk_id, "i": uid}
    )
    return uid


class TestModoDesarrollo:
    def test_no_inventa_un_usuario(self, db: Session, monkeypatch) -> None:
        """Sin proveedor de identidad no hay identidad, y se dice.

        Devolver un usuario ficticio seria peor que devolver `null`: el cliente
        no tiene como distinguirlo de uno real y lo va a mostrar como tal.
        """
        _sin_clerk(monkeypatch)

        r = quien_soy(user=_Sesion("quien-sea"), db=db)

        assert r.modo_desarrollo is True
        assert r.usuario is None
        assert r.permisos == []

    def test_igual_devuelve_la_empresa(self, db: Session, monkeypatch) -> None:
        """La empresa si se conoce: viene del header. Es lo que hace usable el
        modo local, donde no hay Clerk pero si hay datos que consultar."""
        _sin_clerk(monkeypatch)

        r = quien_soy(user=_Sesion("quien-sea"), db=db)

        assert r.empresa.id == TENANT
        assert r.empresa.nombre != ""


class TestConProveedorDeIdentidad:
    def test_devuelve_el_uuid_interno_no_el_de_clerk(
        self, db: Session, monkeypatch
    ) -> None:
        """**El campo que mas facil se usa mal.**

        Los demas endpoints esperan el UUID interno; el JWT lleva el del
        proveedor. Devolver el segundo en `id` haria fallar toda consulta por
        usuario con un 404 que se lee como "no existe".
        """
        _con_clerk(monkeypatch)
        uid = _usuario_con_clerk(db, "user_2prueba_identidad")

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.usuario is not None
        assert r.usuario.id == uid
        assert r.usuario.clerk_id == "user_2prueba_identidad"
        assert str(r.usuario.id) != r.usuario.clerk_id

    def test_trae_el_perfil_normativo_de_la_empresa(
        self, db: Session, monkeypatch
    ) -> None:
        """El sector y el tramo deciden que normativa aplica.

        Un cliente que no los reciba no puede explicar por que la matriz esta
        vacia, que es justo el estado en que estan hoy casi todas las empresas.
        """
        _con_clerk(monkeypatch)
        _usuario_con_clerk(db, "user_2prueba_identidad")
        sid = db.execute(text("SELECT id FROM sectors LIMIT 1")).scalar()
        db.execute(
            text("UPDATE tenants SET sector_id = :s, size_bracket = 'mediana' WHERE id = :t"),
            {"s": sid, "t": TENANT},
        )

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.empresa.sector_id == sid
        assert r.empresa.tramo == "mediana"

    def test_sin_perfil_normativo_viene_en_null_no_en_cero(
        self, db: Session, monkeypatch
    ) -> None:
        """`null` dice "no declarado". Un cero o una cadena vacia se leerian
        como un sector real y mandarian a buscar normativa que no existe."""
        _con_clerk(monkeypatch)
        _usuario_con_clerk(db, "user_2prueba_identidad")
        db.execute(
            text("UPDATE tenants SET sector_id = NULL, size_bracket = NULL WHERE id = :t"),
            {"t": TENANT},
        )

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.empresa.sector_id is None
        assert r.empresa.tramo is None

    def test_los_permisos_vienen_resueltos(self, db: Session, monkeypatch) -> None:
        """Ya aplicada la precedencia, no la lista cruda de los roles.

        Si el cliente tuviera que resolverla, la regla quedaria escrita dos
        veces y la pantalla mostraria acciones que la API va a rechazar.
        """
        _con_clerk(monkeypatch)
        uid = _usuario_con_clerk(db, "user_2prueba_identidad")
        from app.services.permisos import permisos_efectivos

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.permisos == sorted(permisos_efectivos(db, uid))

    def test_una_denegacion_individual_no_aparece_en_la_lista(
        self, db: Session, monkeypatch
    ) -> None:
        """La denegacion le gana al rol, y eso tiene que verse en `/me`.

        Es la propiedad util del modelo —quitarle un permiso a alguien sin
        sacarlo del rol— y si `/me` la ignorara, el cliente ofreceria una accion
        que la API rechaza con 403.
        """
        _con_clerk(monkeypatch)
        uid = _usuario_con_clerk(db, "user_2prueba_identidad")

        antes = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db).permisos
        if not antes:
            pytest.skip("El usuario de prueba no tiene permisos que denegar")

        codigo = antes[0]
        pid = db.execute(
            text("SELECT id FROM permissions WHERE code = :c"), {"c": codigo}
        ).scalar()
        db.execute(
            text(
                # `tenant_id` es NOT NULL y ademas lo exige la politica de RLS:
                # sin el, el INSERT no falla por la columna sino por la politica,
                # y el error habla de "row-level security" en vez de decir que
                # falta un dato.
                "INSERT INTO user_permissions "
                "(user_id, permission_id, tenant_id, granted) "
                "VALUES (:u, :p, :t, false) "
                "ON CONFLICT (user_id, permission_id) DO UPDATE SET granted = false"
            ),
            {"u": uid, "p": pid, "t": TENANT},
        )

        despues = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db).permisos

        assert codigo in antes
        assert codigo not in despues

    def test_un_token_sin_fila_de_usuario_explica_por_que(
        self, db: Session, monkeypatch
    ) -> None:
        """Es el estado que deja el SSO cuando el webhook no corrio.

        La causa es operativa, no un error de quien llama, asi que se explica en
        vez de devolver un 404 generico que manda a revisar el codigo.
        """
        from fastapi import HTTPException

        _con_clerk(monkeypatch)

        with pytest.raises(HTTPException) as exc:
            quien_soy(user=_Sesion("user_2que_no_existe_en_la_base"), db=db)

        assert exc.value.status_code == 403
        assert exc.value.detail["codigo"] == "sesion_sin_usuario"


class TestElAlcance:
    def test_sin_acotar_lo_dice_explicito(self, db: Session, monkeypatch) -> None:
        """**Una lista vacia significa "sin acotar", no "ninguno".**

        Es la diferencia entre un encargado de toda la empresa y uno sin acceso
        a nada. `acotado` existe para que el cliente no tenga que interpretar la
        lista, porque la interpretacion intuitiva es la contraria.
        """
        _con_clerk(monkeypatch)
        uid = _usuario_con_clerk(db, "user_2prueba_identidad")
        db.execute(
            text(
                "UPDATE user_roles SET facility_id = NULL, department_id = NULL "
                "WHERE user_id = :u"
            ),
            {"u": uid},
        )

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.acotado is False
        assert r.instalaciones == []
        assert r.departamentos == []

    def test_acotado_a_una_instalacion(self, db: Session, monkeypatch) -> None:
        _con_clerk(monkeypatch)
        uid = _usuario_con_clerk(db, "user_2prueba_identidad")
        fid = db.execute(
            text("SELECT id FROM facilities WHERE tenant_id = :t LIMIT 1"), {"t": TENANT}
        ).scalar()
        if fid is None:
            pytest.skip("Sin instalaciones sembradas")
        db.execute(
            text("UPDATE user_roles SET facility_id = :f WHERE user_id = :u"),
            {"f": fid, "u": uid},
        )

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.acotado is True
        assert fid in r.instalaciones


class TestLoQueNecesitaUnaIntegracion:
    """Los campos que pidio quien construye el agente, y por que estos.

    El pedido fue: usuario, compania, **tipo de compania**, sector, y **su rol**.
    Los tres ultimos no estaban, y cada uno se equivoca de una forma distinta si
    se resuelve mal.
    """

    def test_dice_si_la_empresa_es_gestor_o_cliente(
        self, db: Session, monkeypatch
    ) -> None:
        """`tenant_type` decide como se administra su normativa.

        Son **cuatro** valores, no dos. Tratar `managed_client` como `company`
        pierde que su normativa la lleva un tercero.
        """
        _con_clerk(monkeypatch)
        _usuario_con_clerk(db, "user_2prueba_identidad")

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.empresa.tipo in {"company", "manager", "managed_client", "platform"}

    def test_el_sector_viene_con_codigo_y_nombre_no_solo_el_id(
        self, db: Session, monkeypatch
    ) -> None:
        """El id no explica nada.

        Quien consuma esto tiene que poder decir "le aplica porque es industria
        manufacturera", no "porque es 3".
        """
        _con_clerk(monkeypatch)
        _usuario_con_clerk(db, "user_2prueba_identidad")
        sid = db.execute(text("SELECT id FROM sectors WHERE code = 'C'")).scalar()
        db.execute(
            text("UPDATE tenants SET sector_id = :s WHERE id = :t"),
            {"s": sid, "t": TENANT},
        )

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.empresa.sector is not None
        assert r.empresa.sector.codigo == "C"
        assert r.empresa.sector.nombre != ""
        # El id suelto sigue estando, y coincide.
        assert r.empresa.sector_id == r.empresa.sector.id

    def test_sin_sector_declarado_el_objeto_es_null(
        self, db: Session, monkeypatch
    ) -> None:
        """`null`, no un sector inventado con nombre vacio."""
        _con_clerk(monkeypatch)
        _usuario_con_clerk(db, "user_2prueba_identidad")
        db.execute(
            text("UPDATE tenants SET sector_id = NULL WHERE id = :t"), {"t": TENANT}
        )

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.empresa.sector is None
        assert r.empresa.sector_id is None

    def test_devuelve_los_roles_vigentes(self, db: Session, monkeypatch) -> None:
        _con_clerk(monkeypatch)
        uid = _usuario_con_clerk(db, "user_2prueba_identidad")
        from app.services.permisos import roles_vigentes

        r = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert r.roles == roles_vigentes(db, uid)
        assert r.roles  # el usuario sembrado tiene al menos uno

    def test_un_rol_vencido_no_aparece(self, db: Session, monkeypatch) -> None:
        """"Fue encargado" no es "es encargado".

        Sin el filtro de vigencia, alguien conserva su etiqueta despues de que
        se le retiro — y los permisos ya la respetan, asi que el rol y los
        permisos se contradirian en la misma respuesta.
        """
        _con_clerk(monkeypatch)
        uid = _usuario_con_clerk(db, "user_2prueba_identidad")
        antes = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db).roles
        if not antes:
            pytest.skip("El usuario de prueba no tiene roles que vencer")

        # **Se mueven las dos fechas, no solo `valid_to`.** El CHECK
        # `ck_user_roles_vigencia` exige `valid_to > valid_from`, asi que vencer
        # el rol dejando `valid_from` donde estaba solo funciona si el dato es
        # mas viejo que un dia. En local el seed lleva tiempo y pasaba; en CI la
        # base se crea en el momento y fallaba. La prueba dependia de la edad de
        # los datos, que es una forma silenciosa de no probar nada estable.
        db.execute(
            text(
                "UPDATE user_roles "
                "SET valid_from = now() - interval '10 days', "
                "    valid_to   = now() - interval '1 day' "
                "WHERE user_id = :u"
            ),
            {"u": uid},
        )

        despues = quien_soy(user=_Sesion("user_2prueba_identidad"), db=db)

        assert despues.roles == []
        # Y los permisos se van con el, que es la razon de filtrar.
        assert despues.permisos == []
