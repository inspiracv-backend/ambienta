"""Como se siembra catalogo PUBLICO en las pruebas, desde `db/29`.

## Por que hace falta esto

`db/29` puso RLS sobre `legal_norms`, `legal_norm_versions` y `legal_articles`
para que una empresa pueda registrar su RCA sin mostrarsela a las demas
(RF-10). La politica dice:

| quien escribe | que puede escribir |
|---|---|
| sesion con tenant declarado | **solo lo suyo** |
| sesion sin tenant | **solo lo publico** |

Varias pruebas sembraban articulado **publico** desde una sesion **con tenant
declarado**, y eso ahora lo rechaza Postgres. No es un defecto de la politica:
es que el arnes hacia algo que el sistema real no hace. En produccion el
catalogo lo escribe la sincronizacion de la BCN, que corre **sin tenant**.

## Por que se suelta el tenant en vez de abrir otra sesion

Los fixtures de esas pruebas terminan con `rollback()`, asi que todo lo que
escriben se descarta. Sembrar desde una sesion aparte obligaria a confirmar, y
dejaria filas de prueba en la base de desarrollo — el descuido que ya aparecio
dos veces hoy, con 159 comentarios y 70 vinculos huerfanos.

`set_config(..., true)` es **local a la transaccion**, asi que soltar y volver
a declarar el tenant no se escapa del `rollback`.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.orm import Session


@contextmanager
def como_catalogo(db: Session, tenant_id: str):
    """Suelta el tenant declarado mientras dura el bloque, y lo repone.

    Dentro del bloque, `current_tenant_id()` es NULL —`nullif(..., '')`— asi que
    la politica de `db/29` admite escribir filas publicas y **solo** publicas.

    Se repone al salir aunque el bloque falle: sin eso, el resto de la prueba
    correria sin empresa declarada y **veria cero filas** en todas las tablas
    de negocio, con un fallo que no se parece a la causa (CLAUDE.md §4).
    """
    # **Se vacia lo pendiente ANTES de soltar el tenant.** Sin esto, cualquier
    # `flush` dentro del bloque —propio o automatico— escribe tambien las filas
    # de empresa que quedaron en la sesion, y esas **si** violan su politica sin
    # tenant declarado. Costo una hora: dos pruebas de `sincronizar_matriz`
    # fallaban diciendo que actualizar la version no hacia nada, cuando lo que
    # pasaba es que el `flush` de adentro reventaba y dejaba la transaccion a
    # medias.
    db.flush()
    db.execute(text("SELECT set_config('ambienta.tenant_id', '', true)"))
    try:
        yield db
        # Y se vacia lo del catalogo antes de reponer el tenant, por el mismo
        # motivo al reves: un `flush` posterior escribiria estas filas publicas
        # con la empresa declarada, y el `WITH CHECK` las rechazaria.
        db.flush()
    finally:
        db.execute(
            text("SELECT set_config('ambienta.tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
