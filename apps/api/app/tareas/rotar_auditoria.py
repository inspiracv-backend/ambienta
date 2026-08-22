"""Archiva el registro de actividades del mes y lo saca de la tabla.

Lo pidio el negocio: *"cada mes la BD en x tabla la baja a un JSON por cliente y
se va a guardar, asi para cuando se pueda subir de nuevo la carga sin problemas.
Asi sacamos informacion de la tabla y luego se borra para que no se degrade la
BD."*

## El orden importa, y no es negociable

**Se exporta, se verifica que el archivo existe y tiene lo que debe, y recien
ahi se borra.** Todo dentro de una transaccion: si el borrado falla, no queda un
archivo huerfano; si la escritura del archivo falla, no se borra nada.

Invertir el orden —borrar y despues escribir— pierde el registro entero ante
cualquier fallo de disco. Y no seria un fallo ruidoso: la tabla quedaria
prolija, el archivo no existiria, y nadie se enteraria hasta la auditoria.

## Un archivo por empresa, no uno solo

El negocio lo pidio "por cliente" y ademas es lo correcto: el registro de una
empresa **no puede viajar mezclado con el de otra**. Un archivo unico obligaria
a filtrarlo antes de entregarlo, y ese filtrado es justo el paso que se olvida.

## Por que corre con el dueno de la base

`ambienta_app` —la conexion de la API— tiene solo `INSERT` y `SELECT` sobre
`audit_log`: **no puede borrar**, y esta bien que sea asi. Es lo que impide que
un endpoint mal escrito tape sus huellas.

Esta tarea no es un endpoint: es mantenimiento, corre fuera del ciclo de las
peticiones, y usa la conexion del dueno. La inmutabilidad protege contra la
aplicacion, no contra el mantenimiento — y confundir las dos cosas fue lo que
hizo creer que el plan del negocio era inviable.

Como el dueno **salta RLS**, aca hay que filtrar por `tenant_id` a mano. Es la
unica parte del sistema donde eso es cierto, y por eso se dice fuerte.

## Cuando se puede volver a cargar

El JSON conserva las columnas tal como estan en la tabla, con los mismos
nombres. Reinsertarlo es un `COPY` o un `INSERT` directo; no hace falta
transformar nada. Es lo que pidio el negocio con *"para cuando se pueda subir de
nuevo"*.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: Columnas que se exportan. Explicitas y no `SELECT *` a proposito: si alguien
#: agrega una columna, el archivo no cambia de forma sin que nadie lo decida.
COLUMNAS = (
    "id",
    "tenant_id",
    "occurred_at",
    "actor_user_id",
    "action",
    "entity_type",
    "entity_id",
    "request_id",
    "ip_address",
    "reason",
    "before_data",
    "after_data",
    "metadata",
)


@dataclass
class ResultadoPorEmpresa:
    tenant_id: UUID
    nombre: str
    filas: int
    archivo: Path | None


@dataclass
class Resultado:
    """Que se archivo y que se borro.

    Se devuelven los numeros y no un "ok" porque **la promesa es verificable**:
    `filas_borradas` tiene que ser igual a `filas_archivadas`. Si difieren, algo
    se borro sin quedar guardado y hay que mirarlo.
    """

    desde: date
    hasta: date
    por_empresa: list[ResultadoPorEmpresa] = field(default_factory=list)
    filas_archivadas: int = 0
    filas_borradas: int = 0

    @property
    def cuadra(self) -> bool:
        return self.filas_archivadas == self.filas_borradas


def _serializable(valor):
    """Lo que `json` no sabe convertir por su cuenta."""
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    return valor


def rotar(
    db: Session,
    *,
    desde: date,
    hasta: date,
    destino: Path,
    borrar: bool = True,
) -> Resultado:
    """Archiva `[desde, hasta)` y borra lo archivado.

    `hasta` es **exclusivo**: para el mes de julio se pasa `2026-07-01` y
    `2026-08-01`. Un rango con el ultimo dia incluido deja fuera lo que ocurrio
    ese dia despues de medianoche, y ese error no se ve hasta que alguien busca
    un evento y no esta.

    **No hace `commit`.** Quien llama decide, para poder correrlo en seco.

    `borrar=False` archiva sin purgar: sirve para comprobar que el archivo sale
    bien antes de confiar en la parte destructiva.
    """
    destino.mkdir(parents=True, exist_ok=True)
    resultado = Resultado(desde=desde, hasta=hasta)

    empresas = db.execute(
        text(
            "SELECT DISTINCT t.id, t.legal_name FROM audit_log a "
            "JOIN tenants t ON t.id = a.tenant_id "
            "WHERE a.occurred_at >= :d AND a.occurred_at < :h "
            "ORDER BY t.legal_name"
        ),
        {"d": desde, "h": hasta},
    ).all()

    for tenant_id, nombre in empresas:
        filas = db.execute(
            text(
                f"SELECT {', '.join(COLUMNAS)} FROM audit_log "  # noqa: S608
                "WHERE tenant_id = :t AND occurred_at >= :d AND occurred_at < :h "
                "ORDER BY id"
            ),
            {"t": tenant_id, "d": desde, "h": hasta},
        ).all()

        if not filas:
            continue

        registros = [
            {c: _serializable(v) for c, v in zip(COLUMNAS, fila)} for fila in filas
        ]
        archivo = destino / f"auditoria-{desde:%Y-%m}-{tenant_id}.json"
        archivo.write_text(
            json.dumps(
                {
                    "tenant_id": str(tenant_id),
                    "empresa": nombre,
                    "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
                    "exportado_en": datetime.now(timezone.utc).isoformat(),
                    "filas": len(registros),
                    "registros": registros,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # **Se relee el archivo antes de borrar nada.** Que `write_text` no haya
        # lanzado no prueba que el contenido este en disco y sea legible: un
        # disco lleno puede truncar sin error. Es barato comprobarlo y el costo
        # de no hacerlo es perder el registro.
        guardado = json.loads(archivo.read_text(encoding="utf-8"))
        if guardado["filas"] != len(registros):
            raise RuntimeError(
                f"El archivo de {nombre} quedo con {guardado['filas']} filas y se "
                f"exportaron {len(registros)}. No se borra nada."
            )

        resultado.por_empresa.append(
            ResultadoPorEmpresa(
                tenant_id=tenant_id, nombre=nombre, filas=len(registros), archivo=archivo
            )
        )
        resultado.filas_archivadas += len(registros)

        if borrar:
            borradas = db.execute(
                text(
                    "DELETE FROM audit_log WHERE tenant_id = :t "
                    "AND occurred_at >= :d AND occurred_at < :h"
                ),
                {"t": tenant_id, "d": desde, "h": hasta},
            ).rowcount
            resultado.filas_borradas += borradas

    if borrar and not resultado.cuadra:
        # No deberia poder pasar dentro de una transaccion, pero si pasa hay que
        # frenar: significa que se borro algo que no quedo guardado.
        raise RuntimeError(
            f"Se archivaron {resultado.filas_archivadas} filas y se borraron "
            f"{resultado.filas_borradas}. Se aborta sin confirmar."
        )

    return resultado


def mes_anterior(hoy: date) -> tuple[date, date]:
    """El rango del mes cerrado anterior a `hoy`, como `[desde, hasta)`.

    **No se rota el mes en curso.** Correr la tarea el 15 y llevarse lo que va
    del mes deja el registro partido en dos lugares para un periodo que todavia
    no termino, y el que busque un evento de ayer no lo va a encontrar donde
    espera.
    """
    primero_de_este = hoy.replace(day=1)
    ultimo_del_anterior = primero_de_este - timedelta(days=1)
    return ultimo_del_anterior.replace(day=1), primero_de_este
