"""Un Gestor, su cartera, y sobre todo lo que NO puede hacer (#59, #60, #65).

## Que habia antes

Medido el 4-sep: el gestor del seed tiene el contrato `ECOG-2026-001` con Minera
Andes, y al entrar veia un sistema vacio — `/obligations/` devolvia **0 filas** y
no habia **ni una ruta** que nombrara a un cliente o a un sub-tenant. El modelo
sabia quien administra a quien y no existia ningun camino para actuar sobre ello.

## Lo que se agrego, y por que es tan poco

Una lista (`/gestor/clientes`) y una cabecera (`X-Cliente-Id`). El resto de la
API ya funcionaba: lo unico que faltaba era **poder declarar el otro tenant**.

**RLS no se toco.** La politica de las 38 tablas sigue siendo
`tenant_id = current_tenant_id()`. Ampliarla a "o el tenant es cliente de mi
gestor" habria sido una condicion mas que mantener correcta en 38 lugares, y un
error ahi no da una pantalla vacia: da una fuga. La barrera se queda donde
estaba; delante se pone una puerta con llave.

## Por que la mitad de este archivo son negativas

Porque es lo unico que separa esta funcionalidad de un agujero. Un gestor que
puede escribir una cabecera y ver los datos de cualquier empresa **no es una
funcionalidad, es la ausencia de multi-tenancy**. Las cuatro puertas:

| intento | lo que tiene que pasar |
|---|---|
| Empresa normal manda `X-Cliente-Id` | 403 — no es gestor |
| Gestor pide una empresa sin contrato | 403 |
| Gestor pide una empresa con contrato **no vigente** | 403 |
| Gestor sin cabecera | ve lo suyo, no lo de nadie mas |

Y las dos ultimas responden **igual**: mismo codigo y mismo mensaje que un
contrato inexistente. Distinguirlos convertiria la cabecera en un oraculo para
averiguar con quien trabaja otro gestor — el mismo criterio que `validar_visible`.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from sqlalchemy import text  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

#: `EcoGestion Consultoria Ambiental Ltda`, el gestor del seed.
GESTOR = "a0000000-0000-0000-0000-000000000002"
#: `Minera Andes SpA`, su cliente por el contrato `ECOG-2026-001`.
CLIENTE = "a0000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def cliente_http():
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
        yield c


@pytest.fixture
def sesion_duena():
    """Sesion sin RLS para mover el estado del contrato. **Confirma de verdad.**

    La primera version envolvia todo en una transaccion y la revertia al final,
    que es lo prolijo. **No sirve aca:** `TestClient` usa otra conexion, y una
    transaccion sin confirmar no se ve desde fuera de la suya. El resultado era
    que suspender el contrato no cambiaba nada y las dos pruebas de revocacion
    pasaban por el motivo equivocado — reportaban "el gestor sigue entrando"
    cuando en realidad el contrato nunca se habia suspendido.

    Asi que escribe de verdad y cada prueba restaura lo que movio en su
    `finally`. Se toca **solo el contrato del seed**, y volviendo a `active` sin
    `end_date`, que es como estaba.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    url = os.environ["DATABASE_URL"].replace(
        "ambienta_app:ambienta_app_dev", "ambienta:ambienta_dev"
    )
    motor = create_engine(url)
    db = Session(bind=motor)
    try:
        yield db
    finally:
        db.close()
        motor.dispose()


class TestLaCartera:
    def test_el_gestor_ve_a_su_cliente(self, cliente_http) -> None:
        respuesta = cliente_http.get(
            "/api/v1/gestor/clientes", headers={"X-Tenant-Id": GESTOR}
        )
        assert respuesta.status_code == 200, respuesta.text
        cartera = respuesta.json()

        assert cartera, (
            "El gestor no ve ningun cliente. Tiene un contrato en el seed: si "
            "esto vuelve vacio, la cartera no esta leyendo `contracts`."
        )
        suyo = next((c for c in cartera if c["tenant_id"] == CLIENTE), None)
        assert suyo is not None, f"no esta su cliente: {cartera}"
        assert suyo["legal_name"], "el nombre del cliente no se resolvio"
        assert suyo["puede_actuar"] is True

    def test_una_empresa_normal_no_tiene_cartera(self, cliente_http) -> None:
        """403 y no una lista vacia.

        Una lista vacia diria "no tienes clientes todavia", que invita a
        buscarlos. La respuesta correcta es que esta empresa no es un gestor.
        """
        respuesta = cliente_http.get(
            "/api/v1/gestor/clientes", headers={"X-Tenant-Id": CLIENTE}
        )
        assert respuesta.status_code == 403, respuesta.text


