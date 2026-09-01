"""El checklist de la auditoria y su cobertura (#36, RF-92/RF-93).

## Lo que estaba roto, medido

El CRUD del checklist **existia**. Lo que no funcionaba era lo que aceptaba:
`AuditItemCreateAnidado` nombraba cuatro campos que `audit_items` no tiene
—`clause_reference`, `article_id`, `result`, `evidence_note`— y
`create_audit_item` se los pasaba a `AuditItemCreate`, que los descarta.

Medido contra la API antes del arreglo:

    POST /audits/{id}/items
      {"result": "conform", "evidence_note": "informe adjunto", ...}
    -> 201
       result guardado: pending
       evidence_note: no aparece

**Respondia 201 y descartaba en silencio cuatro de los seis campos que decia
aceptar.** Es el mismo defecto de `compliance_answer` e `is_active`: un esquema
que nombra columnas inexistentes, sin que nada lo detecte.

Y faltaba `article_compliance_id`, que es **el vinculo por clausula que RF-92
pide**: sin el no habia forma de decir que requisito legal revisa cada pregunta.

## Por que la cobertura importa (RF-93)

Sin ella, una auditoria que reviso **3 de 50** requisitos y no encontro nada se
lee **identica** a una que los reviso los 50: las dos dicen "0 no conformes".
El resumen que ya existia contaba resultados y no decia cuanto se habia mirado.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)

from app.main import app  # noqa: E402

EMPRESA_A = "a0000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def cliente():
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        engine.connect().close()
    except Exception as exc:  # pragma: no cover - entorno sin base
        pytest.skip(f"Sin base de datos disponible: {exc}")
    engine.dispose()
    return TestClient(app)


def _como(t: str) -> dict[str, str]:
    return {"X-Tenant-Id": t}


@pytest.fixture
def auditoria(cliente):
    filas = cliente.get("/api/v1/audits/", headers=_como(EMPRESA_A)).json()
    if not filas:
        pytest.skip("El seed no dejo auditorias")
    return filas[0]["id"]


@pytest.fixture
def clausula(cliente):
    filas = cliente.get(
        "/api/v1/compliance/article-compliance/", headers=_como(EMPRESA_A)
    ).json()
    if not filas:
        pytest.skip("El seed no dejo evaluaciones de articulo")
    return filas[0]["id"]


@pytest.fixture
def limpiar():
    """Borra lo que la prueba creo. Estas pruebas escriben en tablas vivas."""
    creados: list[str] = []
    yield creados
    if creados:
        # Se borra con la sesion del tenant, no asumiendo el rol dueno:
        # `ambienta_app` no puede hacerlo, y ademas RLS ya deja borrar lo
        # propio — que es exactamente lo que estas filas son.
        engine = create_engine(os.environ["DATABASE_URL"])
        with engine.begin() as con:
            con.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": EMPRESA_A},
            )
            con.execute(
                text("DELETE FROM audit_items WHERE id = ANY(:ids)"),
                {"ids": [str(i) for i in creados]},
            )
        engine.dispose()


def _crear(cliente, auditoria, limpiar, **cuerpo):
    cuerpo.setdefault("question", "Se mide el caudal de la descarga?")
    r = cliente.post(
        f"/api/v1/audits/{auditoria}/items", headers=_como(EMPRESA_A), json=cuerpo
    )
    if r.status_code == 201:
        limpiar.append(r.json()["id"])
    return r


class TestLoQueSeAceptaAhoraSeGuarda:
    def test_el_vinculo_POR_CLAUSULA_se_puede_fijar(
        self, cliente, auditoria, clausula, limpiar
    ) -> None:
        """Es RF-92, y antes era **inalcanzable**: el cuerpo no tenia el campo."""
        r = _crear(cliente, auditoria, limpiar, article_compliance_id=clausula)

        assert r.status_code == 201, r.text
        assert r.json()["article_compliance_id"] == clausula

    def test_la_nota_se_guarda(self, cliente, auditoria, limpiar) -> None:
        r = _crear(cliente, auditoria, limpiar, notes="Se reviso el informe de marzo")

        assert r.json()["notes"] == "Se reviso el informe de marzo"

    def test_una_pregunta_nace_SIN_responder(self, cliente, auditoria, limpiar) -> None:
        """`result` no se acepta al crear, a proposito.

        Aceptarlo permitiria levantar un checklist ya contestado sin que nadie
        lo haya recorrido, y la marca de cuando se respondio quedaria vacia.
        """
        r = _crear(cliente, auditoria, limpiar)

        assert r.json()["result"] == "pending"
        assert r.json()["assessed_at"] is None


class TestElOrden:
    def test_la_secuencia_se_asigna_sola(self, cliente, auditoria, limpiar) -> None:
        """`uq_audit_items_seq` la exige unica por auditoria.

        Dejarla siempre en manos de quien llama convierte un olvido en un error
        de restriccion, que se lee como una falla del sistema.
        """
        primera = _crear(cliente, auditoria, limpiar).json()["sequence"]
        segunda = _crear(cliente, auditoria, limpiar).json()["sequence"]

        assert segunda == primera + 1

    def test_repetir_una_secuencia_a_mano_responde_409(
        self, cliente, auditoria, limpiar
    ) -> None:
        """Y no un error de restriccion crudo.

        Lo traduce el manejador global de `IntegrityError`, que ademas **nombra
        la restriccion**. No se envuelve en el endpoint: `CRUDBase.create` hace
        `flush` por dentro, asi que un `try` alrededor del `commit` seria una
        guarda que nunca se cumple. La primera version de este endpoint tenia
        una, y esta prueba la delato.
        """
        n = _crear(cliente, auditoria, limpiar).json()["sequence"]

        r = _crear(cliente, auditoria, limpiar, sequence=n)

        assert r.status_code == 409, r.text
        assert "uq_audit_items_seq" in r.json()["detail"]


class TestResponderUnaPregunta:
    def test_al_responder_se_anota_CUANDO(
        self, cliente, auditoria, limpiar
    ) -> None:
        """Sin esa marca no se puede decir si la auditoria se contesto durante
        su ejecucion o despues de cerrarla — que es justo lo que revisa un
        certificador."""
        item = _crear(cliente, auditoria, limpiar).json()

        r = cliente.patch(
            f"/api/v1/audits/{auditoria}/items/{item['id']}",
            headers=_como(EMPRESA_A),
            json={"result": "conform"},
        )

        assert r.status_code == 200, r.text
        assert r.json()["result"] == "conform"
        assert r.json()["assessed_at"] is not None

    def test_dejarla_en_PENDING_no_la_fecha(
        self, cliente, auditoria, limpiar
    ) -> None:
        """La otra mitad: sin esto la marca se pondria siempre, y diria que se
        respondio algo que sigue sin responder."""
        item = _crear(cliente, auditoria, limpiar).json()

        r = cliente.patch(
            f"/api/v1/audits/{auditoria}/items/{item['id']}",
            headers=_como(EMPRESA_A),
            json={"result": "pending"},
        )

        assert r.json()["assessed_at"] is None

    def test_la_fecha_NO_se_puede_mandar_desde_el_cuerpo(
        self, cliente, auditoria, limpiar
    ) -> None:
        """Aceptarla permitiria fechar una respuesta cuando conviniera."""
        item = _crear(cliente, auditoria, limpiar).json()

        r = cliente.patch(
            f"/api/v1/audits/{auditoria}/items/{item['id']}",
            headers=_como(EMPRESA_A),
            json={"result": "conform", "assessed_at": "2020-01-01T00:00:00Z"},
        )

        assert r.status_code == 200
        assert not r.json()["assessed_at"].startswith("2020")


class TestLasClavesForaneasDelCuerpo:
    def test_una_clausula_INVENTADA_se_rechaza(
        self, cliente, auditoria, limpiar
    ) -> None:
        r = _crear(cliente, auditoria, limpiar, article_compliance_id=str(uuid.uuid4()))

        assert r.status_code == 422, r.text
        assert "article_compliance_id" in r.json()["detail"]

    def test_la_comprobacion_es_la_misma_que_cierra_la_fuga_conocida(
        self, cliente, auditoria, limpiar
    ) -> None:
        """El caso "existe pero es de otra empresa" **no se puede ejercitar con
        este seed**, y conviene decirlo en vez de dejar un `skip` que se lea
        como verde.

        Medido: la empresa A tiene 100 evaluaciones y la B **cero**, asi que no
        existe en la base ninguna fila de otra empresa que A no vea. Construirla
        exigiria sembrar matriz, norma y articulo — una cadena que esta prueba
        no deberia arrastrar.

        Lo que si se fija es que el endpoint pasa por `validar_visible`, que es
        el mismo camino que ya cierra esa fuga en el resto de la API y que
        responde **identico** para un id inventado y para uno ajeno. La mitad
        cruzada tiene su prueba propia en `test_iso_aislamiento.py`, donde el
        seed si permite montarla.
        """
        r = _crear(cliente, auditoria, limpiar, article_compliance_id=str(uuid.uuid4()))

        assert r.status_code == 422
        # El mensaje de `validar_visible`, palabra por palabra: es lo que hace
        # que las dos respuestas sean indistinguibles.
        assert r.json()["detail"] == (
            "article_compliance_id no corresponde a un registro de esta empresa."
        )


class TestLaCobertura:
    def test_dice_cuanto_de_lo_aplicable_se_reviso(
        self, cliente, auditoria, clausula, limpiar
    ) -> None:
        """El numero que falta para leer un resumen sin equivocarse."""
        _crear(cliente, auditoria, limpiar, article_compliance_id=clausula)

        d = cliente.get(
            f"/api/v1/audits/{auditoria}/coverage", headers=_como(EMPRESA_A)
        ).json()

        assert d["aplicables"] >= 1
        assert d["cubiertos"] >= 1
        assert d["porcentaje"] is not None

    def test_dos_preguntas_sobre_LA_MISMA_clausula_no_la_cubren_dos_veces(
        self, cliente, auditoria, clausula, limpiar
    ) -> None:
        """Si no, preguntar lo mismo diez veces daria 100 % de cobertura."""
        antes = cliente.get(
            f"/api/v1/audits/{auditoria}/coverage", headers=_como(EMPRESA_A)
        ).json()["cubiertos"]

        _crear(cliente, auditoria, limpiar, article_compliance_id=clausula)
        _crear(cliente, auditoria, limpiar, article_compliance_id=clausula)

        despues = cliente.get(
            f"/api/v1/audits/{auditoria}/coverage", headers=_como(EMPRESA_A)
        ).json()["cubiertos"]

        assert despues - antes <= 1

    def test_las_preguntas_SIN_clausula_van_aparte(
        self, cliente, auditoria, limpiar
    ) -> None:
        """Son preguntas de proceso, legitimas, que no cubren ningun requisito
        legal. Contarlas como cobertura la inflaria."""
        antes = cliente.get(
            f"/api/v1/audits/{auditoria}/coverage", headers=_como(EMPRESA_A)
        ).json()

        _crear(cliente, auditoria, limpiar)

        despues = cliente.get(
            f"/api/v1/audits/{auditoria}/coverage", headers=_como(EMPRESA_A)
        ).json()

        assert despues["items_sin_articulo"] == antes["items_sin_articulo"] + 1
        assert despues["cubiertos"] == antes["cubiertos"]

    def test_sin_nada_aplicable_el_porcentaje_es_NULO_y_no_cero(
        self, cliente
    ) -> None:
        """Un 0 % ahi seria una acusacion por algo que no existe.

        Es el mismo error del tablero con las plantas sin evaluar, que ya se
        corrigio una vez (#125).
        """
        from app.models.audit import Audit
        from app.services.audits import cobertura
        from sqlalchemy.orm import Session

        engine = create_engine(os.environ["DATABASE_URL"])
        con = engine.connect()
        s = Session(bind=con)
        s.execute(text("SET LOCAL ROLE ambienta_app"))
        s.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"), {"t": EMPRESA_A}
        )
        # Una planta sin ninguna evaluacion: el denominador queda en cero.
        vacia = Audit(
            tenant_id=uuid.UUID(EMPRESA_A),
            facility_id=uuid.uuid4(),
            code=f"A-{uuid.uuid4().hex[:6]}",
            title="Sin nada aplicable",
            audit_type="interna",
            scope="prueba",
        )
        try:
            d = cobertura(s, vacia)
            assert d["aplicables"] == 0
            assert d["porcentaje"] is None
        finally:
            s.rollback()
            s.close()
            con.close()
            engine.dispose()
