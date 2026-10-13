"""Comprueba que el camino de produccion siga siendo desplegable.

    docker compose -f docker-compose.prod.yml --env-file .env config | \
        python herramientas/verificar_despliegue.py

**Existe porque el camino de produccion se podrido en silencio durante meses.**
`docker-compose.prod.yml` se mantuvo a mano sin que nadie corriera el `up` —no
hay servidor aprovisionado— y cuando se ensayo, el 13-oct, tenia ocho fallas.
Las de abajo son las que no se ven ni desplegando: el sistema arranca, se ve
bien y falla en silencio, o deja de cumplir una garantia sin que nada lo diga.

No reemplaza al ensayo completo. Comprueba lo que se puede comprobar sin
servidor, que es lo que nadie estaba comprobando.
"""
from __future__ import annotations

import sys

import yaml

FALLAS: list[str] = []


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        FALLAS.append(mensaje)


def volumenes_de(servicio: dict) -> list[str]:
    """Los nombres de volumen que monta un servicio.

    Entiende las dos formas, y hace falta: a mano se escribe la corta
    (`respaldos:/ruta`) y **`docker compose config` normaliza a la larga**
    (`{type, source, target}`). La primera version de este verificador buscaba
    la subcadena `"respaldos:"` y dio un falso positivo contra el compose real,
    mientras el chequeo del volumen de auditoria pasaba por coincidencia de
    substring — o sea, ninguno de los dos estaba comprobando lo que decia.
    """
    nombres = []
    for v in servicio.get("volumes") or []:
        if isinstance(v, dict):
            if v.get("type") == "volume" and v.get("source"):
                nombres.append(str(v["source"]))
        elif isinstance(v, str) and ":" in v and not v.startswith((".", "/")):
            nombres.append(v.split(":", 1)[0])
    return nombres


def main() -> int:
    compose = yaml.safe_load(sys.stdin)
    servicios = compose["services"]

    def entorno(nombre: str) -> dict:
        return servicios[nombre].get("environment") or {}

    # 1. `clerkMiddleware()` corre en el servidor de Next y necesita la llave
    #    secreta en tiempo de ejecucion. Sin ella toda pantalla protegida
    #    responde 500 — y el login, que es publico, se ve perfecto.
    for s in ("api", "web"):
        exigir(
            "CLERK_SECRET_KEY" in entorno(s),
            f"el servicio «{s}» no recibe CLERK_SECRET_KEY",
        )

    # 2. La API no se conecta con el dueno de la base. Es el rol al que aplica
    #    el REVOKE que hace inmutable `audit_log` (RNF-08, RNF-25) y el que no
    #    puede saltarse RLS, la unica barrera entre empresas.
    for s in ("api", "cron", "respaldos"):
        url = entorno(s).get("DATABASE_URL", "")
        # Solo el usuario, nunca el resto de la URL: **los logs de CI de un
        # repositorio publico se leen**, y `url.split('@')[0]` incluye la
        # contrasena. Un verificador que filtra lo que protege no sirve.
        usuario = url.split("://")[-1].split(":")[0] or "(sin usuario)"
        exigir(
            "ambienta_app:" in url,
            f"el servicio «{s}» se conecta como «{usuario}», no como ambienta_app",
        )
        # 3. Si falta, `db.py` cae a la URL de la aplicacion sin avisar: el
        #    webhook de Clerk no puede escribir y /health/db queda en rojo.
        exigir(
            "DATABASE_ADMIN_URL" in entorno(s),
            f"el servicio «{s}» no recibe DATABASE_ADMIN_URL",
        )

    # 4. `rotar-auditoria` borra de `audit_log` lo que archivo. Sin volumen, el
    #    `up -d --build` del runbook destruye el archivo y la tabla ya no lo
    #    tiene: se pierde el registro de actividades de meses enteros.
    for s in ("api", "cron", "respaldos"):
        exigir(
            "auditoria-archivada" in volumenes_de(servicios[s]),
            f"el servicio «{s}» no monta el volumen de la auditoria archivada",
        )

    # 4.b El respaldo diario tiene que existir y guardar donde no se borre.
    #     Hasta el 13-oct no habia ninguno: RNF-19 era deuda declarada, con la
    #     base del piloto en un volumen de una sola maquina.
    exigir("respaldos" in servicios, "no hay servicio de respaldo diario (RNF-19)")
    if "respaldos" in servicios:
        exigir(
            "respaldos" in volumenes_de(servicios["respaldos"]),
            "el servicio «respaldos» no monta un volumen: el respaldo moriria con el contenedor",
        )

    # 5. **Las tareas de fondo necesitan salir a internet.** `internal: true` no
    #    es solo "no publica puertos": un contenedor cuya unica red es esa **no
    #    resuelve DNS**. Medido el 13-oct: `cron` estaba solo en `interna`, asi
    #    que no alcanzaba api.resend.com y ningun correo habria salido nunca —
    #    encolado como fallo de red transitorio, en un log que nadie lee.
    redes = compose.get("networks") or {}
    for s in ("cron", "respaldos"):
        if s not in servicios:
            continue
        propias = servicios[s].get("networks") or []
        if isinstance(propias, dict):
            propias = list(propias)
        con_salida = [
            n for n in propias if not (redes.get(n) or {}).get("internal", False)
        ]
        exigir(
            bool(con_salida),
            f"el servicio «{s}» solo esta en redes internal: no resuelve DNS, "
            "asi que no alcanza Resend ni el bucket",
        )

    # 6. Postgres no se publica al host. Es lo que convierte una filtracion de
    #    credenciales en un problema acotado.
    exigir(
        not servicios["postgres"].get("ports"),
        "postgres publica puertos: la base queda alcanzable desde internet",
    )

    if FALLAS:
        print("El camino de despliegue tiene fallas:\n", file=sys.stderr)
        for f in FALLAS:
            print(f"  · {f}", file=sys.stderr)
        return 1

    print("OK · llave de Clerk, rol de base, URL de administracion, volumenes de")
    print("     auditoria y respaldo, salida a internet de las tareas de fondo y")
    print("     aislamiento de Postgres estan en su lugar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