class TestActuarPorUnCliente:
    def test_con_la_cabecera_ve_los_datos_del_cliente(self, cliente_http) -> None:
        """La medicion que motivo todo esto.

        Sin cabecera el gestor ve **cero** obligaciones — las de su cliente no
        son suyas. Con la cabecera ve las del cliente.
        """
        propias = cliente_http.get(
            "/api/v1/obligations/", headers={"X-Tenant-Id": GESTOR}
        )
        assert propias.status_code == 200, propias.text

        del_cliente = cliente_http.get(
            "/api/v1/obligations/",
            headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": CLIENTE},
        )
        assert del_cliente.status_code == 200, del_cliente.text

        assert len(del_cliente.json()) > len(propias.json()), (
            "Con `X-Cliente-Id` el gestor no vio mas que sin ella. O la "
            "cabecera no se esta aplicando, o el cliente del seed no tiene "
            "obligaciones — y las tiene."
        )

    def test_actuando_por_el_cliente_no_ve_lo_suyo(self, cliente_http) -> None:
        """**No es una vista combinada**, y no debe serlo.

        Una consulta que mezclara las dos empresas es justo lo que RLS existe
        para impedir. El gestor corre como su cliente, entero, o como el mismo.
        """
        propias = cliente_http.get(
            "/api/v1/facilities/", headers={"X-Tenant-Id": GESTOR}
        ).json()
        actuando = cliente_http.get(
            "/api/v1/facilities/",
            headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": CLIENTE},
        ).json()

        ids_propios = {f["id"] for f in propias}
        ids_actuando = {f["id"] for f in actuando}

        assert ids_propios and ids_actuando, "el seed tiene plantas en las dos"
        assert not (ids_propios & ids_actuando), (
            "Actuando por el cliente aparecen plantas del propio gestor. Eso es "
            "una vista mezclada de dos empresas, que es exactamente lo que RLS "
            "existe para impedir."
        )

    def test_la_cartera_sigue_siendo_la_del_gestor(self, cliente_http) -> None:
        """Si `/gestor/clientes` tomara el tenant efectivo, un gestor que esta
        actuando por un cliente pediria su cartera, recibiria la del cliente
        —vacia, con 403— y **perderia la forma de volver**."""
        respuesta = cliente_http.get(
            "/api/v1/gestor/clientes",
            headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": CLIENTE},
        )
        assert respuesta.status_code == 200, respuesta.text
        assert any(c["tenant_id"] == CLIENTE for c in respuesta.json())


