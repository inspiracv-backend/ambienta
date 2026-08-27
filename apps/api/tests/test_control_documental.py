"""Control de informacion documentada (RF-102 a RF-106, epica #31).

## El agujero que motiva todo esto

**Nada impedia usar un borrador como evidencia.** Medido con una sonda antes de
escribir nada: un documento recien creado, sin ninguna revision aprobada, se
podia colgar de una evaluacion de cumplimiento y el sistema lo aceptaba sin
decir palabra. La empresa quedaba creyendo que tenia respaldo.

Una evidencia sin aprobar no sostiene nada ante un fiscalizador. Es el mismo
tipo de mentira que esta serie lleva encontrando en cada pantalla: algo que se
ve bien y no es cierto.

## Que se prueba aca

Las tres negaciones —borrador, aprobado-sin-vigencia, y obsoleto— son las que
importan. Aprobar un documento se ve funcionando; rechazar el que no sirve, no.

Y las dos restricciones **con dientes**, que no son un `if` en Python:

- aprobado exige quien y cuando (`ck_document_versions_aprobacion`)
- una sola revision vigente por documento (`uq_document_versions_vigente`)

Se prueban contra la base real porque en una sesion simulada no existirian.
"""
from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.documents import Document, DocumentVersion
from app.services.control_documental import (
    SIRVE_COMO_EVIDENCIA,
    TIPOS_CONTROLADOS,
    TRANSICIONES,
    ErrorDocumental,
    EvidenciaSinAprobar,
    NoEsControlado,
    TransicionInvalida,
    aprobar,
    documentos_que_lo_citan,
    enviar_a_revision,
    marcar_obsoleta,
    poner_en_vigencia,
    validar_sirve_como_evidencia,
)

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


@pytest.fixture
def persona(db: Session):
    return db.execute(
        text("SELECT id FROM users WHERE deleted_at IS NULL LIMIT 1")
    ).scalar_one()


def _documento(db: Session, tipo: str = "procedimiento") -> Document:
    did = db.execute(
        text(
            "INSERT INTO documents (tenant_id, document_type, code, title, status) "
            "VALUES (:t, :ti, :c, 'Manejo de Residuos Peligrosos', 'borrador') "
            "RETURNING id"
        ),
        {"t": str(EMPRESA_A), "ti": tipo, "c": f"PR-{uuid.uuid4().hex[:6].upper()}"},
    ).scalar_one()
    db.flush()
    return db.get(Document, did)


def _revision(db: Session, doc: Document, n: int = 1) -> DocumentVersion:
    # `storage_provider` no admite 'local': el CHECK del esquema son
    # s3/backblaze/google_drive/onedrive. Ver la nota sobre almacenamiento.
    vid = db.execute(
        text(
            "INSERT INTO document_versions (tenant_id, document_id, version_no, "
            "storage_provider, storage_key, file_name, mime_type, size_bytes) "
            "VALUES (:t, :d, :n, 's3', :k, 'PR-07.pdf', 'application/pdf', 1024) "
            "RETURNING id"
        ),
        {"t": str(EMPRESA_A), "d": doc.id, "n": n, "k": f"docs/{doc.id}/{n}"},
    ).scalar_one()
    db.flush()
    return db.get(DocumentVersion, vid)


def _vigente(db: Session, doc: Document, persona, n: int = 1) -> DocumentVersion:
    """Una revision recorriendo el ciclo entero hasta regir."""
    r = _revision(db, doc, n)
    enviar_a_revision(db, version_id=r.id)
    aprobar(db, version_id=r.id, aprobador_id=persona)
    poner_en_vigencia(db, version_id=r.id)
    return r


