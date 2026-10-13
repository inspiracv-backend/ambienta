"""Traduce los errores de integridad de Postgres a respuestas de cliente.

Sin esto, cualquier violacion de una restriccion sale como **500**: un
`provider` que no esta en el CHECK, un codigo repetido, una clave foranea que
no existe. Todos son datos malos del cliente, y un 500 dice lo contrario —
que el problema es del servidor.

La diferencia no es cosmetica. Un 500 no le dice a quien llama que corregir,
ensucia el monitoreo con alertas que no son incidentes, y en un cliente con
reintentos automaticos hace que se reintente algo que jamas va a funcionar.

Se traduce por el tipo de violacion y no por el texto del mensaje, que cambia
entre versiones de Postgres y de idioma.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Request, status
from fastapi.responses import JSONResponse
from psycopg import errors as pg
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# Que responder segun que restriccion se violo.
#
# 409 para la unicidad porque el estado del servidor es el problema: ya existe
# algo con ese valor, y quien llama no puede arreglarlo cambiando su peticion
# — tiene que elegir otro valor o mirar lo que ya hay.
#
# 422 para el resto porque el cuerpo enviado no es aceptable: un valor fuera
# del CHECK, un campo obligatorio en null, una referencia a algo inexistente.
_TRADUCCION = {
    pg.UniqueViolation: (
        status.HTTP_409_CONFLICT,
        "Ya existe un registro con ese valor.",
        "valor_duplicado",
    ),
    pg.CheckViolation: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Algun valor enviado no esta entre los permitidos.",
        "valor_no_permitido",
    ),
    pg.NotNullViolation: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Falta un campo obligatorio.",
        "campo_obligatorio",
    ),
    pg.ForeignKeyViolation: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Alguna referencia apunta a un registro que no existe.",
        "referencia_inexistente",
    ),
}

#: Columnas que no se le nombran a quien llama: las pone el servidor, no la
#: persona, y decir "ya existe con ese tenant_id" no le dice que corregir.
_COLUMNAS_DEL_SERVIDOR = frozenset({"tenant_id"})

_COLUMNAS_DE_RESTRICCION = text(
    """
    SELECT a.attname
      FROM pg_constraint k
      JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = ANY (k.conkey)
     WHERE k.conname = :n
    UNION ALL
    SELECT a.attname
      FROM pg_class i
      JOIN pg_index x ON x.indexrelid = i.oid
      JOIN pg_attribute a ON a.attrelid = x.indrelid AND a.attnum = ANY (x.indkey)
     WHERE i.relname = :n
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = :n)
    """
)


@lru_cache(maxsize=256)
def columnas_de_restriccion(nombre: str) -> tuple[str, ...]:
    """Las columnas de una restriccion o indice unico, leidas del catalogo.

    **No se leen de `message_detail`**, que era la primera idea: con RLS activo
    Postgres **omite ese detalle** en las violaciones de unicidad, justamente
    porque lleva los valores de la fila. Medido el 14-sep: `message_detail` es
    `None` para `uq_improvement_methodologies_code`. El nombre de la
    restriccion si llega, y el catalogo dice a que columnas corresponde sin
    tocar ningun dato.

    Conexion propia y aparte: la de la peticion esta en una transaccion
    abortada. Solo corre en el camino de error, y se cachea por nombre.
    """
    from .db import engine

    try:
        with engine.connect() as con:
            filas = con.execute(_COLUMNAS_DE_RESTRICCION, {"n": nombre}).scalars().all()
    except Exception:  # pragma: no cover - el error original importa mas
        logger.warning("No se pudieron leer las columnas de %s", nombre)
        return ()
    return tuple(filas)


def campos_de(diag: object) -> list[str]:
    """Que columnas participan del rechazo, **nunca sus valores**.

    Un NOT NULL trae `column_name`; una unicidad, un CHECK o una clave foranea
    traen `constraint_name`, y las columnas salen del catalogo. Si nada calza
    se devuelve lista vacia —el `codigo` sigue sirviendo— en vez de adivinar.
    """
    columna = getattr(diag, "column_name", None)
    if columna:
        return [columna] if columna not in _COLUMNAS_DEL_SERVIDOR else []
    restriccion = getattr(diag, "constraint_name", None)
    if not restriccion:
        return []
    return [c for c in columnas_de_restriccion(restriccion) if c not in _COLUMNAS_DEL_SERVIDOR]


def _nombre_de_restriccion(exc: IntegrityError) -> str | None:
    """El nombre de la constraint, que es la parte util del error.

    `integration_accounts_provider_check` le dice a quien integra exactamente
    que revisar. No es informacion sensible: es el nombre de una restriccion
    del propio esquema, no un dato de nadie.
    """
    diag = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diag, "constraint_name", None)


async def manejar_error_de_integridad(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    original = getattr(exc, "orig", None)
    codigo, mensaje, motivo = _TRADUCCION.get(
        type(original),
        (status.HTTP_500_INTERNAL_SERVER_ERROR, "Error de integridad en la base.", "error_de_integridad"),
    )

    restriccion = _nombre_de_restriccion(exc)
    detalle = f"{mensaje} (restriccion: {restriccion})" if restriccion else mensaje

    # El SQL completo va al log y nunca a la respuesta: lleva los valores
    # enviados, que pueden ser datos de la empresa.
    if codigo >= 500:
        logger.exception("Violacion de integridad no traducida: %s", request.url.path)
    else:
        logger.info(
            "%s %s rechazado por %s", request.method, request.url.path, restriccion
        )

    # **`codigo` y `campos` son el contrato; `detail` es para personas.** La
    # interfaz ramifica sobre el codigo y nombra los campos; el texto se puede
    # reescribir sin romperla. Hasta el 14-sep solo habia `detail`, y distinguir
    # un duplicado de una referencia rota exigia leer la frase.
    return JSONResponse(
        status_code=codigo,
        content={
            "detail": detalle,
            "codigo": motivo,
            "campos": campos_de(getattr(original, "diag", None)),
            "restriccion": restriccion,
        },
    )
