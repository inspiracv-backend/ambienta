"""El viaje completo contra Backblaze **de verdad** (RF-110, ADR-005).

## Por que esto existe aparte

`test_almacenamiento.py` no llama a Backblaze, y lo dice: comprueba la forma de
la clave, las validaciones y las guardas del router — lo que puede fallar por
un error nuestro. Esa decision sigue siendo la correcta para la suite de
siempre: una prueba que dependa de la disponibilidad de B2 se pone roja cuando
ellos tienen mantenimiento, y entonces nadie la mira.

Pero deja **sin comprobar** justo lo que no es teoria nuestra:

- que el `Content-Type` viaje firmado de verdad, y no solo en los `Params` que
  le pasamos a botocore;
- que el bucket **no sea publico**, que es lo unico que hay entre un enlace
  firmado y cualquiera con la URL;
- que la firma sea v4 y B2 la acepte (con v2 el enlace se genera igual y falla
  recien al usarlo, que es el peor momento para enterarse);
- que `confirmar_subida()` lea el tamano real y no el declarado.

Hasta que se escribio este archivo, nada de eso se habia ejecutado nunca contra
el bucket. Estaba escrito y razonado, que no es lo mismo que probado.

## Como se corre

Es **opt-in a proposito**: gasta cuota, necesita credenciales reales y escribe
en el bucket. No corre en CI ni en la suite de siempre.

    PRUEBA_B2_REAL=1 python -m pytest tests/test_almacenamiento_contra_b2.py -v

Sin esa variable se salta. **Un salto aca no significa que el almacenamiento
este comprobado** — significa que nadie lo comprobo en esta corrida. Si vas a
tocar `services/almacenamiento.py`, corre esto antes de dar por bueno el
cambio.

## Lo que deja atras

Nada: cada objeto que crea queda anotado y se borra en el teardown, tambien si
la prueba falla. Van bajo un `tenant_id` de prueba (`...0000b2`) que no le
pertenece a ninguna empresa real, asi que aunque un borrado fallara no se pisa
nada de nadie.
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest

from app.config import get_settings
from app.services import almacenamiento as alm

#: Un tenant que no existe en la base. Lo unico que hace es dar un prefijo
#: propio dentro del bucket, para que estas pruebas nunca escriban dentro de la
#: carpeta de una empresa real.
TENANT_DE_PRUEBA = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
DOC_DE_PRUEBA = uuid.UUID("00000000-0000-0000-0000-0000000000cc")

CONTENIDO = b"prueba de ida y vuelta contra B2\n" * 40
MIME = "application/pdf"
NOMBRE = "informe.pdf"


def _por_que_no_corre() -> str | None:
    """El motivo del salto, en palabras, o None si hay que correr."""
    if os.getenv("PRUEBA_B2_REAL") != "1":
        return (
            "opt-in: habla con Backblaze de verdad. "
            "Corre con PRUEBA_B2_REAL=1 (esto NO comprueba el almacenamiento)"
        )
    if not alm.esta_configurado():
        return (
            "PRUEBA_B2_REAL=1 pero faltan credenciales: STORAGE_ENDPOINT, "
            "STORAGE_BUCKET, STORAGE_KEY_ID y STORAGE_KEY en el .env"
        )
    return None


pytestmark = [
    pytest.mark.b2_real,
    pytest.mark.skipif(_por_que_no_corre() is not None, reason=_por_que_no_corre() or ""),
]


@pytest.fixture(scope="module")
def borrar_al_final():
    """Anota claves y las borra al terminar, pase lo que pase con las pruebas."""
    claves: list[str] = []
    yield claves.append

    cliente = alm._cliente()
    bucket = get_settings().storage_bucket
    for clave in claves:
        try:
            cliente.delete_object(Bucket=bucket, Key=clave)
        except Exception as exc:  # pragma: no cover - limpieza, no asercion
            print(f"AVISO: quedo sin borrar {clave!r} en {bucket}: {exc}")


@pytest.fixture(scope="module")
def subido(borrar_al_final):
    """Sube el archivo una vez y devuelve el enlace usado.

    Se hace en un fixture y no en una prueba para que las demas no dependan del
    orden en que pytest las corra.
    """
    enlace = alm.url_para_subir(
        tenant_id=TENANT_DE_PRUEBA,
        document_id=DOC_DE_PRUEBA,
        version_no=1,
        nombre=NOMBRE,
        mime=MIME,
    )
    borrar_al_final(enlace.clave)

    r = httpx.put(enlace.url, content=CONTENIDO, headers=enlace.cabeceras, timeout=60)
    assert r.status_code in (200, 201), (
        f"B2 rechazo la subida con HTTP {r.status_code}. "
        f"Suele ser la firma o el endpoint. Respuesta: {r.text[:400]}"
    )
    return enlace


class TestElArchivoLlegaYVuelve:
    """Lo minimo: que subir y bajar funcione contra el bucket real."""

    def test_la_clave_queda_bajo_el_prefijo_de_la_empresa(self, subido) -> None:
        assert subido.clave.startswith(f"tenants/{TENANT_DE_PRUEBA}/")

    def test_confirmar_subida_ve_el_TAMANO_REAL(self, subido) -> None:
        # No el declarado por el navegador: ese es justamente el que no vale.
        assert alm.confirmar_subida(clave=subido.clave)["size_bytes"] == len(CONTENIDO)

    def test_confirmar_subida_devuelve_el_mime_y_un_etag(self, subido) -> None:
        datos = alm.confirmar_subida(clave=subido.clave)
        assert datos["mime_type"] == MIME
        assert datos["etag"]

    def test_los_bytes_vuelven_identicos(self, subido) -> None:
        enlace = alm.url_para_descargar(clave=subido.clave, nombre=NOMBRE)
        r = httpx.get(enlace.url, timeout=60)
        assert r.status_code == 200, r.text[:400]
        assert r.content == CONTENIDO

    def test_se_baja_con_el_nombre_original_y_no_con_la_ruta(self, subido) -> None:
        enlace = alm.url_para_descargar(clave=subido.clave, nombre=NOMBRE)
        r = httpx.get(enlace.url, timeout=60)
        assert f'filename="{NOMBRE}"' in r.headers.get("content-disposition", "")


class TestLoQueNoPodiamosComprobarSinRed:
    """Las tres que solo B2 puede responder. Son el motivo de este archivo."""

    def test_el_BUCKET_NO_ES_PUBLICO(self, subido) -> None:
        """Sin esto, un enlace firmado no protege nada: basta con la URL.

        Es la unica prueba de todo el proyecto que lo comprueba, y no se puede
        deducir del codigo: depende de como este configurado el bucket en la
        consola de Backblaze, que nadie versiona.
        """
        s = get_settings()
        sin_firmar = f"https://{s.storage_endpoint}/{s.storage_bucket}/{subido.clave}"

        r = httpx.get(sin_firmar, timeout=60)

        assert r.status_code >= 400, (
            f"El bucket {s.storage_bucket!r} sirve el archivo SIN FIRMA "
            f"(HTTP {r.status_code}). Cualquiera con la URL baja documentos de "
            "cualquier empresa. Ponelo privado en la consola de Backblaze."
        )

    def test_con_otro_content_type_del_firmado_B2_rechaza(self, borrar_al_final) -> None:
        """El `Content-Type` va dentro de la firma, no es una sugerencia.

        Si no fuera asi, el enlace que se emite para subir un PDF serviria para
        subir un `.html` con ese nombre — y despues alguien lo abre.
        """
        enlace = alm.url_para_subir(
            tenant_id=TENANT_DE_PRUEBA,
            document_id=DOC_DE_PRUEBA,
            version_no=2,
            nombre=NOMBRE,
            mime=MIME,
        )
        borrar_al_final(enlace.clave)

        r = httpx.put(
            enlace.url, content=b"<html></html>", headers={"Content-Type": "text/html"}, timeout=60
        )

        assert r.status_code >= 400, (
            f"B2 acepto un text/html con un enlace firmado para {MIME} "
            f"(HTTP {r.status_code}). El Content-Type no esta viajando firmado."
        )

    def test_confirmar_una_clave_que_no_existe_FALLA(self) -> None:
        """Que no se pueda dar por buena una subida que nunca llego.

        Con enlaces firmados el navegador habla directo con el bucket: si el
        `PUT` se corta a la mitad, esta es la unica forma de enterarse. Una fila
        de `document_versions` apuntando a un objeto que no existe es un
        documento que la empresa cree tener.
        """
        inexistente = f"tenants/{TENANT_DE_PRUEBA}/documents/{DOC_DE_PRUEBA}/v99/no-existe.pdf"

        with pytest.raises(alm.ErrorDeAlmacenamiento):
            alm.confirmar_subida(clave=inexistente)


class TestElHashLoVerificaElBucket:
    """El hash del contenido, comprobado por B2 y no afirmado por nosotros.

    ## Por que esto existe

    `document_versions.checksum_sha256` existia desde el principio y estaba
    **vacia en el 100 % de las filas**: `confirmar_subida` recibia el `ETag` de
    B2 y lo descartaba. Una revision documental sin hash no se puede verificar
    despues, que es justo lo que un auditor querria hacer con la evidencia.

    ## La distincion que importa

    Un hash **afirmado** —el que el navegador dice que tiene el archivo— sirve
    para detectar corrupcion en el trayecto y **no sirve para nada si quien
    sube miente**. Un hash **verificado** viaja dentro de la firma: el bucket
    comprueba el contenido y rechaza la subida si no corresponde, asi que lo
    que se guarda despues es un hecho.

    `test_B2_RECHAZA_un_contenido_que_no_corresponde` es la prueba que sostiene
    toda la diferencia. Si algun dia se pusiera verde por el motivo equivocado
    —por ejemplo, porque se dejo de mandar el hash en la firma— la de al lado,
    que comprueba que el hash vuelve, se pondria roja.
    """

    CONTENIDO = b"acta de inspeccion ambiental\n" * 40

    @property
    def sha(self) -> str:
        import hashlib

        return hashlib.sha256(self.CONTENIDO).hexdigest()

    def test_el_enlace_lleva_la_cabecera_del_hash(self, borrar_al_final) -> None:
        enlace = alm.url_para_subir(
            tenant_id=TENANT_DE_PRUEBA, document_id=DOC_DE_PRUEBA, version_no=10,
            nombre=NOMBRE, mime=MIME, sha256_hex=self.sha,
        )
        borrar_al_final(enlace.clave)
        assert "x-amz-checksum-sha256" in enlace.cabeceras

    def test_el_bucket_devuelve_el_MISMO_hash(self, borrar_al_final) -> None:
        enlace = alm.url_para_subir(
            tenant_id=TENANT_DE_PRUEBA, document_id=DOC_DE_PRUEBA, version_no=11,
            nombre=NOMBRE, mime=MIME, sha256_hex=self.sha,
        )
        borrar_al_final(enlace.clave)
        r = httpx.put(enlace.url, content=self.CONTENIDO, headers=enlace.cabeceras, timeout=60)
        assert r.status_code == 200, r.text[:300]

        assert alm.confirmar_subida(clave=enlace.clave)["checksum_sha256"] == self.sha

    def test_B2_RECHAZA_un_contenido_que_no_corresponde(self, borrar_al_final) -> None:
        """**La prueba que le da sentido al hash.**

        Sin esto, el checksum guardado seria lo que declaro el navegador y no
        probaria nada sobre el archivo que de verdad esta en el bucket.
        """
        enlace = alm.url_para_subir(
            tenant_id=TENANT_DE_PRUEBA, document_id=DOC_DE_PRUEBA, version_no=12,
            nombre=NOMBRE, mime=MIME, sha256_hex=self.sha,
        )
        borrar_al_final(enlace.clave)

        r = httpx.put(enlace.url, content=b"otro archivo distinto",
                      headers=enlace.cabeceras, timeout=60)

        assert r.status_code >= 400, (
            f"B2 acepto un contenido que NO corresponde al hash firmado "
            f"(HTTP {r.status_code}). El checksum ya no prueba nada."
        )
        with pytest.raises(alm.ErrorDeAlmacenamiento):
            alm.confirmar_subida(clave=enlace.clave)

    def test_sin_hash_el_checksum_queda_VACIO_y_no_con_el_ETag(self, borrar_al_final) -> None:
        """El ETag de B2 es **MD5** —medido—, asi que ponerlo en una columna
        llamada `checksum_sha256` seria guardar una cosa diciendo que es otra."""
        enlace = alm.url_para_subir(
            tenant_id=TENANT_DE_PRUEBA, document_id=DOC_DE_PRUEBA, version_no=13,
            nombre=NOMBRE, mime=MIME,
        )
        borrar_al_final(enlace.clave)
        httpx.put(enlace.url, content=self.CONTENIDO, headers=enlace.cabeceras, timeout=60)

        datos = alm.confirmar_subida(clave=enlace.clave)
        assert datos["checksum_sha256"] is None
        assert datos["size_bytes"] == len(self.CONTENIDO)