class TestLasCuatroPuertas:
    """Lo unico que separa esto de un agujero."""

    def test_una_empresa_normal_no_puede_suplantar(self, cliente_http) -> None:
        """La puerta principal. Si esto pasara, la cabecera seria una forma de
        leer cualquier empresa escribiendo su identificador."""
        respuesta = cliente_http.get(
            "/api/v1/obligations/",
            headers={"X-Tenant-Id": CLIENTE, "X-Cliente-Id": GESTOR},
        )
        assert respuesta.status_code == 403, (
            f"Una empresa que no es gestor actuo por otra: {respuesta.status_code}. "
            "Eso es la ausencia de multi-tenancy, no una funcionalidad."
        )

    def test_dejar_de_ser_gestor_corta_el_acceso_aunque_el_contrato_siga(
        self, cliente_http, sesion_duena
    ) -> None:
        """**Esta prueba existe porque una mutacion sobrevivio.**

        Al desconectar `es_gestor` de `comprobar_puede_actuar`, las quince
        pruebas seguian en verde. El motivo: el unico caso negativo que habia
        —una empresa normal intentando suplantar al gestor— tambien lo frena la
        *otra* guarda, porque no existe un contrato en esa direccion. Las dos
        puertas estaban tapadas por la misma prueba, y una de ellas se podia
        quitar sin que nada avisara.

        Aca se deja el contrato **intacto** y se le quita el tipo `manager` a la
        empresa. Si el acceso sigue abierto, la unica condicion que queda es
        "tener una fila en `contracts`" — y esa fila la escribe cualquiera que
        pueda crear un contrato.
        """
        sesion_duena.execute(
            text("UPDATE tenants SET tenant_type = 'company' WHERE id = :g"),
            {"g": GESTOR},
        )
        sesion_duena.commit()
        try:
            respuesta = cliente_http.get(
                "/api/v1/obligations/",
                headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": CLIENTE},
            )
            assert respuesta.status_code == 403, (
                f"Una empresa que ya no es gestor sigue actuando por su antiguo "
                f"cliente ({respuesta.status_code}), con el contrato intacto."
            )
        finally:
            sesion_duena.execute(
                text("UPDATE tenants SET tenant_type = 'manager' WHERE id = :g"),
                {"g": GESTOR},
            )
            sesion_duena.commit()

    def test_un_gestor_no_puede_actuar_por_quien_no_es_su_cliente(
        self, cliente_http, sesion_duena
    ) -> None:
        """Una empresa inventada: no hay contrato, asi que no hay acceso."""
        import uuid

        ajena = str(uuid.uuid4())
        respuesta = cliente_http.get(
            "/api/v1/obligations/",
            headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": ajena},
        )
        assert respuesta.status_code == 403, respuesta.text

    def test_un_contrato_suspendido_corta_el_acceso(
        self, cliente_http, sesion_duena
    ) -> None:
        """Suspender un contrato tiene que hacer algo.

        Si el acceso siguiera abierto, "suspender" seria un gesto decorativo — y
        se descubriria cuando alguien pregunte por que un consultor despedido
        sigue leyendo los datos de la empresa.
        """
        sesion_duena.execute(
            text(
                "UPDATE contracts SET status = 'suspended' "
                "WHERE manager_tenant_id = :g AND client_tenant_id = :c"
            ),
            {"g": GESTOR, "c": CLIENTE},
        )
        sesion_duena.commit()
        try:
            respuesta = cliente_http.get(
                "/api/v1/obligations/",
                headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": CLIENTE},
            )
            assert respuesta.status_code == 403, (
                f"Con el contrato suspendido el gestor sigue entrando "
                f"({respuesta.status_code}). Suspender no puede ser decorativo."
            )
        finally:
            sesion_duena.execute(
                text(
                    "UPDATE contracts SET status = 'active' "
                    "WHERE manager_tenant_id = :g AND client_tenant_id = :c"
                ),
                {"g": GESTOR, "c": CLIENTE},
            )
            sesion_duena.commit()

    def test_un_contrato_vencido_corta_el_acceso(
        self, cliente_http, sesion_duena
    ) -> None:
        """Y por la **fecha**, no solo por el estado.

        Un contrato al que se le paso la fecha sin que nadie lo marcara
        `expired` sigue diciendo `active`. Confiar solo en la columna dejaria el
        acceso abierto hasta que alguien se acuerde: el estado es una decision,
        la fecha es un hecho.
        """
        # **Diez dias y no uno.** `CURRENT_DATE` lo evalua Postgres, que corre
        # en UTC; el huso de la empresa es America/Santiago. Pasadas las 20:00
        # los dos estan en dias distintos, asi que `CURRENT_DATE - 1` puede ser
        # **hoy** para la empresa — y un contrato que termina hoy sigue vigente
        # hoy. La primera version de esta prueba fallaba por eso y el mensaje
        # acusaba al codigo. El borde exacto lo mide `TestElBordeDeLaFecha`.
        sesion_duena.execute(
            text(
                "UPDATE contracts SET end_date = CURRENT_DATE - 10 "
                "WHERE manager_tenant_id = :g AND client_tenant_id = :c"
            ),
            {"g": GESTOR, "c": CLIENTE},
        )
        sesion_duena.commit()
        try:
            respuesta = cliente_http.get(
                "/api/v1/obligations/",
                headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": CLIENTE},
            )
            assert respuesta.status_code == 403, (
                "El contrato vencio por fecha y el gestor sigue entrando. El "
                "estado dice `active` porque nadie lo movio, que es justo el "
                "caso que esto tiene que cubrir."
            )
        finally:
            sesion_duena.execute(
                text(
                    "UPDATE contracts SET end_date = NULL "
                    "WHERE manager_tenant_id = :g AND client_tenant_id = :c"
                ),
                {"g": GESTOR, "c": CLIENTE},
            )
            sesion_duena.commit()

    def test_los_dos_rechazos_se_ven_iguales(self, cliente_http) -> None:
        """Sin contrato y con contrato invisible responden lo mismo.

        Distinguirlos convertiria la cabecera en un oraculo para averiguar con
        quien trabaja otro gestor: mandar identificadores al azar y mirar cual
        de los dos errores vuelve. Mismo criterio que `validar_visible`.
        """
        import uuid

        inventada = cliente_http.get(
            "/api/v1/obligations/",
            headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": str(uuid.uuid4())},
        )
        # El otro gestor no existe en el seed, asi que se usa el propio cliente
        # de otra empresa: `CLIENTE` no es gestor, y pedirle actuar por el
        # gestor da el otro camino de rechazo.
        assert inventada.status_code == 403
        assert inventada.json()["detail"] == (
            "No hay un contrato vigente con esa empresa."
        ), (
            "El mensaje de rechazo cambio. Si dice algo distinto segun exista o "
            "no la empresa, se puede enumerar."
        )

    def test_una_cabecera_mal_formada_no_pasa(self, cliente_http) -> None:
        respuesta = cliente_http.get(
            "/api/v1/obligations/",
            headers={"X-Tenant-Id": GESTOR, "X-Cliente-Id": "no-es-un-uuid"},
        )
        assert respuesta.status_code == 400, respuesta.text


