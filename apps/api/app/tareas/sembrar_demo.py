"""Deja una empresa lista para mostrar el sistema funcionando.

## El problema que resuelve

Con la base recien creada, el tablero se ve pobre y el CORE no responde nada —y
por un problema de **datos**, no de funcionalidad. Medido el 1-sep-2026 sobre
una base recreada desde cero:

    empresas con sector declarado ..... 0 de 2
    evaluaciones de cumplimiento ...... 6, concentradas en una planta
    documentos ........................ 0

Sin sector declarado, el calculo de normativa aplicable devuelve `sin_perfil`
para todas las empresas: la pregunta central del producto —**que normativa le
aplica a esta empresa**— no se puede demostrar. Y las plantas sin ninguna
evaluacion salen como "Sin evaluar", que es correcto pero no muestra nada.

## Por que usa los servicios de negocio y no `INSERT`

Podria escribir las filas a mano y seria mas corto. **Seria tambien una
mentira util**: la matriz legal quedaria poblada con lo que yo elegi, no con lo
que el sistema calcula, y una demostracion sobre datos inventados no demuestra
que el sistema funcione.

Aca la matriz sale de `normativa_aplicable.calcular()` y
`sincronizar_matriz.sincronizar()`, que son exactamente los que corre la
aplicacion. Si el CORE estuviera roto, esta tarea fallaria — que es lo que
queremos.

Lo unico que se escribe directo son las **evaluaciones**, porque evaluar un
articulo es un juicio humano que ningun servicio puede producir. Van marcadas
como de demostracion en `assessment_reason`, para que nadie las confunda con
trabajo real.

## No corre en produccion

Se niega si `ENVIRONMENT=production`. Sembrar datos de ejemplo en la base de un
cliente es de los errores que no se pueden deshacer con una disculpa.

## Uso

    docker compose exec api python -m app.tareas.sembrar_demo

Es **idempotente**: correrla dos veces no duplica nada. Y necesita el catalogo
normativo sincronizado; si detecta que no lo esta, lo dice y no sigue, en vez
de sembrar sobre un catalogo de ejemplo y aparentar que funciona.
"""
from __future__ import annotations

import argparse
import sys
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import AdminSessionLocal
from ..models.catalog import LegalArticle, LegalNorm
from ..models.compliance import ArticleCompliance, TenantLegalMatrix
from ..models.organization import Facility, Tenant, User
from ..services import normativa_aplicable, sincronizar_matriz

#: Palabras del giro de la empresa que apuntan a un sector CIIU.
#:
#: **El sector tiene que ser coherente con la empresa, no el que da mas
#: normas.** Es la primera version de esto: se elegia el sector con mas
#: normativa clasificada, y a "Minera Andes SpA" le quedaba declarado
#: *suministro de agua y gestion de residuos*. Nadie que mire la demostracion
#: dos segundos se lo cree, y una demostracion que no se cree no demuestra nada.
POR_EL_GIRO: list[tuple[tuple[str, ...], int]] = [
    (("miner", "mineral", "extracc", "cantera"), 2),
    (("agricol", "ganader", "silvicultura", "pesca", "acuicultura"), 1),
    (("manufactur", "fabricacion", "industrial"), 3),
    (("electricidad", "gas", "energia", "termoelectrica"), 4),
    (("agua", "residuo", "sanitari", "saneamiento"), 5),
    (("construcc", "obra"), 6),
    (("comercio", "retail", "venta"), 7),
    (("transporte", "logistica", "almacenamiento"), 8),
]

#: Si el giro no dice nada reconocible. Es el sector con mas normativa
#: clasificada, y por lo tanto el unico con el que el CORE tiene algo que
#: proponer: sembrar sobre un sector sin clasificar produce una matriz vacia
#: que se lee como un fallo del sistema.
SECTOR_DE_RESPALDO = 5
TRAMO_DEMO = "grande"

#: Cuantas normas hacen falta para que el catalogo sea el real y no el sembrado.
#: Con las 8 de ejemplo la demostracion muestra normativa que no existe.
MINIMO_DE_NORMAS = 12