class TestUnBorradorNoEsEvidencia:
    """**RF-105, y es el agujero que motiva la epica.**"""

    def test_un_documento_sin_revision_vigente_no_sirve(self, db) -> None:
        doc = _documento(db)
        _revision(db, doc)

        with pytest.raises(EvidenciaSinAprobar):
            validar_sirve_como_evidencia(db, document_id=doc.id)

    def test_aprobado_pero_sin_entrar_en_vigencia_TAMPOCO(self, db, persona) -> None:
        """Aprobada y vigente son dos cosas, y esta es la razon.

        Se aprueba hoy una revision que entra en vigencia el primero del mes.
        Hasta entonces **rige la anterior**, y usar la nueva como evidencia
        seria citar algo que todavia no manda.
        """
        doc = _documento(db)
        r = _revision(db, doc)
        enviar_a_revision(db, version_id=r.id)
        aprobar(db, version_id=r.id, aprobador_id=persona)

        with pytest.raises(EvidenciaSinAprobar):
            validar_sirve_como_evidencia(db, document_id=doc.id)

    def test_una_revision_vigente_SI_sirve(self, db, persona) -> None:
        """El otro lado: la guarda no puede volverse un estorbo."""
        doc = _documento(db)
        _vigente(db, doc, persona)

        validar_sirve_como_evidencia(db, document_id=doc.id)

    def test_un_documento_retirado_deja_de_servir(self, db, persona) -> None:
        doc = _documento(db)
        r = _vigente(db, doc, persona)
        marcar_obsoleta(db, version_id=r.id, motivo="Se retiro el proceso")

        with pytest.raises(EvidenciaSinAprobar):
            validar_sirve_como_evidencia(db, document_id=doc.id)

    def test_un_comprobante_NO_necesita_aprobacion(self, db) -> None:
        """Los archivos de la operacion pasan sin comprobacion.

        Un comprobante del RETC o un adjunto de correo son evidencia por lo que
        son, no por haber sido aprobados por nadie. Exigirles un flujo de
        aprobacion obligaria a inventar uno para algo que llega ya validado por
        un tercero.
        """
        doc = _documento(db, tipo="receipt")
        _revision(db, doc)

        validar_sirve_como_evidencia(db, document_id=doc.id)

    def test_solo_vigente_sirve_como_evidencia(self) -> None:
        """Fija la lista, para que agregar un estado no la afloje por descuido."""
        assert SIRVE_COMO_EVIDENCIA == frozenset({"vigente"})


class TestElCicloNoSeSaltea:
    """RF-104 — las transiciones que no estan declaradas, no existen."""

    def test_no_se_aprueba_un_borrador_sin_revisarlo(self, db, persona) -> None:
        doc = _documento(db)
        r = _revision(db, doc)

        with pytest.raises(TransicionInvalida):
            aprobar(db, version_id=r.id, aprobador_id=persona)

    def test_no_se_pone_en_vigencia_lo_no_aprobado(self, db) -> None:
        doc = _documento(db)
        r = _revision(db, doc)

        with pytest.raises(TransicionInvalida):
            poner_en_vigencia(db, version_id=r.id)

    def test_una_revision_puede_volver_a_borrador(self, db) -> None:
        """Si la revision encuentra algo que corregir, se devuelve."""
        doc = _documento(db)
        r = _revision(db, doc)
        enviar_a_revision(db, version_id=r.id)

        r.lifecycle_status = "borrador"  # lo que hara el endpoint de rechazo
        assert "borrador" in TRANSICIONES["en_revision"]

    def test_un_obsoleto_no_revive(self, db, persona) -> None:
        """**Sin salida, a proposito.**

        Un documento obsoleto que vuelve a regir deja a quien lo cito sin saber
        si en ese momento mandaba. Se emite una revision nueva.
        """
        assert TRANSICIONES["obsoleto"] == set()

        doc = _documento(db)
        r = _vigente(db, doc, persona)
        marcar_obsoleta(db, version_id=r.id, motivo="x")

        with pytest.raises(TransicionInvalida):
            enviar_a_revision(db, version_id=r.id)


class TestLaAprobacionQuedaEscrita:
    """RF-105 — la pregunta de una auditoria no es si se aprobo, es quien."""

    def test_aprobar_registra_quien_y_cuando(self, db, persona) -> None:
        doc = _documento(db)
        r = _revision(db, doc)
        enviar_a_revision(db, version_id=r.id)

        aprobar(db, version_id=r.id, aprobador_id=persona)

        assert r.approved_by == persona
        assert r.approved_at is not None

    def test_la_BASE_impide_una_aprobacion_anonima(self, db) -> None:
        """**La restriccion con dientes.**

        Ni un `UPDATE` a mano puede dejar una revision aprobada sin firma. Si
        esto fuera solo un `if` en Python, cualquier camino nuevo que escriba
        en la tabla lo saltaria.
        """
        from sqlalchemy.exc import IntegrityError

        doc = _documento(db)
        r = _revision(db, doc)

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "UPDATE document_versions SET lifecycle_status = 'aprobado' "
                    "WHERE id = :i"
                ),
                {"i": r.id},
            )
            db.flush()