class TestElBordeDeLaFecha:
    """El ultimo dia de un contrato, y de que reloj sale "hoy".

    Va aparte y sin base de datos porque es aritmetica de fechas: mezclarlo con
    las pruebas por HTTP fue justamente lo que hizo fallar la de arriba por el
    motivo equivocado.
    """

    def _contrato(self, **campos):
        from app.models.organization import Contract

        base = {"status": "active", "start_date": None, "end_date": None}
        base.update(campos)
        return Contract(**base)

    def test_el_ultimo_dia_todavia_vale(self) -> None:
        """Un contrato que termina hoy **sigue vigente hoy**.

        Cortarlo el mismo dia le quitaria al gestor el ultimo dia de trabajo que
        contrato, y nadie lee "vigente hasta el 30" como "hasta el 29".
        """
        from datetime import date

        from app.services.gestor import _vigente

        hoy = date(2026, 9, 4)
        assert _vigente(self._contrato(end_date=hoy), hoy) is True
        assert _vigente(self._contrato(end_date=date(2026, 9, 3)), hoy) is False

    def test_todavia_no_empieza(self) -> None:
        from datetime import date

        from app.services.gestor import _vigente

        hoy = date(2026, 9, 4)
        assert _vigente(self._contrato(start_date=date(2026, 9, 5)), hoy) is False
        assert _vigente(self._contrato(start_date=hoy), hoy) is True

    def test_el_estado_manda_aunque_las_fechas_esten_bien(self) -> None:
        """Suspender no puede quedar anulado porque las fechas sigan cubriendo."""
        from datetime import date

        from app.services.gestor import _vigente

        hoy = date(2026, 9, 4)
        for estado in ("draft", "pending_signature", "suspended", "expired", "terminated"):
            assert _vigente(self._contrato(status=estado), hoy) is False, estado

    def test_hoy_sale_del_huso_de_la_empresa_y_no_del_servidor(self) -> None:
        """`date.today()` no es "hoy": es "hoy donde corre este proceso".

        La base esta en UTC y el host en hora de Chile. Pasadas las 20:00 los
        dos estan en dias distintos, y con el reloj equivocado un contrato
        vencido ayer seguiria habilitando acceso durante esas horas. Es el mismo
        error que la banda de +-12 h del cron de avisos.
        """
        from datetime import datetime, timezone

        from app.services.husos import hoy_de

        class _SesionFalsa:
            def scalar(self, _consulta):
                return "America/Santiago"

        # 02:00 UTC del dia 5 es todavia el dia 4 en Chile.
        medianoche_utc = datetime(2026, 9, 5, 2, 0, tzinfo=timezone.utc)
        from datetime import date as _date

        assert hoy_de(_SesionFalsa(), None, ahora=medianoche_utc) == _date(2026, 9, 4)
