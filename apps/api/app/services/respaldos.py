"""Respaldo de la base y del registro de actividades archivado (RNF-19, RNF-20).

    docker compose exec api python -m app.tareas respaldar

## Por que existe

Hasta el 13-oct-2026 **no habia ninguno**, y el runbook lo declaraba como deuda
abierta: *"debe resolverse antes de tener datos reales de clientes"*. La Beta
corre con la base en un volumen de Docker de una sola maquina, asi que un disco
que falla es la perdida de los datos del piloto.

## Lo que respalda, y por que son DOS cosas

1. **La base**, con `pg_dump` en formato `custom`: comprimido, y `pg_restore`
   puede restaurar de a tablas sin desempaquetar todo.
2. **El registro de actividades ya rotado.** `rotar-auditoria` escribe un JSON
   por empresa y **borra esas filas de `audit_log`**: desde ese momento el JSON
   es el unico lugar donde existe ese registro, y **no esta en `pg_dump`**. Un
   respaldo que solo copie la base pierde la auditoria de los meses cerrados —
   justo lo que un fiscalizador pide.

## Las dos trampas que este modulo evita a proposito

**El volcado se hace con el dueno de la base, nunca con `ambienta_app`.**
Medido el 13-oct contra la base real: `pg_dump` **se niega en voz alta**,
`ERROR: query would be affected by row-level security policy for table
"action_plans"`. Es la buena noticia — por defecto `pg_dump` pone
`row_security = off` y falla antes que entregar datos parciales — y por eso
`DATABASE_ADMIN_URL` se exige en vez de caer a `DATABASE_URL` como hace
`db.py`: con el rol de la aplicacion el respaldo no sale **ninguna** noche, y
el motivo no se parece al sintoma.

**Lo que si seria silencioso es `--enable-row-security`**, que apaga esa
proteccion y hace que `pg_dump` vuelque solo las filas visibles. Con el rol de
la aplicacion y sin tenant declarado eso son **cero filas de empresa**, en un
archivo con el esquema entero y un tamano creible. Esa bandera no se pasa, y
este comentario existe para que nadie la agregue para "arreglar" el error de
arriba: el error de arriba se arregla con el rol correcto.

**Y el respaldo se verifica restaurandolo**, porque el rol es solo una de las
formas de terminar con un archivo inservible. Un archivo que nadie restauro no
es un respaldo: `verificar()` crea una base temporal, restaura ahi, cuenta filas
y la borra. Eso caza lo que un `pg_dump` exitoso no descarta — un volcado que se
corto porque el disco se lleno, un `.dump` corrupto, un restore que falla a
medias— y compara contra la base viva, que es la unica referencia que vale.

## Donde queda

En el bucket, bajo el prefijo `respaldos/` — **fuera de `tenants/`** a
proposito: un respaldo contiene los datos de **todas** las empresas, asi que no
pertenece a la carpeta de ninguna, y el dia que se acote una llave de B2 al
prefijo de una empresa, los respaldos no deben caer dentro.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tarfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..config import get_settings
from . import almacenamiento as alm

logger = logging.getLogger(__name__)

#: Cuantos dias se conservan los respaldos, local y remotamente.
RETENER_DIAS = 30

#: Un respaldo de una base recien creada pesa ~100 KB con el esquema vacio. Por
#: debajo de esto el volcado se corto: no es un umbral de "base chica", es un
#: piso por debajo del cual ni el esquema cabe.
MINIMO_CREIBLE_BYTES = 20_000

#: Las tablas que se cuentan al verificar. No son "unas cualquiera": son las
#: que **estan bajo RLS** —donde un volcado tomado con el rol equivocado, o con
#: `--enable-row-security`, saldria vacio— mas `audit_log`, que es la mas grande
#: y por eso la primera que se nota truncada.
TABLAS_TESTIGO = ("tenants", "users", "audit_log", "legal_norms")

_FECHA_EN_NOMBRE = re.compile(r"(\d{4}-\d{2}-\d{2})")


class ErrorDeRespaldo(Exception):
    """El respaldo no se pudo completar o no se pudo verificar."""


@dataclass
class Artefacto:
    nombre: str
    ruta: Path
    bytes: int
    subido: bool = False


@dataclass
class Informe:
    artefactos: list[Artefacto] = field(default_factory=list)
    filas_verificadas: dict[str, int] = field(default_factory=dict)
    purgados_locales: list[str] = field(default_factory=list)
    purgados_remotos: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        lineas = []
        for a in self.artefactos:
            destino = "subido al bucket" if a.subido else "solo local"
            lineas.append(f"  · {a.nombre} — {a.bytes/1_048_576:.1f} MB ({destino})")
        if self.filas_verificadas:
            filas = ", ".join(f"{t}={n}" for t, n in self.filas_verificadas.items())
            lineas.append(f"  · verificado restaurando: {filas}")
        if self.purgados_locales:
            lineas.append(f"  · purgados en disco: {len(self.purgados_locales)}")
        if self.purgados_remotos:
            lineas.append(f"  · purgados en el bucket: {len(self.purgados_remotos)}")
        for a in self.advertencias:
            lineas.append(f"  AVISO: {a}")
        return "\n".join(lineas)


# ── La URL, en el dialecto que entiende pg_dump ─────────────────────────────


def url_de_administracion() -> str:
    """La URL del **dueno** de la base, lista para `pg_dump`.

    Dos conversiones, las dos necesarias:

    1. `postgresql+psycopg://` es dialecto de SQLAlchemy; `pg_dump` quiere
       `postgresql://`.
    2. Se exige `DATABASE_ADMIN_URL`. **No se cae a `DATABASE_URL` como hace
       `db.py`**: con el rol de la aplicacion `pg_dump` falla todas las noches
       con un error sobre RLS que no se parece a "falta una variable".
    """
    s = get_settings()
    if not s.database_admin_url:
        raise ErrorDeRespaldo(
            "Falta DATABASE_ADMIN_URL. El respaldo se toma con el dueno de la "
            "base: con el rol de la aplicacion, `pg_dump` se niega con "
            "'query would be affected by row-level security policy'."
        )
    return re.sub(r"^postgresql\+\w+://", "postgresql://", s.database_admin_url)


def _correr(orden: list[str], *, entorno: dict | None = None) -> str:
    completo = {**os.environ, **(entorno or {})}
    r = subprocess.run(orden, capture_output=True, text=True, env=completo)
    if r.returncode != 0:
        # El mensaje de pg_dump dice exactamente que falta —version del
        # cliente, permiso, base inexistente— y vale mas que el codigo suelto.
        raise ErrorDeRespaldo(
            f"`{orden[0]}` fallo con codigo {r.returncode}: "
            f"{(r.stderr or r.stdout).strip()[:500]}"
        )
    return r.stdout


# ── Volcado ─────────────────────────────────────────────────────────────────


def volcar_base(destino: Path, *, dia: date) -> Artefacto:
    """`pg_dump` en formato custom. Devuelve el artefacto escrito."""
    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"ambienta-base-{dia.isoformat()}.dump"
    ruta = destino / nombre

    _correr(
        [
            "pg_dump",
            "--format=custom",
            # Nivel 6: el punto donde comprimir mas deja de pagar el tiempo.
            "--compress=6",
            # Sin dueno ni privilegios: restaurar en otro servidor no deberia
            # exigir que existan los mismos roles con los mismos nombres. Los
            # roles los crean `db/07` y las migraciones, no el respaldo.
            "--no-owner",
            "--no-privileges",
            f"--file={ruta}",
            url_de_administracion(),
        ]
    )

    tamano = ruta.stat().st_size
    if tamano < MINIMO_CREIBLE_BYTES:
        raise ErrorDeRespaldo(
            f"El volcado pesa {tamano} bytes, por debajo del minimo creible "
            f"({MINIMO_CREIBLE_BYTES}). Se corto o salio vacio."
        )
    return Artefacto(nombre=nombre, ruta=ruta, bytes=tamano)


def empaquetar_auditoria(destino: Path, *, dia: date, origen: Path | None = None) -> Artefacto | None:
    """La auditoria ya rotada, en un `.tar.gz`. `None` si todavia no hay nada.

    Que el directorio este vacio es lo normal hasta la primera rotacion
    mensual, asi que no es un error — pero **que no exista si es un aviso**:
    significa que la ruta no coincide con el volumen, y entonces la rotacion va
    a escribir en disco efimero.
    """
    origen = origen or Path(get_settings().ruta_archivo_auditoria)
    if not origen.exists():
        return None

    archivos = [p for p in origen.rglob("*") if p.is_file() and p.name != ".prueba"]
    if not archivos:
        return None

    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"ambienta-auditoria-{dia.isoformat()}.tar.gz"
    ruta = destino / nombre
    with tarfile.open(ruta, "w:gz") as tar:
        for p in archivos:
            tar.add(p, arcname=str(p.relative_to(origen)))
    return Artefacto(nombre=nombre, ruta=ruta, bytes=ruta.stat().st_size)


# ── Verificacion: restaurar de verdad ───────────────────────────────────────


def verificar(artefacto: Artefacto) -> dict[str, int]:
    """Restaura el volcado en una base temporal y cuenta filas.

    Que `pg_dump` salga con codigo 0 dice que leyo la base, no que el archivo
    sirva: el disco se puede haber llenado a mitad de la escritura, el `.dump`
    puede estar corrupto, y `pg_restore` puede fallar en la mitad de las tablas.

    Compara contra la base viva: si una tabla testigo tiene filas alla y menos
    aca, el respaldo no sirve y se dice ahora, no el dia de la restauracion.
    """
    import psycopg

    url = url_de_administracion()
    sello = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    temporal = f"ambienta_verificacion_{sello}"

    # `autocommit`: CREATE DATABASE no corre dentro de una transaccion.
    with psycopg.connect(url, autocommit=True) as cx:
        vivas = {}
        for tabla in TABLAS_TESTIGO:
            with cx.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {tabla}")  # noqa: S608 - lista fija
                vivas[tabla] = cur.fetchone()[0]
        cx.execute(f'CREATE DATABASE "{temporal}"')

    try:
        destino = re.sub(r"/[^/?]+(\?|$)", f"/{temporal}\\1", url, count=1)
        # `--exit-on-error`: sin esto `pg_restore` informa los errores y sale
        # con 0, asi que un respaldo a medias se veria restaurado.
        _correr(
            [
                "pg_restore",
                "--dbname=" + destino,
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                str(artefacto.ruta),
            ]
        )

        restauradas: dict[str, int] = {}
        with psycopg.connect(destino, autocommit=True) as cx:
            for tabla in TABLAS_TESTIGO:
                with cx.cursor() as cur:
                    cur.execute(f"SELECT count(*) FROM {tabla}")  # noqa: S608
                    restauradas[tabla] = cur.fetchone()[0]

        faltantes = [
            f"{t}: {vivas[t]} en la base y {restauradas[t]} en el respaldo"
            for t in TABLAS_TESTIGO
            if vivas[t] > 0 and restauradas[t] != vivas[t]
        ]
        if faltantes:
            raise ErrorDeRespaldo(
                "El respaldo restaurado no tiene las filas de la base viva. "
                + "; ".join(faltantes)
                + ". Lo mas probable: el volcado se tomo con un rol al que RLS "
                "le esconde las filas."
            )
        return restauradas
    finally:
        # La base temporal se borra pase lo que pase: una verificacion que deja
        # basura acumula una copia de la base por dia.
        with psycopg.connect(url, autocommit=True) as cx:
            cx.execute(f'DROP DATABASE IF EXISTS "{temporal}" WITH (FORCE)')


# ── Fuera del servidor ──────────────────────────────────────────────────────


def subir(artefactos: list[Artefacto], informe: Informe) -> None:
    """Sube cada artefacto al bucket. Sin credenciales, avisa y sigue.

    No falla la corrida: un respaldo en el disco local **es mejor que ninguno**,
    y dejar la base sin volcar porque el bucket no esta configurado seria
    cambiar un problema por uno peor. Pero queda dicho en el informe, porque un
    respaldo que vive en el mismo disco que la base no protege del caso que mas
    importa.
    """
    if not alm.esta_configurado():
        informe.advertencias.append(
            "El almacenamiento no esta configurado: los respaldos quedaron SOLO "
            "en el disco de esta maquina, que es el mismo que puede fallar."
        )
        return

    for a in artefactos:
        try:
            alm.subir_respaldo(nombre=a.nombre, ruta=a.ruta)
            a.subido = True
        except Exception as exc:  # noqa: BLE001 - se informa y se sigue
            informe.advertencias.append(f"No se pudo subir {a.nombre}: {exc}")


def _fecha_de(nombre: str) -> date | None:
    m = _FECHA_EN_NOMBRE.search(nombre)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def purgar(destino: Path, *, dias: int, dia: date, informe: Informe) -> None:
    """Borra los respaldos mas viejos que `dias`, local y remotamente.

    **Nunca deja cero.** Si todo lo que hay cae fuera de la ventana —porque
    alguien cambio el reloj, o porque no se respaldo en un mes— purgar dejaria
    la instalacion sin ningun respaldo, que es exactamente lo contrario de lo
    que esta tarea existe para evitar.
    """
    limite = dia - timedelta(days=dias)

    locales = sorted(p for p in destino.glob("ambienta-*") if p.is_file())
    viejos = [p for p in locales if (_fecha_de(p.name) or dia) < limite]
    if viejos and len(viejos) < len(locales):
        for p in viejos:
            p.unlink()
            informe.purgados_locales.append(p.name)
    elif viejos:
        informe.advertencias.append(
            "No se purgo nada en disco: todos los respaldos son mas viejos que "
            f"{dias} dias y borrarlos dejaria la instalacion sin ninguno."
        )

    if not alm.esta_configurado():
        return
    try:
        remotos = alm.listar_respaldos()
    except Exception as exc:  # noqa: BLE001
        informe.advertencias.append(f"No se pudo listar el bucket: {exc}")
        return

    viejos_remotos = [n for n in remotos if (_fecha_de(n) or dia) < limite]
    if viejos_remotos and len(viejos_remotos) < len(remotos):
        for n in viejos_remotos:
            try:
                alm.borrar_respaldo(nombre=n)
                informe.purgados_remotos.append(n)
            except Exception as exc:  # noqa: BLE001
                informe.advertencias.append(f"No se pudo borrar {n}: {exc}")
    elif viejos_remotos:
        informe.advertencias.append(
            "No se purgo nada en el bucket por la misma razon que en disco."
        )


# ── La corrida completa ─────────────────────────────────────────────────────


def correr(
    *,
    destino: Path | None = None,
    dia: date | None = None,
    verificando: bool = True,
    subiendo: bool = True,
    retener_dias: int = RETENER_DIAS,
) -> Informe:
    s = get_settings()
    destino = destino or Path(s.ruta_respaldos)
    dia = dia or datetime.now(timezone.utc).date()
    informe = Informe()

    base = volcar_base(destino, dia=dia)
    informe.artefactos.append(base)

    auditoria = empaquetar_auditoria(destino, dia=dia)
    if auditoria:
        informe.artefactos.append(auditoria)
    elif not Path(s.ruta_archivo_auditoria).exists():
        informe.advertencias.append(
            f"No existe {s.ruta_archivo_auditoria}. Si la rotacion mensual "
            "escribe ahi, lo hara en disco efimero y se perdera en el proximo "
            "`up -d --build`."
        )

    if verificando:
        informe.filas_verificadas = verificar(base)
        # **Un cero no es una tranquilidad.** Sobre una base recien instalada
        # todas las testigo valen 0, asi que la comparacion contra la base viva
        # no compara nada y lo unico demostrado es que el archivo se restaura.
        # El informe lo dice en vez de mostrar "verificado" y dejar que se lea
        # como "los datos estan ahi".
        if not any(informe.filas_verificadas.values()):
            informe.advertencias.append(
                "La base no tiene filas en ninguna tabla testigo "
                f"({', '.join(TABLAS_TESTIGO)}): la verificacion solo probo que "
                "el archivo se restaura, no que contenga datos. Normal en una "
                "instalacion nueva."
            )

    if subiendo:
        subir(informe.artefactos, informe)

    purgar(destino, dias=retener_dias, dia=dia, informe=informe)
    return informe


def espacio_libre(destino: Path) -> int:
    """Bytes libres donde caen los respaldos. Para avisar antes de llenar el disco."""
    destino.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(destino).free


__all__ = [
    "ErrorDeRespaldo",
    "Informe",
    "correr",
    "empaquetar_auditoria",
    "espacio_libre",
    "purgar",
    "subir",
    "url_de_administracion",
    "verificar",
    "volcar_base",
]