class TestUnaSolaRevisionVigente:
    """La empresa tiene que saber cual manda."""

    def test_poner_en_vigencia_la_nueva_obsoleta_la_anterior(self, db, persona) -> None:
        doc = _documento(db)
        r1 = _vigente(db, doc, persona, n=1)

        _vigente(db, doc, persona, n=2)

        assert r1.lifecycle_status == "obsoleto"

    def test_y_dice_por_que(self, db, persona) -> None:
        """RF-106: un obsoleto sin motivo obliga a adivinar si todavia sirve."""
        doc = _documento(db)
        r1 = _vigente(db, doc, persona, n=1)

        _vigente(db, doc, persona, n=2)

        assert "revision 2" in (r1.obsoleted_reason or "")

    def test_la_anterior_se_conserva_no_se_borra(self, db, persona) -> None:
        """RF-106. Las evaluaciones que la citan necesitan saber contra que se
        evaluaron."""
        doc = _documento(db)
        r1 = _vigente(db, doc, persona, n=1)
        _vigente(db, doc, persona, n=2)

        sigue = db.execute(
            text("SELECT count(*) FROM document_versions WHERE id = :i"), {"i": r1.id}
        ).scalar_one()
        assert sigue == 1

    def test_nunca_hay_dos_vigentes(self, db, persona) -> None:
        doc = _documento(db)
        _vigente(db, doc, persona, n=1)
        _vigente(db, doc, persona, n=2)
        _vigente(db, doc, persona, n=3)

        vigentes = db.execute(
            text(
                "SELECT count(*) FROM document_versions "
                "WHERE document_id = :d AND lifecycle_status = 'vigente'"
            ),
            {"d": doc.id},
        ).scalar_one()
        assert vigentes == 1

    def test_el_documento_apunta_a_la_que_rige(self, db, persona) -> None:
        doc = _documento(db)
        _vigente(db, doc, persona, n=1)
        r2 = _vigente(db, doc, persona, n=2)

        assert doc.current_version_id == r2.id
        assert doc.status == "vigente"

    def test_la_BASE_impide_dos_vigentes(self, db, persona) -> None:
        """La otra restriccion con dientes."""
        from sqlalchemy.exc import IntegrityError

        doc = _documento(db)
        _vigente(db, doc, persona, n=1)
        r2 = _revision(db, doc, 2)

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "UPDATE document_versions SET lifecycle_status = 'vigente', "
                    "approved_at = now(), approved_by = :u WHERE id = :i"
                ),
                {"i": r2.id, "u": persona},
            )
            db.flush()


class TestRetirarUnDocumento:
    def test_sin_motivo_no_se_retira(self, db, persona) -> None:
        doc = _documento(db)
        r = _vigente(db, doc, persona)

        with pytest.raises(ErrorDocumental):
            marcar_obsoleta(db, version_id=r.id, motivo="   ")

    def test_retirar_la_vigente_deja_el_documento_sin_nada_que_rija(
        self, db, persona
    ) -> None:
        doc = _documento(db)
        r = _vigente(db, doc, persona)

        marcar_obsoleta(db, version_id=r.id, motivo="Se retiro el proceso")

        assert doc.status == "obsoleto"
        assert doc.current_version_id is None

    def test_se_puede_saber_quien_lo_citaba_antes_de_retirarlo(
        self, db, persona
    ) -> None:
        """No lo impide: retirar un documento vencido es correcto aunque haya
        evaluaciones viejas apuntandole, porque se hicieron cuando si regia."""
        doc = _documento(db)
        r = _vigente(db, doc, persona)

        assert documentos_que_lo_citan(db, version_id=r.id) == []


class TestLosTiposControlados:
    def test_un_archivo_de_operacion_no_lleva_ciclo_de_vida(self, db) -> None:
        """Aprobar el comprobante que devolvio un portal no tiene sentido."""
        doc = _documento(db, tipo="receipt")
        r = _revision(db, doc)

        with pytest.raises(NoEsControlado):
            enviar_a_revision(db, version_id=r.id)

    def test_los_seis_tipos_del_sistema_de_gestion(self) -> None:
        """RF-102. La lista se fija para que quitar uno sea deliberado."""
        assert TIPOS_CONTROLADOS == frozenset(
            {"politica", "procedimiento", "instructivo", "formato", "registro", "externo"}
        )

    def test_la_base_admite_los_seis(self, db) -> None:
        """Y que el CHECK del esquema no se haya quedado atras."""
        for tipo in sorted(TIPOS_CONTROLADOS):
            _documento(db, tipo=tipo)


