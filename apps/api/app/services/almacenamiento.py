"""El puente hacia el almacenamiento de archivos (RF-110, epica #31).

Backblaze B2 por ADR-005, hablado por su **API compatible con S3** — la misma
que usarian S3 o cualquier otro proveedor S3-compatible. Eso es deliberado: si
manana hay que mover el bucket, cambia el endpoint y nada mas.

## Lo que este modulo protege, y es lo que mas importa

**Row Level Security no cubre el almacenamiento de objetos.** ADR-005 lo marca
como riesgo y tiene razon: Postgres no sabe nada de un bucket. Un enlace
firmado es una credencial temporal, y quien la tenga baja el archivo sin pasar
por la base ni por RLS.

Por eso hay dos reglas que este modulo hace cumplir y que no se pueden
saltar desde afuera:

1. **La ruta del objeto lleva el `tenant_id` adelante.** No es cosmetico: es lo
   que permite, si algun dia hace falta, acotar una llave de aplicacion a un
   prefijo por empresa. Con las rutas mezcladas eso ya no se puede hacer sin
   mover todos los archivos.
2. **El enlace se emite solo despues de leer la fila con la sesion del
   tenant.** Si RLS no ve el documento, para esta empresa no existe, y no hay
   URL. La comprobacion vive en el router, que es quien tiene la sesion.

## Por que enlaces firmados y no un proxy por la API

Pasar el archivo por FastAPI significa que un PDF de 40 MB ocupa un worker
durante toda la subida. Con enlaces firmados el navegador habla directo con B2
y la API solo firma — que es trabajo de milisegundos.

Lo que se cede: el archivo llega a B2 sin que nosotros lo hayamos visto, asi
que **el tamano y el tipo declarados hay que verificarlos despues**, no antes.
Ver `confirmar_subida()`.

## Sin credenciales, no se inventa nada

Igual que `TOKEN_INVITADO_SECRETO`: si falta la configuracion, esto **falla con
un mensaje claro** en vez de escribir en un bucket por defecto o guardar en
disco. Un archivo que la empresa cree subido y no esta es peor que un error.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from ..config import get_settings

#: Cuanto vive un enlace de subida.
#:
#: Quince minutos: lo que tarda una persona en elegir el archivo y que suba,
#: con margen para una conexion mala. Mas tiempo es mas ventana para que un
#: enlace filtrado siga sirviendo.
VIGENCIA_SUBIDA = timedelta(minutes=15)

#: Cuanto vive un enlace de descarga.
#:
#: Cinco minutos, y **mas corto que el de subida a proposito**. Una descarga se
#: pide y se usa en el acto; una subida puede tardar. ADR-005 pide expiracion
#: corta tambien en descarga, y es donde mas importa: el enlace de descarga da
#: acceso al contenido.
VIGENCIA_DESCARGA = timedelta(minutes=5)

#: Tamano maximo por archivo, en bytes.
#:
#: 50 MB. Los documentos de un sistema de gestion son PDF y ofimatica; lo que
#: pasa de ahi suele ser un video o un escaneo sin comprimir, y aceptarlo
#: llenaria el bucket con cosas que nadie abre. Se puede subir si aparece un
#: caso real que lo justifique.
TAMANO_MAXIMO = 50 * 1024 * 1024

#: Lo que se acepta subir.
#:
#: Lista blanca y no negra: una negra hay que ir ampliandola cada vez que
#: aparece algo nuevo, y mientras tanto lo nuevo pasa. Aca lo que no esta, no
#: entra.
TIPOS_ACEPTADOS = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/jpeg",
        "image/png",
        "text/plain",
        "text/csv",
    }
)


class ErrorDeAlmacenamiento(Exception):
    """Algo impide guardar o entregar el archivo."""


class SinConfigurar(ErrorDeAlmacenamiento):
    """No hay credenciales de almacenamiento.

    **No se cae a disco local ni a un bucket por defecto.** Guardar en el disco
    del servidor sin que nadie lo haya decidido produce archivos sin respaldo
    que se pierden en el primer redespliegue, y la empresa los cree guardados.
    """


class ArchivoRechazado(ErrorDeAlmacenamiento):
    """El archivo no cumple lo que se acepta subir."""


@dataclass(frozen=True)
class EnlaceFirmado:
    """Un permiso temporal para subir o bajar un objeto concreto."""

    url: str
    #: La ruta dentro del bucket. Se guarda en `document_versions.storage_key`.
    clave: str
    #: Segundos que le quedan de vida. Va en la respuesta para que la pantalla
    #: pueda avisar en vez de dejar que falle en silencio.
    expira_en: int
    #: Cabeceras que el navegador **debe** mandar, o la firma no valida.
    cabeceras: dict[str, str]


def clave_de(tenant_id: UUID, document_id: UUID, version_no: int, nombre: str) -> str:
    """La ruta del objeto dentro del bucket.

        tenants/<tenant_id>/documents/<document_id>/v<n>/<nombre>

    **El `tenant_id` va primero y eso no es cosmetico.** Es lo que permite
    acotar una llave de aplicacion de B2 a un prefijo por empresa el dia que
    haga falta —una llave por cliente, o una para un proceso que solo debe ver
    a uno—. Con las rutas mezcladas eso ya no se puede sin mover todo.

    La version va en la ruta para que **las revisiones no se pisen**. El bucket
    esta en "Keep all versions", pero depender de eso significa depender de una
    opcion de consola que alguien puede cambiar; con la version en la clave, dos
    revisiones son dos objetos distintos y punto.

    El nombre original se conserva al final: es lo que la persona reconoce
    cuando lo descarga.
    """
    limpio = _nombre_seguro(nombre)
    return f"tenants/{tenant_id}/documents/{document_id}/v{version_no}/{limpio}"


def _nombre_seguro(nombre: str) -> str:
    """Deja el nombre en algo que no se pueda usar para salirse de la ruta.

    `../` en un nombre de archivo escribiria fuera del prefijo del tenant, que
    es exactamente lo que la clave con `tenant_id` adelante intenta impedir. No
    es teorico: es el primer intento de cualquiera que pruebe.
    """
    nombre = (nombre or "").strip().replace("\\", "/").split("/")[-1]
    nombre = nombre.replace("..", "").strip(". ")
    return nombre[:200] or "archivo"


def validar_archivo(*, nombre: str, mime: str, tamano: int) -> None:
    """Comprueba lo que se puede comprobar **antes** de firmar el enlace.

    Con enlaces firmados el archivo va directo a B2, asi que esto es lo
    declarado, no lo real. Sirve igual: corta el caso normal —alguien elige un
    `.exe` o un archivo de 800 MB— antes de gastar la subida.

    Lo que **no** garantiza: que el archivo que llegue sea el declarado. Eso se
    verifica despues, en `confirmar_subida()`.
    """
    if tamano <= 0:
        raise ArchivoRechazado("El archivo esta vacio.")
    if tamano > TAMANO_MAXIMO:
        mb = TAMANO_MAXIMO // (1024 * 1024)
        raise ArchivoRechazado(
            f"El archivo pesa {tamano / 1024 / 1024:.1f} MB y el maximo son {mb} MB."
        )
    if mime not in TIPOS_ACEPTADOS:
        raise ArchivoRechazado(
            f"No se aceptan archivos '{mime}'. Se admiten PDF, Word, Excel, "
            f"imagenes JPG/PNG y texto plano."
        )
    if not _nombre_seguro(nombre):
        raise ArchivoRechazado("El nombre del archivo no es valido.")


def _cliente() -> Any:
    """El cliente S3 apuntando a B2.

    `boto3` se importa aca dentro y no arriba **a proposito**: la API tiene que
    poder arrancar sin credenciales de almacenamiento —el resto del sistema
    funciona igual— y un import al tope obligaria a tener la libreria instalada
    para levantar cualquier endpoint.
    """
    s = get_settings()
    if not (s.storage_endpoint and s.storage_bucket and s.storage_key_id and s.storage_key):
        raise SinConfigurar(
            "El almacenamiento de archivos no esta configurado. Faltan "
            "STORAGE_ENDPOINT, STORAGE_BUCKET, STORAGE_KEY_ID o STORAGE_KEY."
        )

    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:  # pragma: no cover - entorno sin la libreria
        raise SinConfigurar(f"Falta la libreria de almacenamiento: {exc}") from exc

    return boto3.client(
        "s3",
        endpoint_url=f"https://{s.storage_endpoint}",
        aws_access_key_id=s.storage_key_id,
        aws_secret_access_key=s.storage_key,
        region_name=s.storage_region,
        # **Firma v4.** B2 la exige en su API de S3; con v2 los enlaces se
        # generan igual y fallan recien al usarlos, que es el peor momento.
        config=Config(signature_version="s3v4"),
    )


def url_para_subir(
    *, tenant_id: UUID, document_id: UUID, version_no: int, nombre: str, mime: str
) -> EnlaceFirmado:
    """Un enlace temporal para que el navegador suba el archivo directo a B2.

    **El `Content-Type` va firmado.** Si el navegador manda otro, B2 rechaza la
    subida: sin eso, el enlace firmado para un PDF serviria para subir
    cualquier cosa con ese nombre.
    """
    clave = clave_de(tenant_id, document_id, version_no, nombre)
    cliente = _cliente()
    s = get_settings()

    url = cliente.generate_presigned_url(
        "put_object",
        Params={"Bucket": s.storage_bucket, "Key": clave, "ContentType": mime},
        ExpiresIn=int(VIGENCIA_SUBIDA.total_seconds()),
        HttpMethod="PUT",
    )
    return EnlaceFirmado(
        url=url,
        clave=clave,
        expira_en=int(VIGENCIA_SUBIDA.total_seconds()),
        cabeceras={"Content-Type": mime},
    )


def url_para_descargar(*, clave: str, nombre: str) -> EnlaceFirmado:
    """Un enlace temporal de descarga.

    `ResponseContentDisposition` hace que el navegador guarde el archivo con su
    nombre original en vez de con la ruta del objeto, que es ilegible.

    **Quien llama tiene que haber comprobado que la clave es de este tenant.**
    Este modulo firma lo que le piden: la comprobacion de pertenencia vive en el
    router, que es quien tiene la sesion con RLS.
    """
    cliente = _cliente()
    s = get_settings()

    url = cliente.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": s.storage_bucket,
            "Key": clave,
            "ResponseContentDisposition": f'attachment; filename="{_nombre_seguro(nombre)}"',
        },
        ExpiresIn=int(VIGENCIA_DESCARGA.total_seconds()),
        HttpMethod="GET",
    )
    return EnlaceFirmado(
        url=url,
        clave=clave,
        expira_en=int(VIGENCIA_DESCARGA.total_seconds()),
        cabeceras={},
    )


def confirmar_subida(*, clave: str) -> dict:
    """Pregunta a B2 si el objeto llego, y con que tamano.

    **Es la unica forma de saber que la subida funciono.** Con enlaces firmados
    el navegador habla directo con el bucket: si el `PUT` falla a la mitad,
    nuestra API no se entera de nada y la fila de `document_versions` quedaria
    apuntando a un objeto que no existe. Un documento que la empresa cree subido
    y no esta es peor que un error al subirlo.

    Devuelve el tamano y el `ETag` reales — no los declarados— para que quien
    llame los guarde en vez de los que dijo el navegador.
    """
    cliente = _cliente()
    s = get_settings()

    try:
        cabecera = cliente.head_object(Bucket=s.storage_bucket, Key=clave)
    except Exception as exc:
        raise ErrorDeAlmacenamiento(
            f"El archivo no llego al almacenamiento. Volve a intentar la subida. ({exc})"
        ) from exc

    return {
        "size_bytes": int(cabecera.get("ContentLength", 0)),
        "etag": str(cabecera.get("ETag", "")).strip('"'),
        "mime_type": cabecera.get("ContentType"),
    }


def esta_configurado() -> bool:
    """Si hay credenciales. Sirve para que la pantalla no ofrezca subir en vano."""
    s = get_settings()
    return bool(
        s.storage_endpoint and s.storage_bucket and s.storage_key_id and s.storage_key
    )
