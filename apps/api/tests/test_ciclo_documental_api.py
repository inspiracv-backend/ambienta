"""El ciclo de vida documental, por HTTP (RF-104 a RF-106).

## Por que existe este archivo

`services/control_documental.py` estaba escrito y probado desde el 27-ago
—transiciones, aprobacion firmada, obsolescencia que conserva— **y ningun router
lo llamaba**. Es el mismo patron que tuvo `bcn.sincronizar()`: codigo correcto,
con pruebas en verde, invisible desde fuera y sin ninguna forma de notarlo
mirando la API.

`test_control_documental.py` prueba el servicio. Esto prueba que **se pueda
llegar a el**, que es lo que faltaba.

## Lo que se mide aca y no alla

1. **Que la revision sea de ESE documento.** RLS impide ver las de otra
   empresa; lo que RLS no comprueba es que `/documents/A/versions/B` tenga a B
   colgando de A. Sin la guarda, aprobar por esa URL aprobaria B mientras la
   pantalla cree estar trabajando sobre A.
2. **Que aprobar sin sesion identificada se niegue** en vez de inventar un
   aprobador. Un `approved_by` fabricado es exactamente lo que lee un auditor.
3. **Que una transicion imposible sea 409 y no 422.** El cuerpo esta bien
   formado; lo que no admite el salto es el estado del recurso.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import SessionLocal
    from app.main import app

    # Sin Clerk: la sesion viaja por `X-Tenant-Id` y **no tiene usuario**, que
    # es justo el escenario que hace falta para medir el rechazo de `approve`.
    monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)
    motor = create_engine(URL)
    try:
        motor.connect().close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    original = SessionLocal.kw.get("bind")
    SessionLocal.configure(bind=motor)
    try:
        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original)
        motor.dispose()


@pytest.fixture
def db():
    engine = create_engine(URL)
    try:
        conexion = engine.connect()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    s = Session(bind=conexion)
    # **Por toda la sesion, no `SET LOCAL`.** Los ayudantes de aca hacen
    # `commit` para que el cliente HTTP —que usa otra conexion— vea las filas,
    # y `SET LOCAL` muere en ese commit: el siguiente INSERT falla con
    # "new row violates row-level security policy", que no se parece en nada a
    # la causa. Se limpia al final o la conexion vuelve al pool con la empresa
    # pegada.
    s.execute(text("SET ROLE ambienta_app"))
    s.execute(
        text("SELECT set_config('ambienta.tenant_id', :t, false)"), {"t": EMPRESA_A}
    )
    try:
        yield s
    finally:
        s.rollback()
        s.execute(text("SELECT set_config('ambienta.tenant_id', '', false)"))
        s.execute(text("RESET ROLE"))
        s.commit()
        s.close()
        conexion.close()
        engine.dispose()


@pytest.fixture
def limpiar(db: Session):
    """Las pruebas de HTTP confirman de verdad: hay que borrar a mano."""
    creados: dict[str, list] = {"versions": [], "documents": []}
    yield creados
    # Si la prueba fallo dejando la transaccion abortada, la limpieza tambien
    # falla y **su** error tapa al de la prueba. El rollback deja la sesion
    # utilizable para poder borrar.
    db.rollback()
    if creados["versions"]:
        db.execute(
            text("DELETE FROM document_versions WHERE id = ANY(:ids)"),
            {"ids": creados["versions"]},
        )
    if creados["documents"]:
        db.execute(
            text("UPDATE documents SET current_version_id = NULL WHERE id = ANY(:ids)"),
            {"ids": creados["documents"]},
        )
        db.execute(
            text("DELETE FROM documents WHERE id = ANY(:ids)"),
            {"ids": creados["documents"]},
        )
    db.commit()


def _documento(db: Session, limpiar, *, tipo: str = "procedimiento"):
    did = db.execute(
        text(
            "INSERT INTO documents (tenant_id, document_type, code, title, status) "
            "VALUES (:t, :ti, :c, 'Manejo de residuos', 'borrador') RETURNING id"
        ),
        {"t": EMPRESA_A, "ti": tipo, "c": f"PR-{uuid.uuid4().hex[:6].upper()}"},
    ).scalar_one()
    db.commit()
    limpiar["documents"].append(did)
    return did


#: Estados que la base **no deja escribir** sin quien aprobo y cuando.
#:
#: `ck_document_versions_aprobacion` lo exige, y la primera version de este
#: ayudante lo ignoraba: insertar directo en `vigente` reventaba con
#: "violates check constraint", que se lee como un error de la prueba y es la
#: restriccion haciendo exactamente su trabajo. Es la que sostiene RF-105 —sin
#: ella se podria marcar `aprobado` a mano y la evidencia pasaria la
#: comprobacion sin que nadie hubiera aprobado nada.
EXIGEN_FIRMA = ("aprobado", "vigente", "obsoleto")


def _revision(db: Session, limpiar, document_id, *, numero: int = 1, estado: str = "borrador"):
    firmante = None
    if estado in EXIGEN_FIRMA:
        firmante = db.execute(
            text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
        ).scalar()

    vid = db.execute(
        text(
            "INSERT INTO document_versions "
            "(tenant_id, document_id, version_no, storage_provider, storage_key, "
            " file_name, mime_type, size_bytes, lifecycle_status, "
            " approved_at, approved_by) "
            # `CAST(:f AS uuid)` y no `:f::uuid`: SQLAlchemy confunde el `::`
            # del cast con el `:` de un parametro y deja el primero sin ligar.
            "VALUES (:t, :d, :n, 's3', :k, 'manual.pdf', 'application/pdf', 100, :e, "
            "        :cuando, CAST(:f AS uuid)) "
            "RETURNING id"
        ),
        {
            "t": EMPRESA_A,
            "d": document_id,
            "n": numero,
            "k": f"tenants/{EMPRESA_A}/documents/{document_id}/v{numero}/manual.pdf",
            "e": estado,
            "f": firmante,
            "cuando": datetime.now(timezone.utc) if firmante else None,
        },
    ).scalar_one()
    db.commit()
    limpiar["versions"].append(vid)
    return vid


def _ruta(documento, revision, accion: str) -> str:
    return f"/api/v1/documents/{documento}/versions/{revision}/{accion}"


CABECERAS = {"X-Tenant-Id": EMPRESA_A}


class TestSeLlegaAlServicio:
    """Lo que faltaba: que exista el camino."""

    def test_enviar_a_revision(self, cliente, db, limpiar) -> None:
        doc = _documento(db, limpiar)
        rev = _revision(db, limpiar, doc)

        r = cliente.post(_ruta(doc, rev, "submit-review"), headers=CABECERAS)

        assert r.status_code == 200, r.text
        assert r.json()["lifecycle_status"] == "en_revision"

        # **Y quedo guardado.** Mirar solo la respuesta no basta: sin el
        # `db.commit()` del router la transicion vive en memoria, la sesion se
        # cierra sin confirmar y el endpoint devuelve 200 con el estado nuevo
        # que nunca se escribio. El arnes de mutacion lo encontro asi: quitar
        # el commit no rompia ninguna prueba.
        #
        # Esta sesion es **otra conexion**, asi que solo ve lo confirmado.
        db.rollback()
        assert (
            db.execute(
                text("SELECT lifecycle_status FROM document_versions WHERE id = :v"),
                {"v": rev},
            ).scalar_one()
            == "en_revision"
        ), "la respuesta decia que si y la base no se entero"

    def test_poner_en_vigencia(self, cliente, db, limpiar) -> None:
        doc = _documento(db, limpiar)
        rev = _revision(db, limpiar, doc, estado="aprobado")

        r = cliente.post(
            _ruta(doc, rev, "publish"), json={"motivo": "reemplaza la v1"}, headers=CABECERAS
        )

        assert r.status_code == 200, r.text
        assert r.json()["lifecycle_status"] == "vigente"
        assert r.json()["valid_from"] is not None

    def test_marcar_obsoleta(self, cliente, db, limpiar) -> None:
        doc = _documento(db, limpiar)
        rev = _revision(db, limpiar, doc, estado="vigente")

        r = cliente.post(
            _ruta(doc, rev, "obsolete"),
            json={"motivo": "cambio la normativa aplicable"},
            headers=CABECERAS,
        )

        assert r.status_code == 200, r.text
        cuerpo = r.json()
        assert cuerpo["lifecycle_status"] == "obsoleto"
        assert cuerpo["obsoleted_reason"] == "cambio la normativa aplicable"
        assert cuerpo["obsoleted_at"] is not None


class TestElEstadoSalePorLaAPI:
    """Las siete columnas del ciclo de vida existian y no se exponian.

    Sin ellas la pantalla no puede distinguir un borrador de lo que rige, o sea
    que el control documental era invisible desde fuera.
    """

    def test_la_revision_trae_su_estado(self, cliente, db, limpiar) -> None:
        doc = _documento(db, limpiar)
        rev = _revision(db, limpiar, doc)

        r = cliente.get(f"/api/v1/documents/{doc}/versions/{rev}", headers=CABECERAS)

        assert r.status_code == 200, r.text
        for campo in (
            "lifecycle_status",
            "approved_at",
            "approved_by",
            "valid_from",
            "valid_to",
            "obsoleted_at",
            "obsoleted_reason",
        ):
            assert campo in r.json(), f"falta {campo}: la pantalla no puede mostrarlo"

    def test_el_documento_trae_su_codigo(self, cliente, db, limpiar) -> None:
        """El codigo es lo que se cita en una auditoria."""
        doc = _documento(db, limpiar)

        r = cliente.get(f"/api/v1/documents/{doc}", headers=CABECERAS)

        assert r.status_code == 200, r.text
        assert r.json()["code"], "sin codigo visible el documento no se puede referenciar"


class TestLaRevisionTieneQueSerDeEseDocumento:
    """El agujero que RLS no tapa.

    RLS impide ver revisiones de otra empresa. **No comprueba** que la revision
    de la URL cuelgue del documento de la URL: sin la guarda,
    `/documents/A/versions/B` opera sobre B mientras quien mira la pantalla cree
    estar trabajando sobre A.
    """

    def test_una_revision_de_otro_documento_se_rechaza(self, cliente, db, limpiar) -> None:
        doc_a = _documento(db, limpiar)
        doc_b = _documento(db, limpiar)
        rev_b = _revision(db, limpiar, doc_b)

        r = cliente.post(_ruta(doc_a, rev_b, "submit-review"), headers=CABECERAS)

        assert r.status_code == 422, r.text

        # Y lo importante: **no se movio**.
        estado = db.execute(
            text("SELECT lifecycle_status FROM document_versions WHERE id = :v"),
            {"v": rev_b},
        ).scalar_one()
        assert estado == "borrador", "se opero sobre la revision de otro documento"

    def test_una_revision_inventada_da_el_mismo_error(self, cliente, db, limpiar) -> None:
        """Mismo codigo y mismo mensaje que la de otro documento.

        Distinguirlos convertiria el endpoint en un oraculo para enumerar
        identificadores ajenos: "422 con este texto" contra "422 con este otro"
        responde si una revision existe.
        """
        doc = _documento(db, limpiar)
        inventada = uuid.uuid4()

        r_inventada = cliente.post(
            _ruta(doc, inventada, "submit-review"), headers=CABECERAS
        )

        otro = _documento(db, limpiar)
        rev_otro = _revision(db, limpiar, otro)
        r_ajena = cliente.post(_ruta(doc, rev_otro, "submit-review"), headers=CABECERAS)

        assert r_inventada.status_code == r_ajena.status_code
        assert r_inventada.json()["detail"] == r_ajena.json()["detail"]


class TestAprobarExigeSaberQuien:
    def test_sin_sesion_identificada_se_niega(self, cliente, db, limpiar) -> None:
        """**No se inventa un aprobador.**

        La alternativa —tomar al primer administrador de la empresa— dejaria
        escrito que esa persona aprobo algo que no aprobo, y eso es exactamente
        lo que lee un auditor. Con `X-Tenant-Id` no hay usuario en la sesion.
        """
        doc = _documento(db, limpiar)
        rev = _revision(db, limpiar, doc, estado="en_revision")

        r = cliente.post(_ruta(doc, rev, "approve"), headers=CABECERAS)

        assert r.status_code == 409, r.text
        assert "identificada" in r.json()["detail"]

        estado = db.execute(
            text(
                "SELECT lifecycle_status, approved_by FROM document_versions WHERE id = :v"
            ),
            {"v": rev},
        ).first()
        assert estado[0] == "en_revision", "quedo aprobada sin saber quien"
        assert estado[1] is None


class TestLosCodigosDeError:
    def test_una_transicion_imposible_es_409_y_no_422(self, cliente, db, limpiar) -> None:
        """El cuerpo esta bien formado; el recurso es el que no admite el salto.

        Un 422 le diria a la pantalla "corrige lo que mandaste", y no hay nada
        que corregir — hay que mirar en que estado esta el documento.
        """
        doc = _documento(db, limpiar)
        rev = _revision(db, limpiar, doc, estado="obsoleto")

        r = cliente.post(_ruta(doc, rev, "submit-review"), headers=CABECERAS)

        assert r.status_code == 409, r.text
        assert "obsoleto" in r.json()["detail"]

    def test_un_tipo_no_controlado_es_422(self, cliente, db, limpiar) -> None:
        """Un comprobante de un portal del Estado no se aprueba: se guarda.

        Los tipos NO controlados van en ingles (`receipt`, `evidence`,
        `contract`...) y los controlados en espanol (`procedimiento`,
        `instructivo`...). No es un descuido mio: `db/18` agrego los segundos a
        un CHECK que ya tenia los primeros, y renombrarlos habria roto las
        filas existentes. Vale conocerlo antes de escribir un tipo a mano.
        """
        doc = _documento(db, limpiar, tipo="receipt")
        rev = _revision(db, limpiar, doc)

        r = cliente.post(_ruta(doc, rev, "submit-review"), headers=CABECERAS)

        assert r.status_code == 422, r.text
        assert "controlada" in r.json()["detail"]

    def test_obsoleto_SIN_el_campo_motivo_se_rechaza(self, cliente, db, limpiar) -> None:
        """Omitirlo, no mandarlo en blanco.

        Son dos caminos distintos y la prueba de abajo solo cubria el segundo:
        con `motivo` en blanco lo rechaza el servicio, pero si el esquema le
        pusiera un valor por defecto —"sin motivo"— omitir el campo pasaria
        derecho y la revision quedaria obsoleta con una explicacion inventada.
        El arnes de mutacion lo encontro: ponerle default no rompia nada.
        """
        doc = _documento(db, limpiar)
        rev = _revision(db, limpiar, doc, estado="vigente")

        r = cliente.post(_ruta(doc, rev, "obsolete"), json={}, headers=CABECERAS)

        assert r.status_code == 422, r.text
        db.rollback()
        assert (
            db.execute(
                text("SELECT lifecycle_status FROM document_versions WHERE id = :v"),
                {"v": rev},
            ).scalar_one()
            == "vigente"
        )

    def test_obsoleto_con_motivo_en_blanco_se_rechaza(self, cliente, db, limpiar) -> None:
        doc = _documento(db, limpiar)
        rev = _revision(db, limpiar, doc, estado="vigente")

        r = cliente.post(
            _ruta(doc, rev, "obsolete"), json={"motivo": "   "}, headers=CABECERAS
        )

        assert r.status_code == 422, r.text
        estado = db.execute(
            text("SELECT lifecycle_status FROM document_versions WHERE id = :v"),
            {"v": rev},
        ).scalar_one()
        assert estado == "vigente"


class TestPublicarRetiraLaAnterior:
    def test_la_vigente_anterior_queda_obsoleta(self, cliente, db, limpiar) -> None:
        """Lo exige la restriccion de una sola revision vigente por documento.

        Si esto no pasara, la base rechazaria el segundo `publish` con un error
        de indice unico — ilegible para quien esta en la pantalla.
        """
        doc = _documento(db, limpiar)
        v1 = _revision(db, limpiar, doc, numero=1, estado="vigente")
        v2 = _revision(db, limpiar, doc, numero=2, estado="aprobado")

        r = cliente.post(
            _ruta(doc, v2, "publish"),
            json={"motivo": "reemplazada por la v2"},
            headers=CABECERAS,
        )

        assert r.status_code == 200, r.text
        estados = dict(
            db.execute(
                text(
                    "SELECT id::text, lifecycle_status FROM document_versions "
                    "WHERE id = ANY(:ids)"
                ),
                {"ids": [v1, v2]},
            ).all()
        )
        assert estados[str(v1)] == "obsoleto"
        assert estados[str(v2)] == "vigente"
