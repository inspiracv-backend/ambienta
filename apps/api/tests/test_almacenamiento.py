"""El puente hacia el almacenamiento de archivos (RF-110, ADR-005).

Backblaze B2 por su API compatible con S3.

## Lo que estas pruebas protegen

**Row Level Security no cubre el almacenamiento de objetos.** ADR-005 lo marca
como riesgo y tiene razon: Postgres no sabe nada de un bucket. Un enlace
firmado es una credencial temporal, y quien la tenga baja el archivo sin pasar
por la base.

Las dos reglas que sostienen el aislamiento aca son:

1. **La ruta del objeto lleva el `tenant_id` adelante**, para que una llave de
   aplicacion pueda acotarse por empresa el dia que haga falta.
2. **El enlace se emite despues de leer la fila con la sesion del tenant.** Si
   RLS no ve el documento, no hay URL.

Las de `TestNoSeSaleDelPrefijo` son las que importan: firmar un enlace se ve
funcionando; impedir que apunte a la carpeta de otro, no.

## Sin red

Ninguna prueba llama a Backblaze. Lo que se comprueba es **la forma de la
clave, las validaciones y las guardas del router** — que es donde puede haber
un error nuestro. Que B2 acepte una firma v4 no es algo que podamos arreglar
nosotros, y una prueba que dependa de su disponibilidad se pone roja cuando
ellos tienen mantenimiento.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from app.services import almacenamiento as alm

EMPRESA_A = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EMPRESA_B = uuid.UUID("a0000000-0000-0000-0000-000000000002")
DOC = uuid.UUID("b0000000-0000-0000-0000-00000000abcd")
URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ambienta_app:ambienta_app_dev@localhost:5432/ambienta",
)


class TestLaClaveLlevaLaEmpresa:
    """La regla que permite acotar una llave de B2 por empresa."""

    def test_el_tenant_va_primero(self) -> None:
        clave = alm.clave_de(EMPRESA_A, DOC, 1, "PR-07.pdf")

        assert clave.startswith(f"tenants/{EMPRESA_A}/")

    def test_dos_empresas_no_comparten_prefijo(self) -> None:
        a = alm.clave_de(EMPRESA_A, DOC, 1, "PR-07.pdf")
        b = alm.clave_de(EMPRESA_B, DOC, 1, "PR-07.pdf")

        assert not a.startswith(f"tenants/{EMPRESA_B}/")
        assert not b.startswith(f"tenants/{EMPRESA_A}/")

    def test_la_revision_va_en_la_ruta(self) -> None:
        """Para que dos revisiones no se pisen.

        El bucket esta en "Keep all versions", pero depender de eso es depender
        de una opcion de consola que alguien puede cambiar. Con la version en la
        clave son dos objetos distintos y punto.
        """
        v1 = alm.clave_de(EMPRESA_A, DOC, 1, "PR-07.pdf")
        v2 = alm.clave_de(EMPRESA_A, DOC, 2, "PR-07.pdf")

        assert v1 != v2

    def test_conserva_el_nombre_original(self) -> None:
        """Es lo que la persona reconoce al descargarlo."""
        clave = alm.clave_de(EMPRESA_A, DOC, 1, "PR-07 Manejo de Residuos.pdf")

        assert clave.endswith("PR-07 Manejo de Residuos.pdf")


class TestNoSeSaleDelPrefijo:
    """**Lo que hay que proteger.** Un `../` en el nombre escribiria fuera."""

    @pytest.mark.parametrize(
        "nombre",
        [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config",
            "carpeta/subcarpeta/archivo.pdf",
            "....//....//escape.pdf",
        ],
    )
    def test_ningun_nombre_saca_la_clave_de_su_carpeta(self, nombre: str) -> None:
        clave = alm.clave_de(EMPRESA_A, DOC, 1, nombre)

        esperado = f"tenants/{EMPRESA_A}/documents/{DOC}/v1/"
        assert clave.startswith(esperado)
        # Y no queda ningun `..` que un cliente pueda resolver.
        assert ".." not in clave

    def test_un_nombre_vacio_no_deja_la_clave_a_medias(self) -> None:
        """Sin esto la clave terminaria en `/`, que en S3 es una carpeta."""
        clave = alm.clave_de(EMPRESA_A, DOC, 1, "   ")

        assert not clave.endswith("/")


class TestQueSeAcepta:
    def test_un_pdf_pasa(self) -> None:
        alm.validar_archivo(nombre="a.pdf", mime="application/pdf", tamano=1024)

    def test_un_ejecutable_no(self) -> None:
        """Lista blanca y no negra: una negra hay que ir ampliandola cada vez
        que aparece algo nuevo, y mientras tanto lo nuevo pasa."""
        with pytest.raises(alm.ArchivoRechazado):
            alm.validar_archivo(
                nombre="virus.exe", mime="application/x-msdownload", tamano=1024
            )

    def test_un_archivo_vacio_no(self) -> None:
        with pytest.raises(alm.ArchivoRechazado):
            alm.validar_archivo(nombre="a.pdf", mime="application/pdf", tamano=0)

    def test_pasado_el_tope_no(self) -> None:
        with pytest.raises(alm.ArchivoRechazado) as exc:
            alm.validar_archivo(
                nombre="a.pdf", mime="application/pdf", tamano=alm.TAMANO_MAXIMO + 1
            )

        # El mensaje dice el limite: "demasiado grande" obliga a adivinar.
        assert "MB" in str(exc.value)

    def test_justo_en_el_tope_si(self) -> None:
        """El limite es inclusivo. Un `>=` de mas rechaza el caso del borde."""
        alm.validar_archivo(
            nombre="a.pdf", mime="application/pdf", tamano=alm.TAMANO_MAXIMO
        )


class TestSinCredencialesNoSeInventaNada:
    def test_pedir_un_enlace_falla_con_un_mensaje_claro(self, monkeypatch) -> None:
        """**No se cae a disco local.**

        Guardar en el disco del servidor sin que nadie lo haya decidido produce
        archivos sin respaldo que se pierden en el primer redespliegue, y la
        empresa los cree guardados. Es la misma decision que
        `TOKEN_INVITADO_SECRETO`: sin configuracion, se falla.
        """
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "storage_key", "", raising=False)

        with pytest.raises(alm.SinConfigurar) as exc:
            alm.url_para_subir(
                tenant_id=EMPRESA_A,
                document_id=DOC,
                version_no=1,
                nombre="a.pdf",
                mime="application/pdf",
            )

        assert "STORAGE_" in str(exc.value)

    def test_esta_configurado_dice_la_verdad(self, monkeypatch) -> None:
        """La pantalla lo usa para no ofrecer subir en vano."""
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "storage_key", "", raising=False)
        assert alm.esta_configurado() is False


class TestLosPlazos:
    def test_la_descarga_expira_antes_que_la_subida(self) -> None:
        """ADR-005 pide expiracion corta tambien en descarga, y ahi importa mas:
        el enlace de descarga da acceso al contenido."""
        assert alm.VIGENCIA_DESCARGA < alm.VIGENCIA_SUBIDA

    def test_ninguno_dura_mas_de_media_hora(self) -> None:
        """Mas tiempo es mas ventana para que un enlace filtrado siga sirviendo."""
        assert alm.VIGENCIA_SUBIDA.total_seconds() <= 1800
        assert alm.VIGENCIA_DESCARGA.total_seconds() <= 1800


# ── Por la API, que es por donde entra el dano ───────────────────────────

@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import SessionLocal
    from app.main import app

    monkeypatch.setattr(get_settings(), "clerk_jwks_url", "", raising=False)
    original = SessionLocal.kw.get("bind")
    motor = create_engine(URL)
    SessionLocal.configure(bind=motor)
    try:
        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original)
        motor.dispose()


@pytest.fixture
def documento():
    """Un documento confirmado de la empresa A. Se borra al terminar."""
    admin = create_engine(
        os.getenv(
            "DATABASE_ADMIN_URL",
            "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
        )
    )
    codigo = f"ALM-{uuid.uuid4().hex[:8].upper()}"
    with admin.begin() as c:
        did = c.execute(
            text(
                "INSERT INTO documents (tenant_id, document_type, code, title) "
                "VALUES (:t, 'procedimiento', :c, 'Prueba de almacenamiento') "
                "RETURNING id"
            ),
            {"t": str(EMPRESA_A), "c": codigo},
        ).scalar_one()

    yield did

    with admin.begin() as c:
        c.execute(text("DELETE FROM document_versions WHERE document_id = :d"), {"d": did})
        c.execute(text("DELETE FROM documents WHERE id = :d"), {"d": did})
    admin.dispose()


class TestElRouterComprueba:
    A = {"X-Tenant-Id": str(EMPRESA_A)}
    B = {"X-Tenant-Id": str(EMPRESA_B)}

    def _pedir(self, cliente, doc, headers, **extra):
        cuerpo = {
            "file_name": "PR-07.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            **extra,
        }
        return cliente.post(f"/api/v1/documents/{doc}/upload-url", headers=headers, json=cuerpo)

    def test_un_documento_de_otra_empresa_responde_404(self, cliente, documento) -> None:
        """**La comprobacion que evita firmar contra la carpeta ajena.**

        404 y no 403: RLS hace que ni siquiera se vea, asi que la API nunca
        confirma que ese identificador exista en otro lado.
        """
        r = self._pedir(cliente, documento, self.B)

        assert r.status_code == 404, r.text

    def test_un_documento_inventado_responde_404_IGUAL(self, cliente) -> None:
        """Mismo codigo que el ajeno: distinguirlos seria un oraculo."""
        r = self._pedir(cliente, uuid.uuid4(), self.B)

        assert r.status_code == 404

    def test_un_ejecutable_se_rechaza_antes_de_firmar(self, cliente, documento) -> None:
        r = self._pedir(
            cliente, documento, self.A, file_name="x.exe", mime_type="application/x-msdownload"
        )

        assert r.status_code == 422, r.text

    def test_sin_credenciales_responde_503_y_no_500(self, cliente, documento, monkeypatch) -> None:
        """Un 500 se lee como "el sistema esta roto"; un 503 con mensaje dice
        que falta configurar algo."""
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "storage_key", "", raising=False)

        r = self._pedir(cliente, documento, self.A)

        assert r.status_code == 503, r.text
        assert "STORAGE_" in r.json()["detail"]

    def test_confirmar_con_una_clave_de_otra_carpeta_se_rechaza(
        self, cliente, documento
    ) -> None:
        """**El agujero que quedaria sin esta guarda.**

        Sin comprobar el prefijo, alguien podria confirmar una subida apuntando
        a la clave de otra empresa y quedarse con una revision que la descarga —
        el enlace de descarga se emite sobre la clave guardada.
        """
        ajena = alm.clave_de(EMPRESA_B, uuid.uuid4(), 1, "robado.pdf")

        r = cliente.post(
            f"/api/v1/documents/{documento}/confirm-upload",
            headers=self.A,
            json={"storage_key": ajena, "file_name": "robado.pdf"},
        )

        assert r.status_code == 422, r.text
        assert "no corresponde" in r.json()["detail"]

    def test_confirmar_con_la_clave_de_OTRO_documento_propio_tampoco(
        self, cliente, documento
    ) -> None:
        """La misma empresa, pero otro documento. El prefijo lleva los dos."""
        otra = alm.clave_de(EMPRESA_A, uuid.uuid4(), 1, "otro.pdf")

        r = cliente.post(
            f"/api/v1/documents/{documento}/confirm-upload",
            headers=self.A,
            json={"storage_key": otra, "file_name": "otro.pdf"},
        )

        assert r.status_code == 422, r.text

    def test_descargar_una_revision_de_otro_documento_responde_404(
        self, cliente, documento
    ) -> None:
        """Anidar la ruta no ata al hijo con el padre por si solo."""
        r = cliente.get(
            f"/api/v1/documents/{documento}/versions/{uuid.uuid4()}/download-url",
            headers=self.A,
        )

        assert r.status_code == 404

    def test_una_revision_REAL_de_otro_documento_tampoco_se_descarga(
        self, cliente, documento
    ) -> None:
        """**La comprobacion que la mutacion delato.**

        La primera version de esta prueba usaba un id inventado, asi que la
        atrapaba el `is None` y el `document_id != document_id` sobrevivia sin
        que nada fallara. Hace falta una revision **que exista y sea de otro
        documento**.

        Sin esa comprobacion, anidar la ruta seria decorativo: cualquiera con
        el id de una revision podria pedir su enlace de descarga colgandola de
        un documento suyo.
        """
        admin = create_engine(
            os.getenv(
                "DATABASE_ADMIN_URL",
                "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
            )
        )
        codigo = f"ALM-{uuid.uuid4().hex[:8].upper()}"
        with admin.begin() as c:
            otro = c.execute(
                text(
                    "INSERT INTO documents (tenant_id, document_type, code, title) "
                    "VALUES (:t, 'procedimiento', :c, 'Otro documento') RETURNING id"
                ),
                {"t": str(EMPRESA_A), "c": codigo},
            ).scalar_one()
            ajena = c.execute(
                text(
                    "INSERT INTO document_versions (tenant_id, document_id, version_no, "
                    "storage_provider, storage_key, file_name, mime_type, size_bytes) "
                    "VALUES (:t, :d, 1, 'backblaze', :k, 'otro.pdf', 'application/pdf', 10) "
                    "RETURNING id"
                ),
                {"t": str(EMPRESA_A), "d": otro, "k": f"tenants/{EMPRESA_A}/x/v1/otro.pdf"},
            ).scalar_one()

        try:
            r = cliente.get(
                f"/api/v1/documents/{documento}/versions/{ajena}/download-url",
                headers=self.A,
            )
            assert r.status_code == 404, r.text
        finally:
            with admin.begin() as c:
                c.execute(text("DELETE FROM document_versions WHERE id = :i"), {"i": ajena})
                c.execute(text("DELETE FROM documents WHERE id = :d"), {"d": otro})
            admin.dispose()


class TestLaProximaVersion:
    def test_se_mira_el_maximo_y_no_la_cantidad(self, cliente, documento) -> None:
        """Contar filas se rompe con cualquier hueco en la numeracion.

        Se comprueba por el efecto observable: con una revision numero 7, la
        siguiente tiene que ser la 8 y no la 2.
        """
        admin = create_engine(
            os.getenv(
                "DATABASE_ADMIN_URL",
                "postgresql+psycopg://ambienta:ambienta_dev@localhost:5432/ambienta",
            )
        )
        with admin.begin() as c:
            c.execute(
                text(
                    "INSERT INTO document_versions (tenant_id, document_id, version_no, "
                    "storage_provider, storage_key, file_name, mime_type, size_bytes) "
                    "VALUES (:t, :d, 7, 'backblaze', :k, 'v7.pdf', 'application/pdf', 10)"
                ),
                {"t": str(EMPRESA_A), "d": documento, "k": f"tenants/{EMPRESA_A}/x/v7/a.pdf"},
            )
        admin.dispose()

        from app.routers.documents import _proxima_version
        from app.db import SessionLocal

        s = SessionLocal()
        try:
            s.execute(text("SET LOCAL ROLE ambienta_app"))
            s.execute(
                text("SELECT set_config('ambienta.tenant_id', :t, true)"),
                {"t": str(EMPRESA_A)},
            )
            assert _proxima_version(s, documento) == 8
        finally:
            s.rollback()
            s.close()
