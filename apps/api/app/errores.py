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

from fastapi import Request, status
from fastapi.responses import JSONResponse
from psycopg import errors as pg
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
    ),
    pg.CheckViolation: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Algun valor enviado no esta entre los permitidos.",
    ),
    pg.NotNullViolation: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Falta un campo obligatorio.",
    ),
    pg.ForeignKeyViolation: (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Alguna referencia apunta a un registro que no existe.",
    ),
}


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
    codigo, mensaje = _TRADUCCION.get(
        type(original),
        (status.HTTP_500_INTERNAL_SERVER_ERROR, "Error de integridad en la base."),
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

    return JSONResponse(status_code=codigo, content={"detail": detalle})