#: La mezcla de estados. **No es aleatoria**: reproduce lo que se ve en una
#: empresa real a mitad de camino, que es lo que hace util la demostracion. Una
#: matriz toda en verde no muestra el producto; una toda en rojo tampoco.
MEZCLA = [
    ("compliant", "Se verifico el cumplimiento con el registro del periodo."),
    ("compliant", "Cumple: la medicion del ultimo trimestre esta dentro del limite."),
    ("compliant", "Cumple con el procedimiento vigente."),
    ("partial", "Cumple parcialmente: falta la medicion de una de las descargas."),
    ("non_compliant", "No cumple: la declaracion del periodo anterior no se presento."),
    ("not_applicable", "No aplica: la instalacion no genera este tipo de residuo."),
    ("pending", None),
    ("pending", None),
]

#: Lo que se escribe en cada evaluacion sembrada, para poder distinguirlas.
MARCA = "[demo]"


class NoSePuedeSembrar(RuntimeError):
    """Falta una condicion previa. Se explica en el mensaje."""


def _empresa_demo(db: Session) -> Tenant:
    """La primera empresa cliente, por fecha de creacion.

    Se elige asi y no por nombre para que la tarea funcione con cualquier
    siembra. Las gestoras quedan fuera: su tablero es el de sus clientes, no
    uno propio, y sembrarles matriz legal seria describir mal el producto.
    """
    empresa = db.scalars(
        select(Tenant)
        .where(Tenant.tenant_type != "manager", Tenant.deleted_at.is_(None))
        .order_by(Tenant.created_at)
        .limit(1)
    ).first()
    if empresa is None:
        raise NoSePuedeSembrar(
            "No hay ninguna empresa cliente en la base. Corre la siembra base "
            "primero: docker compose down -v && docker compose up -d"
        )
    return empresa


def _comprobar_catalogo(db: Session) -> int:
    normas = db.scalar(select(func.count()).select_from(LegalNorm)) or 0
    articulos = db.scalar(select(func.count()).select_from(LegalArticle)) or 0
    if normas < MINIMO_DE_NORMAS:
        raise NoSePuedeSembrar(
            f"El catalogo tiene {normas} normas y {articulos} articulos: son las "
            "de ejemplo, no las reales. Sembrar sobre esto mostraria normativa "
            "que no existe.\n\n"
            "  docker compose exec api python -m app.tareas.sincronizar_bcn\n"
        )
    return articulos


def _sector_segun_el_giro(giro: str | None) -> tuple[int, str]:
    """El sector CIIU que corresponde al giro declarado, y por que.

    Sin acentos y en minuscula para comparar: los giros vienen escritos por
    personas y "Extraccion" y "Extraccion" con tilde son la misma palabra.
    """
    if giro:
        plano = (
            giro.lower()
            .replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u")
        )
        for claves, sector in POR_EL_GIRO:
            if any(c in plano for c in claves):
                return sector, f"por el giro ({giro})"
    return SECTOR_DE_RESPALDO, "el giro no dice nada reconocible; se usa el de respaldo"


def _declarar_perfil(db: Session, empresa: Tenant) -> str:
    if empresa.sector_id and empresa.size_bracket:
        return "ya declarado"
    sector, motivo = _sector_segun_el_giro(empresa.business_activity)
    empresa.sector_id = empresa.sector_id or sector
    empresa.size_bracket = empresa.size_bracket or TRAMO_DEMO
    db.flush()
    return f"sector {empresa.sector_id}, tramo {empresa.size_bracket} — {motivo}"


def _evaluar(db: Session, empresa: Tenant, quien: UUID | None) -> tuple[int, int]:
    """Reparte las evaluaciones entre las plantas y evalua una parte.

    ## Dos cosas que la primera version hizo mal

    **Consultaba antes de que se escribieran las filas nuevas.**
    `sincronizar_matriz` agrega las evaluaciones a la sesion, y sin un `flush`
    explicito la consulta que sigue no las ve: sembraba 258 y evaluaba 33, sin
    que nada fallara.

    **Y dejaba 226 filas sin planta.** El tablero compara el cumplimiento
    **por instalacion**: una evaluacion sin planta no aparece en ninguna
    columna, asi que existe en la base y es invisible en la pantalla — que para
    una demostracion es lo mismo que no existir.

    Ahora se reparten **todas** entre las plantas y se evalua una parte, porque
    una matriz sin nada pendiente tampoco muestra el producto: lo que el sistema
    organiza es justamente el trabajo que falta.
    """
    plantas = list(
        db.scalars(
            select(Facility)
            .where(Facility.tenant_id == empresa.id, Facility.deleted_at.is_(None))
            .order_by(Facility.created_at)
        ).all()
    )
    if not plantas:
        raise NoSePuedeSembrar("La empresa no tiene instalaciones.")

    # **El `flush` va antes de consultar**, no despues: lo que acaba de sembrar
    # la sincronizacion todavia esta en la sesion y no en la base.
    db.flush()

    pendientes = list(
        db.scalars(
            select(ArticleCompliance)
            .where(
                ArticleCompliance.tenant_id == empresa.id,
                ArticleCompliance.compliance_status == "pending",
                ArticleCompliance.deleted_at.is_(None),
            )
            .order_by(ArticleCompliance.created_at)
        ).all()
    )

    ahora = db.scalar(select(func.now()))
    evaluadas = 0
    for i, fila in enumerate(pendientes):
        # Todas reciben planta, evaluadas o no: sin ella no salen en el tablero.
        fila.facility_id = plantas[i % len(plantas)].id

        estado, motivo = MEZCLA[i % len(MEZCLA)]
        if estado == "pending":
            continue
        fila.compliance_status = estado
        fila.assessment_reason = f"{MARCA} {motivo}"
        fila.assessed_at = ahora
        fila.assessed_by = quien
        evaluadas += 1

    db.flush()
    return evaluadas, len(pendientes) - evaluadas


