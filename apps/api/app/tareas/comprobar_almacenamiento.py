"""Comprueba de punta a punta que el almacenamiento funciona.

    python -m app.tareas.comprobar_almacenamiento

**Sube un archivo de prueba, lo baja, compara el contenido y lo borra.** Es lo
unico que demuestra que las credenciales sirven: que `boto3` construya una URL
firmada no prueba nada — la firma se genera igual con una clave equivocada y
falla recien al usarla, que es el peor momento para enterarse.

Las pruebas de `test_almacenamiento.py` **no llaman a Backblaze a proposito**:
comprueban la forma de la clave y las guardas del router, que es donde puede
haber un error nuestro. Que B2 acepte una firma no es algo que podamos
arreglar, y una prueba que dependa de su disponibilidad se pone roja cuando
ellos tienen mantenimiento. Esto se corre a mano, una vez, al configurar.
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
import uuid

from ..services import almacenamiento as alm

#: Una empresa que no existe. El objeto de prueba no debe caer en la carpeta de
#: ninguna empresa real, ni siquiera por un minuto.
EMPRESA_DE_PRUEBA = uuid.UUID("00000000-0000-0000-0000-0000000000ff")

CONTENIDO = b"Ambienta: comprobacion del puente de almacenamiento.\n"


def _paso(n: int, texto: str) -> None:
    print(f"  {n}. {texto}")


def main() -> int:
    print("\nComprobando el puente hacia el almacenamiento\n")

    if not alm.esta_configurado():
        print("  NO CONFIGURADO.")
        print("  Faltan STORAGE_ENDPOINT, STORAGE_BUCKET, STORAGE_KEY_ID o")
        print("  STORAGE_KEY en el `.env`. Ver `.env.example` para que va en cada una.")
        return 1

    doc = uuid.uuid4()
    nombre = "comprobacion-ambienta.txt"

    try:
        _paso(1, "pidiendo un enlace de subida...")
        subida = alm.url_para_subir(
            tenant_id=EMPRESA_DE_PRUEBA,
            document_id=doc,
            version_no=1,
            nombre=nombre,
            mime="text/plain",
        )
        print(f"     clave: {subida.clave}")

        _paso(2, "subiendo el archivo de prueba...")
        peticion = urllib.request.Request(
            subida.url, data=CONTENIDO, method="PUT", headers=subida.cabeceras
        )
        with urllib.request.urlopen(peticion, timeout=30) as r:
            print(f"     respondio {r.status}")

        _paso(3, "confirmando que llego...")
        real = alm.confirmar_subida(clave=subida.clave)
        print(f"     {real['size_bytes']} bytes · tipo {real['mime_type']}")
        if real["size_bytes"] != len(CONTENIDO):
            print(
                f"     AVISO: se subieron {len(CONTENIDO)} bytes y el bucket "
                f"reporta {real['size_bytes']}."
            )
            return 1

        _paso(4, "pidiendo un enlace de descarga y bajandolo...")
        descarga = alm.url_para_descargar(clave=subida.clave, nombre=nombre)
        with urllib.request.urlopen(descarga.url, timeout=30) as r:
            bajado = r.read()

        if bajado != CONTENIDO:
            print("     EL CONTENIDO NO COINCIDE. Algo se corrompio en el camino.")
            return 1
        print("     el contenido coincide")

        _paso(5, "borrando el archivo de prueba...")
        cliente = alm._cliente()
        from ..config import get_settings

        cliente.delete_object(Bucket=get_settings().storage_bucket, Key=subida.clave)
        print("     borrado")

        print("\n  El puente funciona. La subida de documentos ya se puede usar.\n")
        return 0

    except alm.SinConfigurar as exc:
        print(f"\n  NO CONFIGURADO: {exc}\n")
        return 1
    except urllib.error.HTTPError as exc:
        # El caso mas comun: credenciales o nombre de bucket equivocados. El
        # cuerpo de la respuesta de B2 dice cual de los dos, y vale mas que el
        # codigo suelto.
        cuerpo = exc.read().decode("utf-8", "replace")[:400]
        print(f"\n  FALLO con HTTP {exc.code}.")
        print(f"  {cuerpo}\n")
        print("  Lo que suele ser:")
        print("   - 403: la llave no tiene permiso sobre ESTE bucket, o es de otro.")
        print("   - 404: STORAGE_BUCKET tiene el **ID** en vez del **nombre**.")
        print("   - 401: STORAGE_KEY mal copiada (se muestra una sola vez).")
        return 1
    except Exception as exc:  # pragma: no cover - diagnostico
        print(f"\n  FALLO: {type(exc).__name__}: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
