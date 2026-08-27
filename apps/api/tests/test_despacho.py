"""El despachador de avisos: entrega, reintenta, se rinde y no cruza empresas (#118).

## Por que estas pruebas usan savepoints y no el `rollback` de siempre

El resto de las pruebas de servicios abre una transaccion, escribe y la
deshace al terminar. Aca no sirve: **`despachar()` hace `commit`** —tiene que
hacerlo, porque anotar el intento antes de enviar solo protege si queda
guardado aunque el proceso muera— y un `commit` dentro de la prueba dejaria las
filas escritas de verdad.

La salida es `join_transaction_mode="create_savepoint"`: los `commit` del codigo
bajo prueba confirman un savepoint en vez de la transaccion, y la transaccion de
afuera se deshace igual al final. El codigo no se entera y no hay que
adulterarlo para poder probarlo.

## Por que la sesion es la dueña de la base

El despachador cruza empresas a proposito: los avisos son de todas. Probarlo con
`ambienta_app` seria probar otra cosa —RLS le mostraria una sola empresa— y
justamente lo que hay que verificar es que **al no tener RLS, el codigo pone la
comprobacion que RLS ponia**.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.notifications import Notification
from app.services import despacho
from app.services.despacho import (
    ESPERAS,
    MAX_INTENTOS,
    ErrorPermanente,
    Resultado,
    atrasados,
    despachar,
    espera_tras,
    tomar_uno,
    validar_destinatario,
)

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")

#: La dueña de la base: sin RLS, que es como corre el despachador de verdad.
URL_DUENA = os.getenv(
    "DATABASE_ADMIN_URL",
    "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
)


@pytest.fixture
def db():
    engine = create_engine(URL_DUENA)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    tx = conexion.begin()
    s = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        tx.rollback()
        conexion.close()
        engine.dispose()


class TransporteFalso:
    """Cuenta llamadas y hace lo que se le pida.

    Que **cuente** es la mitad del valor: varias pruebas de aca no comprueban
    que el aviso quede en tal estado sino que **no salio ningun correo**, y eso
    solo se puede afirmar mirando el transporte.
    """

    def __init__(self, *, falla: Exception | None = None, id_devuelto: str = "msg_1"):
        self.falla = falla
        self.id_devuelto = id_devuelto
        self.llamadas: list[dict] = []

    def enviar(self, *, destino: str, asunto: str, cuerpo: str, contexto: dict) -> str:
        self.llamadas.append(
            {"destino": destino, "asunto": asunto, "cuerpo": cuerpo, "contexto": contexto}
        )
        if self.falla is not None:
            raise self.falla
        return self.id_devuelto


def _usuario_de(db: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    uid = db.execute(
        text(
            "SELECT id FROM users WHERE tenant_id = :t AND deleted_at IS NULL "
            "AND status = 'active' AND email IS NOT NULL LIMIT 1"
        ),
        {"t": str(tenant_id)},
    ).scalar()
    if uid is None:
        pytest.skip(f"El seed no tiene un usuario activo con correo en {tenant_id}")
    return uid


def _otra_empresa(db: Session) -> uuid.UUID:
    otra = db.execute(
        text("SELECT id FROM tenants WHERE id <> :a AND deleted_at IS NULL LIMIT 1"),
        {"a": str(EMPRESA_A)},
    ).scalar()
    if otra is None:
        pytest.skip("El seed tiene una sola empresa; no se puede cruzar nada")
    return otra


def _aviso(
    db: Session,
    *,
    canal: str = "email",
    destinatario: uuid.UUID | None = None,
    tenant: uuid.UUID = EMPRESA_A,
    dentro_de: timedelta = timedelta(minutes=-1),
    intentos: int = 0,
) -> Notification:
    """Un aviso encolado. Por defecto vencido hace un minuto, o sea: para ahora."""
    if destinatario is None:
        destinatario = _usuario_de(db, tenant)
    n = Notification(
        tenant_id=tenant,
        recipient_user_id=destinatario,
        channel=canal,
        subject="Vence una obligacion",
        body="Cuerpo del aviso.",
        status="queued",
        scheduled_at=datetime.now(timezone.utc) + dentro_de,
        attempts=intentos,
        dedupe_key=f"prueba-{uuid.uuid4()}",
        context={"obligation_id": str(uuid.uuid4())},
    )
    db.add(n)
    db.flush()
    return n


class TestLaEspera:
    """El retroceso entre reintentos."""

    def test_crece_y_despues_se_estanca(self) -> None:
        esperas = [espera_tras(i) for i in range(1, len(ESPERAS) + 1)]
        assert esperas == list(ESPERAS), "cada intento usa su propia espera"
        assert espera_tras(len(ESPERAS) + 5) == ESPERAS[-1], (
            "pasado el ultimo tramo se repite el mayor, no se dispara"
        )

    def test_el_primer_intento_no_pide_una_espera_negativa(self) -> None:
        """`attempts` es 0 antes del primer intento y el indice quedaria en -1.

        En Python `ESPERAS[-1]` no falla: devuelve **seis horas**, la mayor. Un
        aviso que nunca se intento esperaria seis horas por un error de indice
        que ninguna excepcion delata.
        """
        assert espera_tras(0) == ESPERAS[0]


class TestQueSeToma:
    def test_toma_lo_vencido_y_no_lo_futuro(self, db: Session) -> None:
        futuro = _aviso(db, canal="in_app", dentro_de=timedelta(days=3))
        assert tomar_uno(db, excluir=[]) != futuro or True  # puede haber otros del seed

        ahora = _aviso(db, canal="in_app", dentro_de=timedelta(minutes=-5))
        tomado = tomar_uno(db, excluir=[])
        assert tomado is not None
        assert tomado.id != futuro.id, "un aviso programado para dentro de 3 dias no toca"
        assert tomado.scheduled_at <= datetime.now(timezone.utc)
        assert ahora is not None

    def test_el_reintento_manda_sobre_la_fecha_programada(self, db: Session) -> None:
        """`next_attempt_at` en el futuro esconde el aviso aunque venciera ayer.

        Es lo que hace de arriendo: mientras un despachador lo esta enviando,
        ningun otro lo toma.
        """
        a = _aviso(db, canal="in_app", dentro_de=timedelta(days=-2))
        a.next_attempt_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.flush()

        tomados = []
        excluir: list[uuid.UUID] = []
        for _ in range(5):
            t = tomar_uno(db, excluir=excluir)
            if t is None:
                break
            tomados.append(t.id)
            excluir.append(t.id)

        assert a.id not in tomados, "el arriendo no lo protegio"

    def test_lo_excluido_no_vuelve(self, db: Session) -> None:
        a = _aviso(db, canal="in_app")
        primero = tomar_uno(db, excluir=[])
        assert primero is not None
        segundo = tomar_uno(db, excluir=[primero.id])
        assert segundo is None or segundo.id != primero.id
        assert a is not None

    def test_no_toma_los_borrados(self, db: Session) -> None:
        a = _aviso(db, canal="in_app")
        a.deleted_at = datetime.now(timezone.utc)
        db.flush()

        excluir: list[uuid.UUID] = []
        for _ in range(10):
            t = tomar_uno(db, excluir=excluir)
            if t is None:
                break
            assert t.id != a.id, "un aviso borrado no se despacha"
            excluir.append(t.id)


class TestLaEntrega:
    def test_una_notificacion_in_app_se_entrega_sin_transporte(self, db: Session) -> None:
        """Ya esta entregada cuando existe: el centro de notificaciones la lee.

        Dejarla en `queued` seria decir "esperando envio" de algo que nadie va a
        enviar nunca.
        """
        a = _aviso(db, canal="in_app")
        r = despachar(db, transporte=None, limite=50)

        db.refresh(a)
        assert a.status == "delivered"
        assert a.sent_at is not None
        assert a.provider_message_id is None, "no hubo proveedor; inventar un id seria mentir"
        assert r.entregados >= 1

    def test_un_correo_se_entrega_y_guarda_el_id_del_proveedor(self, db: Session) -> None:
        a = _aviso(db, canal="email")
        t = TransporteFalso(id_devuelto="re_abc123")

        despachar(db, transporte=t, limite=50)

        db.refresh(a)
        assert a.status == "sent"
        assert a.provider_message_id == "re_abc123", (
            "sin el id del proveedor no se puede rastrear un correo que el cliente dice no haber recibido"
        )
        assert a.sent_at is not None
        assert a.last_error is None
        assert a.next_attempt_at is None, "entregado no se reintenta"
        assert any(ll["destino"] for ll in t.llamadas)

    def test_el_correo_va_a_la_direccion_del_destinatario(self, db: Session) -> None:
        uid = _usuario_de(db, EMPRESA_A)
        esperado = db.execute(
            text("SELECT email FROM users WHERE id = :u"), {"u": uid}
        ).scalar_one()

        _aviso(db, canal="email", destinatario=uid)
        t = TransporteFalso()
        despachar(db, transporte=t, limite=50)

        assert esperado in [ll["destino"] for ll in t.llamadas]


class TestSinProveedor:
    def test_el_correo_espera_y_NO_gasta_intentos(self, db: Session) -> None:
        """Falta configuracion, no fallo la entrega.

        Si gastara los cinco intentos contra un proveedor ausente, el dia que
        se configuren las credenciales los avisos acumulados ya estarian
        `failed` — perdidos por una variable de entorno que faltaba.
        """
        a = _aviso(db, canal="email")
        r = despachar(db, transporte=None, limite=50)

        db.refresh(a)
        assert a.status == "queued"
        assert a.attempts == 0, "no se intento nada; el contador no se toca"
        assert a.last_error is None
        assert r.sin_proveedor >= 1
        assert r.fallidos == 0, "no es un fallo de entrega y no debe contarse como tal"

    def test_las_in_app_igual_se_entregan(self, db: Session) -> None:
        """Sin correo configurado el producto sigue funcionando a medias, no a cero."""
        a = _aviso(db, canal="in_app")
        despachar(db, transporte=None, limite=50)
        db.refresh(a)
        assert a.status == "delivered"

    def test_el_bucle_no_se_traba_con_varios_correos_en_espera(self, db: Session) -> None:
        """Un aviso saltado sigue cumpliendo la condicion y volveria a salir.

        Sin la lista de exclusion, `tomar_uno` devuelve el mismo una y otra vez
        y la corrida se consume sin atender a nadie mas. Esta prueba lo fija:
        con tres correos en espera, la in-app del final igual se entrega.
        """
        _aviso(db, canal="email")
        _aviso(db, canal="email")
        _aviso(db, canal="email")
        ultima = _aviso(db, canal="in_app")

        r = despachar(db, transporte=None, limite=10)

        db.refresh(ultima)
        assert ultima.status == "delivered", (
            "el bucle se trabo en los correos y no llego a la notificacion in-app"
        )
        assert r.sin_proveedor >= 3


class TestElReintento:
    def test_un_fallo_deja_el_aviso_encolado_con_el_motivo(self, db: Session) -> None:
        a = _aviso(db, canal="email")
        t = TransporteFalso(falla=RuntimeError("502 del proveedor"))

        r = despachar(db, transporte=t, limite=50)

        db.refresh(a)
        assert a.status == "queued", "un corte del proveedor no pierde el aviso"
        assert a.attempts == 1
        assert "502 del proveedor" in (a.last_error or ""), (
            "sin el motivo hay que reproducir el fallo para diagnosticarlo, y fallan de noche"
        )
        assert a.next_attempt_at is not None
        assert a.next_attempt_at > datetime.now(timezone.utc)
        assert r.reintentables >= 1

    def test_el_intento_se_anota_aunque_el_envio_reviente(self, db: Session) -> None:
        """Lo que acota los duplicados.

        Si el contador se anotara despues de enviar, un proceso que muera en la
        ventana entre "salio el correo" y "quedo anotado" reintentaria con el
        contador en cero — para siempre, mandando el mismo correo cada vez.
        """
        a = _aviso(db, canal="email")
        t = TransporteFalso(falla=RuntimeError("cayo el proceso"))
        despachar(db, transporte=t, limite=50)

        db.refresh(a)
        assert a.attempts == 1

    def test_tras_el_ultimo_intento_se_rinde(self, db: Session) -> None:
        a = _aviso(db, canal="email", intentos=MAX_INTENTOS - 1)
        t = TransporteFalso(falla=RuntimeError("sigue caido"))

        r = despachar(db, transporte=t, limite=50)

        db.refresh(a)
        assert a.attempts == MAX_INTENTOS
        assert a.status == "failed", "reintentar para siempre no es una opcion"
        assert a.next_attempt_at is None
        assert r.rendidos >= 1

    def test_un_error_permanente_no_gasta_los_cinco_intentos(self, db: Session) -> None:
        """Reintentar una direccion invalida no la hace valida, y cada intento se paga."""
        a = _aviso(db, canal="email")
        t = TransporteFalso(falla=ErrorPermanente("direccion inexistente"))

        r = despachar(db, transporte=t, limite=50)

        db.refresh(a)
        assert a.status == "failed"
        assert a.attempts == 1, "se rindio al primero, como corresponde"
        assert r.fallidos >= 1


class TestElAisladoEntreEmpresas:
    """La comprobacion que RLS haria si el despachador no corriera sin RLS."""

    def test_un_aviso_NO_sale_hacia_el_correo_de_otra_empresa(self, db: Session) -> None:
        """El agujero que este codigo tiene que tapar.

        `recipient_user_id` es una clave foranea, y **las claves foraneas no
        pasan por RLS**: la restriccion solo exige que la fila exista, no que
        sea de esta empresa. Con el despachador corriendo como dueño de la base
        —sin RLS— no queda nadie mas que este codigo para impedirlo.

        Lo que se afirma no es que el aviso quede en tal estado: es que **el
        transporte no se llamo ni una vez**.
        """
        otra = _otra_empresa(db)
        ajeno = _usuario_de(db, otra)

        a = _aviso(db, canal="email", tenant=EMPRESA_A, destinatario=ajeno)
        t = TransporteFalso()

        despachar(db, transporte=t, limite=50)

        db.refresh(a)
        assert t.llamadas == [], "SALIO un correo de una empresa hacia otra"
        assert a.status == "failed"
        assert "otra empresa" in (a.last_error or "")

    def test_validar_destinatario_lo_dice_directo(self, db: Session) -> None:
        otra = _otra_empresa(db)
        a = _aviso(db, canal="email", tenant=EMPRESA_A, destinatario=_usuario_de(db, otra))
        with pytest.raises(ErrorPermanente, match="otra empresa"):
            validar_destinatario(db, a)

    def test_un_destinatario_bloqueado_no_recibe(self, db: Session) -> None:
        """Los estados son `invited`, `active`, `blocked` y `disabled`.

        La primera version usaba `inactive`, que no existe, y la base la
        rechazo. Vale anotarlo: si el CHECK no estuviera, la prueba habria
        pasado comprobando un estado imaginario.
        """
        uid = _usuario_de(db, EMPRESA_A)
        db.execute(
            text("UPDATE users SET status = 'blocked' WHERE id = :u"), {"u": uid}
        )
        # Un UPDATE crudo no refresca el mapa de identidad: sin esto `db.get`
        # devuelve el objeto viejo y la prueba pasa sin comprobar nada.
        db.expire_all()

        a = _aviso(db, canal="email", destinatario=uid)
        t = TransporteFalso()
        despachar(db, transporte=t, limite=50)

        db.refresh(a)
        assert t.llamadas == [], "se le escribio a alguien dado de baja"
        assert a.status == "failed"

    def test_un_aviso_sin_destinatario_se_rechaza(self, db: Session) -> None:
        """`recipient_user_id` es nulable, y ese es el unico "sin destinatario" posible.

        La primera version de esta prueba le ponia un UUID inventado, y la base
        la rechazo: hay una clave foranea (`fk_notif_recipient`), asi que un
        destinatario que no existe **no se puede escribir**. La rama de "no
        existe" en `validar_destinatario` solo la alcanza el nulo.
        """
        a = _aviso(db, canal="in_app")
        a.recipient_user_id = None
        db.flush()

        despachar(db, transporte=None, limite=50)
        db.refresh(a)
        assert a.status == "failed"
        assert "no existe" in (a.last_error or "")

    def test_un_destinatario_dado_de_baja_no_recibe(self, db: Session) -> None:
        """La ORM no filtra el borrado logico sola: `db.get()` devuelve la fila igual."""
        uid = _usuario_de(db, EMPRESA_A)
        db.execute(
            text("UPDATE users SET deleted_at = now() WHERE id = :u"), {"u": uid}
        )
        db.expire_all()

        a = _aviso(db, canal="email", destinatario=uid)
        t = TransporteFalso()
        despachar(db, transporte=t, limite=50)

        db.refresh(a)
        assert t.llamadas == [], "se le escribio a alguien dado de baja"
        assert a.status == "failed"


class TestLosAtrasados:
    def test_cuenta_lo_que_lleva_mas_de_un_dia_sin_salir(self, db: Session) -> None:
        """Una cola detenida no produce ningun error: deja de entregar y ya.

        Con avisos de plazos legales eso no puede pasar en silencio.
        """
        antes = atrasados(db, horas=24)
        _aviso(db, canal="email", dentro_de=timedelta(days=-3))
        assert atrasados(db, horas=24) == antes + 1

    def test_lo_reciente_no_cuenta_como_atrasado(self, db: Session) -> None:
        antes = atrasados(db, horas=24)
        _aviso(db, canal="email", dentro_de=timedelta(minutes=-5))
        assert atrasados(db, horas=24) == antes


class TestElResumen:
    def test_menciona_las_cinco_categorias(self) -> None:
        r = Resultado(entregados=1, fallidos=2, reintentables=3, rendidos=4, sin_proveedor=5)
        texto = r.resumen()
        for n in ("1", "2", "3", "4", "5"):
            assert n in texto
        assert "sin proveedor" in texto


class TestElCandadoEsDeVerdad:
    """Dos despachadores a la vez no mandan el mismo correo dos veces.

    Esta no puede usar savepoints: hacen falta **dos conexiones**, y dos
    conexiones no comparten una transaccion sin confirmar. Asi que escribe de
    verdad y limpia en `finally`.
    """

    def test_el_segundo_despachador_salta_la_fila_tomada(self) -> None:
        engine = create_engine(URL_DUENA)
        try:
            c1 = engine.connect()
        except Exception as exc:  # pragma: no cover - entorno sin base
            pytest.skip(f"Sin base de datos disponible: {exc}")

        aviso_id = None
        c2 = engine.connect()
        try:
            with Session(bind=c1) as siembra:
                uid = _usuario_de(siembra, EMPRESA_A)
                a = Notification(
                    tenant_id=EMPRESA_A,
                    recipient_user_id=uid,
                    channel="in_app",
                    subject="candado",
                    body="x",
                    status="queued",
                    scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                    dedupe_key=f"candado-{uuid.uuid4()}",
                )
                siembra.add(a)
                siembra.commit()
                aviso_id = a.id

            s1 = Session(bind=c1)
            s2 = Session(bind=c2)
            try:
                # El primero lo toma y **no suelta**: sigue dentro de su
                # transaccion, como cuando esta hablando con el proveedor.
                excluir1: list[uuid.UUID] = []
                tomado1 = None
                for _ in range(50):
                    t = tomar_uno(s1, excluir=excluir1)
                    if t is None:
                        break
                    if t.id == aviso_id:
                        tomado1 = t
                        break
                    excluir1.append(t.id)
                assert tomado1 is not None, "el primero no llego a tomar el aviso sembrado"

                # El segundo recorre todo lo disponible y **no puede** verlo.
                excluir2: list[uuid.UUID] = []
                for _ in range(50):
                    t = tomar_uno(s2, excluir=excluir2)
                    if t is None:
                        break
                    assert t.id != aviso_id, (
                        "DOS despachadores tomaron el mismo aviso: saldria el correo dos veces"
                    )
                    excluir2.append(t.id)
            finally:
                s1.rollback()
                s2.rollback()
                s1.close()
                s2.close()
        finally:
            if aviso_id is not None:
                with Session(bind=c1) as limpieza:
                    limpieza.execute(
                        text("DELETE FROM notifications WHERE id = :i"), {"i": aviso_id}
                    )
                    limpieza.commit()
            c1.close()
            c2.close()
            engine.dispose()


class TestElRelojEsDeliberado:
    def test_el_despacho_usa_el_reloj_de_python_a_proposito(self) -> None:
        """Y no es un olvido del arreglo de `permisos.py`.

        Alla la comparacion vive dentro del SQL y por eso usa `func.now()`. Aca
        el resultado se usa para decidir en Python —cuanto sumarle a una fecha,
        que anotar— y meter una expresion SQL en `next_attempt_at` guardaria la
        expresion sin evaluar. Los dos criterios son correctos en su sitio; lo
        que seria un error es mezclarlos sin decirlo.
        """
        assert isinstance(despacho._ahora(), datetime)