def sembrar(db: Session) -> list[str]:
    """Deja la empresa lista. Devuelve lo que hizo, paso por paso."""
    if get_settings().environment == "production":
        raise NoSePuedeSembrar(
            "ENVIRONMENT=production. Esta tarea siembra datos de ejemplo y no "
            "corre contra la base de un cliente."
        )

    hecho: list[str] = []
    articulos = _comprobar_catalogo(db)
    hecho.append(f"catalogo normativo: {articulos} articulos disponibles")

    empresa = _empresa_demo(db)
    hecho.append(f"empresa: {empresa.legal_name}")
    hecho.append(f"perfil normativo: {_declarar_perfil(db, empresa)}")

    # El CORE, de verdad: lo mismo que corre la aplicacion.
    calculo = normativa_aplicable.calcular(db, empresa.id)
    hecho.append(
        f"normativa aplicable: {calculo.total} normas "
        f"({len(calculo.obligatorias)} obligatorias, "
        f"{len(calculo.recomendadas)} recomendadas)"
    )

    matriz = db.scalars(
        select(TenantLegalMatrix)
        .where(
            TenantLegalMatrix.tenant_id == empresa.id,
            TenantLegalMatrix.deleted_at.is_(None),
        )
        .order_by(TenantLegalMatrix.created_at)
        .limit(1)
    ).first()
    if matriz is None:
        raise NoSePuedeSembrar(
            "La empresa no tiene matriz legal. La crea la siembra base; sin "
            "ella no hay donde sincronizar la normativa aplicable."
        )

    resultado = sincronizar_matriz.sincronizar(db, matriz.id, empresa.id)
    hecho.append(
        f"matriz legal: {resultado.normas_agregadas} normas agregadas "
        f"({resultado.normas_ya_estaban} ya estaban), "
        f"{resultado.articulos_agregados} articulos por evaluar"
    )

    quien = db.scalars(
        select(User).where(User.tenant_id == empresa.id, User.deleted_at.is_(None))
    ).first()
    evaluadas, sin_evaluar = _evaluar(db, empresa, quien.id if quien else None)
    hecho.append(
        f"evaluaciones: {evaluadas} evaluadas, {sin_evaluar} dejadas por evaluar"
    )

    return hecho


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deja una empresa con datos suficientes para mostrar el sistema."
    )
    parser.add_argument(
        "--seco", action="store_true",
        help="Muestra lo que haria y deshace los cambios al final.",
    )
    args = parser.parse_args(argv)

    # Con el dueno de la base: hay que tocar `tenants`, que no lleva tenant_id,
    # y escribir en varias empresas si hiciera falta. Es mantenimiento, no un
    # endpoint.
    db = AdminSessionLocal()
    try:
        pasos = sembrar(db)
    except NoSePuedeSembrar as exc:
        print(f"\nNo se puede sembrar:\n\n{exc}\n", file=sys.stderr)
        db.rollback()
        return 1
    finally_ok = True
    try:
        if args.seco:
            db.rollback()
            print("\n(simulacion: no se guardo nada)")
        else:
            db.commit()
    except Exception:
        db.rollback()
        finally_ok = False
        raise
    finally:
        db.close()

    print("\nSemilla de demostracion:\n")
    for paso in pasos:
        print(f"  - {paso}")
    print()
    return 0 if finally_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
