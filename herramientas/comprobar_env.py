"""Comprueba el `.env` **antes** de desplegar, sin imprimir un solo secreto.

    python herramientas/comprobar_env.py              # el .env de la raiz
    python herramientas/comprobar_env.py --tunel      # ademas, lo del tunel
    python herramientas/comprobar_env.py --archivo otro.env

## Por que existe

El compose de produccion corta el arranque con `:?` cuando falta una variable
obligatoria, y eso es lo correcto — pero las nombra **de a una**: se arregla la
primera, se vuelve a correr, aparece la segunda. Con ocho faltando, eso son
ocho intentos, y el dia del despliegue se hace de noche.

Esto las dice **todas juntas**, en segundos, y revisa ademas lo que `:?` no
puede ver: valores que quedaron con el marcador `CAMBIAR` del ejemplo, la
contrasena de desarrollo que `db/07` publica en el repositorio, un remitente de
correo sin dominio propio, un bucket donde se escribio el ID en vez del nombre.

## Lo que NO hace

**No imprime valores.** Dice si una variable esta, si parece tener la forma
correcta y nada mas. Un comprobador que vuelca el `.env` a la pantalla para
"ayudar a revisar" es una filtracion con buenas intenciones: queda en el
historial del terminal, en la captura que se pega en un chat y en el log de CI.

**No se conecta a nada.** Que las credenciales de Clerk, Resend o Backblaze
sirvan de verdad se comprueba con las tareas que existen para eso
(`comprobar_correo`, `comprobar_almacenamiento`), y eso va despues de levantar.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: Obligatorias en produccion: el compose las declara con `:?` y sin ellas no
#: arranca. El motivo de cada una es el que esta en `.env.example`.
OBLIGATORIAS = {
    "DOMAIN_WEB": "el dominio del frontend",
    "DOMAIN_API": "el dominio de la API",
    "ACME_EMAIL": "el correo al que Let's Encrypt avisa de certificados",
    "POSTGRES_USER": "el dueno de la base",
    "POSTGRES_DB": "el nombre de la base",
    "POSTGRES_PASSWORD": "la contrasena del dueno de la base",
    "APP_DB_PASSWORD": "la contrasena de `ambienta_app`, el rol con el que se conecta la API",
    "CLERK_JWKS_URL": "sin ella la API queda sin autenticacion",
    "CLERK_ISSUER": "impide que un JWT de otra instancia sirva contra esta API",
    "CLERK_WEBHOOK_SECRET": "sin el, quien entra por SSO no tiene fila en `users`",
    "CLERK_SECRET_KEY": "la necesitan la API y **tambien** el servidor de Next",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "sin ella el frontend no puede iniciar sesion",
    "TOKEN_INVITADO_SECRETO": "sin el, el ingreso de invitados responde 503",
    "STORAGE_ENDPOINT": "el endpoint del almacenamiento, sin `https://`",
    "STORAGE_BUCKET": "el **nombre** del bucket, no su ID",
    "STORAGE_KEY_ID": "el keyID del almacenamiento",
    "STORAGE_KEY": "la llave de aplicacion del almacenamiento",
    "RESEND_API_KEY": "sin ella los avisos de vencimiento no salen",
    "CORREO_REMITENTE": "el remitente, con dominio verificado en Resend",
}

#: Solo para el camino del tunel (`docker-compose.tunel.yml`).
DEL_TUNEL = {
    "TUNNEL_TOKEN": "lo da el panel de Cloudflare al crear el tunel",
}

#: Opcionales de verdad: su ausencia degrada algo acotado y nada mas.
OPCIONALES = {
    "BCN_API_KEY": "sin ella la ingesta trae metadatos y relaciones, y el texto de los articulos queda vacio",
    "CORREO_RESPONDER_A": "vacio = las respuestas van al remitente",
    "NEXT_PUBLIC_EMPRESA_INVITADO": "sin ella /acceso-invitado exige `?empresa=<uuid>`",
    "DATABASE_ADMIN_URL": "el compose de produccion la arma solo; hace falta solo fuera de compose",
    "HORA_AVISOS": "por defecto 07",
    "HORA_RESPALDOS": "por defecto 02",
}

PROBLEMAS: list[str] = []
AVISOS: list[str] = []


def leer(archivo: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def revisar_formas(v: dict[str, str]) -> None:
    """Lo que `:?` no puede ver: una variable presente con un valor que no sirve."""
    # 1. Marcadores del ejemplo que nadie reemplazo.
    for clave, valor in v.items():
        if "CAMBIAR" in valor.upper():
            PROBLEMAS.append(f"{clave} todavia trae el marcador del ejemplo")

    # 2. La contrasena que `db/07` publica en el repositorio. El script de init
    #    tambien se niega, pero enterarse ahora es mejor que a mitad del `up`.
    if v.get("APP_DB_PASSWORD") == "ambienta_app_dev":
        PROBLEMAS.append(
            "APP_DB_PASSWORD es la contrasena de desarrollo, que esta escrita "
            "en db/07_rol_aplicacion.sql en un repositorio publico"
        )

    # 3. Dos contrasenas distintas. Reusar una convierte una filtracion en dos.
    if (
        v.get("POSTGRES_PASSWORD")
        and v.get("POSTGRES_PASSWORD") == v.get("APP_DB_PASSWORD")
    ):
        PROBLEMAS.append(
            "POSTGRES_PASSWORD y APP_DB_PASSWORD son iguales: el rol que no puede "
            "saltarse RLS deja de ser una barrera si comparte clave con el dueno"
        )

    # 4. Los dominios van sin esquema: el compose les pone `https://` delante.
    for clave in ("DOMAIN_WEB", "DOMAIN_API"):
        if v.get(clave, "").startswith(("http://", "https://")):
            PROBLEMAS.append(
                f"{clave} lleva esquema. Va solo el dominio: el compose arma "
                "`https://` y el del tunel `http://`"
            )

    # 5. El endpoint del almacenamiento tampoco.
    if v.get("STORAGE_ENDPOINT", "").startswith(("http://", "https://")):
        PROBLEMAS.append("STORAGE_ENDPOINT va sin `https://` (lo agrega el cliente)")

    # 6. El bucket por ID y no por nombre: responde 404 al primer archivo.
    bucket = v.get("STORAGE_BUCKET", "")
    if bucket and re.fullmatch(r"[0-9a-f]{20,}", bucket):
        PROBLEMAS.append(
            "STORAGE_BUCKET parece el ID del bucket (hexadecimal). La API de S3 "
            "usa el NOMBRE; con el ID responde 404 al subir el primer archivo"
        )

    # 7. Clerk: distinguir desarrollo de produccion sin mirar el valor.
    pk = v.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "")
    sk = v.get("CLERK_SECRET_KEY", "")
    if pk.startswith("pk_test_") or sk.startswith("sk_test_"):
        AVISOS.append(
            "Las llaves de Clerk son de **desarrollo** (`pk_test_`/`sk_test_`). "
            "Funcionan, pero muestran avisos de modo desarrollo al entrar y no "
            "corresponden a una instancia de produccion"
        )
    if pk and not pk.startswith("pk_"):
        PROBLEMAS.append("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY no tiene forma de llave de Clerk")
    if sk and not sk.startswith("sk_"):
        PROBLEMAS.append("CLERK_SECRET_KEY no tiene forma de llave secreta de Clerk")
    if pk.startswith("pk_live_") != sk.startswith("sk_live_") and pk and sk:
        PROBLEMAS.append(
            "Las dos llaves de Clerk son de instancias distintas (una live y una "
            "test): el frontend y la API no hablarian de la misma sesion"
        )

    # 8. El remitente con el dominio de pruebas de Resend solo le escribe al
    #    dueno de la cuenta: comprueba la instalacion, no avisa a un cliente.
    remitente = v.get("CORREO_REMITENTE", "")
    if "resend.dev" in remitente:
        AVISOS.append(
            "CORREO_REMITENTE usa el dominio de pruebas de Resend: solo envia a "
            "la direccion con la que se registro la cuenta. Sirve para comprobar "
            "la instalacion, no para avisarle a un cliente"
        )
    elif remitente and not re.search(r"<[^@>]+@[^@>]+>", remitente):
        AVISOS.append(
            "CORREO_REMITENTE no tiene el formato `Nombre <correo@dominio>`"
        )

    # 9. Un secreto de firma corto es un secreto adivinable.
    token = v.get("TOKEN_INVITADO_SECRETO", "")
    if token and len(token) < 32:
        PROBLEMAS.append(
            f"TOKEN_INVITADO_SECRETO mide {len(token)} caracteres. Firma las "
            "sesiones de invitado: generar uno con "
            "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"`"
        )

    # 10. El dominio del frontend y el de la API no pueden ser el mismo: Caddy
    #     enruta por `Host` y el segundo bloque del Caddyfile nunca recibiria.
    if v.get("DOMAIN_WEB") and v.get("DOMAIN_WEB") == v.get("DOMAIN_API"):
        PROBLEMAS.append("DOMAIN_WEB y DOMAIN_API son el mismo: Caddy enruta por Host")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archivo", default=str(RAIZ / ".env"))
    p.add_argument(
        "--tunel",
        action="store_true",
        help="Exige tambien lo que necesita docker-compose.tunel.yml",
    )
    args = p.parse_args()

    archivo = Path(args.archivo)
    if not archivo.exists():
        print(f"No existe {archivo}.")
        print("  cp .env.example .env   y completar lo obligatorio.")
        return 1

    valores = leer(archivo)
    exigidas = dict(OBLIGATORIAS)
    if args.tunel:
        exigidas.update(DEL_TUNEL)

    faltan = {k: v for k, v in exigidas.items() if not valores.get(k)}
    revisar_formas(valores)

    print(f"\nRevisando {archivo.name} — {len(valores)} variables definidas\n")

    if faltan:
        print(f"  FALTAN {len(faltan)} obligatorias:\n")
        for clave, porque in faltan.items():
            print(f"    · {clave:38} {porque}")
        print()

    if PROBLEMAS:
        print(f"  {len(PROBLEMAS)} con un valor que no va a funcionar:\n")
        for x in PROBLEMAS:
            print(f"    · {x}")
        print()

    if AVISOS:
        print(f"  {len(AVISOS)} aviso(s), no bloquean:\n")
        for x in AVISOS:
            print(f"    · {x}")
        print()

    sin_poner = [k for k in OPCIONALES if not valores.get(k)]
    if sin_poner:
        print(f"  Opcionales sin definir ({len(sin_poner)}), y esta bien:")
        for k in sin_poner:
            print(f"    · {k:38} {OPCIONALES[k]}")
        print()

    if faltan or PROBLEMAS:
        print("  El despliegue NO va a funcionar todavia.\n")
        return 1

    print("  Listo: el `.env` tiene lo necesario y con la forma correcta.")
    print("  Lo que esto NO comprueba: que las credenciales sirvan de verdad.")
    print("  Eso va despues de levantar, con `comprobar_correo` y")
    print("  `comprobar_almacenamiento` (runbook 4.8 y 4.9).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