class TestElCodigo:
    """RF-103 — sin codigo no se puede citar un documento en una auditoria."""

    def test_dos_documentos_no_comparten_codigo(self, db) -> None:
        from sqlalchemy.exc import IntegrityError

        doc = _documento(db)

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO documents (tenant_id, document_type, code, title) "
                    "VALUES (:t, 'procedimiento', :c, 'Otro')"
                ),
                {"t": str(EMPRESA_A), "c": doc.code},
            )
            db.flush()

    def test_los_archivos_de_operacion_pueden_ir_sin_codigo(self, db) -> None:
        """El indice unico es parcial: varios `NULL` no chocan entre si."""
        for _ in range(3):
            db.execute(
                text(
                    "INSERT INTO documents (tenant_id, document_type, title) "
                    "VALUES (:t, 'receipt', 'Comprobante')"
                ),
                {"t": str(EMPRESA_A)},
            )
        db.flush()


class TestLaVigenciaQuedaRegistrada:
    def test_la_revision_que_entra_anota_desde_cuando(self, db, persona) -> None:
        doc = _documento(db)
        r = _vigente(db, doc, persona)

        assert r.valid_from == date.today()

    def test_la_que_sale_anota_hasta_cuando(self, db, persona) -> None:
        """**Lo que pregunta una auditoria:** contra que revision se evaluo en
        tal fecha."""
        doc = _documento(db)
        r1 = _vigente(db, doc, persona, n=1)
        _vigente(db, doc, persona, n=2)

        assert r1.valid_to is not None


class TestElMensajeDiceQueHacer:
    """Las dos guardas de `validar_sirve_como_evidencia` dan mensajes distintos,
    y esa diferencia es lo unico que las separa.

    **La mutacion lo delato.** Quitar cualquiera de las dos por separado
    sobrevivia: la otra atrapa el mismo caso. Solo quitando las dos a la vez
    fallaba algo. Eso no significa que una sobre — significa que las pruebas
    miraban el tipo de excepcion y no **lo que la persona lee**, que es donde
    esta la diferencia util.

    Un mensaje que solo dice "no sirve" deja a quien lo recibe sin saber si le
    falta aprobar, poner en vigencia, o subir un archivo.
    """

    def test_sin_ninguna_revision_dice_que_hay_que_aprobar_una(self, db) -> None:
        doc = _documento(db)
        _revision(db, doc)

        with pytest.raises(EvidenciaSinAprobar) as exc:
            validar_sirve_como_evidencia(db, document_id=doc.id)

        assert "no tiene ninguna revision vigente" in str(exc.value)
        assert "Aprueba una revision" in str(exc.value)

    def test_con_una_revision_en_otro_estado_dice_en_cual(self, db, persona) -> None:
        """Para que se vea que falta el ultimo paso y no todo el proceso."""
        doc = _documento(db)
        r = _vigente(db, doc, persona)
        # Se retira: el documento se queda sin vigente pero con historia.
        marcar_obsoleta(db, version_id=r.id, motivo="Se retiro el proceso")

        with pytest.raises(EvidenciaSinAprobar) as exc:
            validar_sirve_como_evidencia(db, document_id=doc.id)

        assert doc.title in str(exc.value)

    def test_si_el_documento_apunta_a_una_revision_que_no_rige_TAMPOCO_sirve(
        self, db, persona
    ) -> None:
        """La segunda guarda, y hay que construir su caso a mano.

        En operacion normal no dispara nunca: `poner_en_vigencia` mueve el
        estado y el puntero juntos, y `marcar_obsoleta` limpia el puntero. Es
        un respaldo contra datos incoherentes — un `UPDATE` suelto, una
        migracion a medias, un camino nuevo que se olvide de una de las dos
        cosas.

        **Sin ella, ese estado dejaria pasar como evidencia una revision
        obsoleta**, que es peor que no tener evidencia: parece respaldo.
        """
        doc = _documento(db)
        r = _vigente(db, doc, persona)

        # El estado incoherente: la revision deja de regir pero el documento
        # sigue apuntandole.
        db.execute(
            text(
                "UPDATE document_versions SET lifecycle_status = 'obsoleto', "
                "obsoleted_at = now() WHERE id = :i"
            ),
            {"i": r.id},
        )
        db.flush()
        # **`expire_all` y no `refresh(doc)` a secas.** El `UPDATE` crudo no
        # pasa por la ORM, asi que la revision sigue en el mapa de identidad de
        # la sesion con su estado anterior: `db.get()` la devuelve como
        # 'vigente' y la guarda no dispara. La primera version de esta prueba
        # fallo con "DID NOT RAISE" por eso, y el mensaje no se parece en nada
        # a la causa.
        db.expire_all()

        with pytest.raises(EvidenciaSinAprobar) as exc:
            validar_sirve_como_evidencia(db, document_id=doc.id)

        assert "obsoleto" in str(exc.value)
