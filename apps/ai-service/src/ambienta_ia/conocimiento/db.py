"""
Conexiones a la base de conocimiento.

Un pool por rol. Cada transacción de consulta fija `app.tenant_id` con `set_config(..., true)`,
que dura lo que dura la transacción: al devolver la conexión al pool no queda ninguna empresa
pegada para la siguiente petición.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import psycopg
from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool


async def _configurar(conn: psycopg.AsyncConnection) -> None:
    await register_vector_async(conn)
    await conn.set_autocommit(False)


class BaseConocimiento:
    def __init__(self, pool: AsyncConnectionPool):
        self._pool = pool

    @asynccontextmanager
    async def de_empresa(self, tenant_id: UUID | None) -> AsyncIterator[psycopg.AsyncConnection]:
        """
        Transacción con la empresa fijada. `tenant_id=None` solo ve el catálogo público.

        Es la única forma de consultar: no hay método que devuelva una conexión sin pasar por
        acá (D-04).
        """
        async with self._pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (str(tenant_id) if tenant_id else "",),
                )
                yield conn

    @asynccontextmanager
    async def transaccion(self) -> AsyncIterator[psycopg.AsyncConnection]:
        """Para el sincronizador, que solo escribe catálogo público."""
        async with self._pool.connection() as conn:
            async with conn.transaction():
                yield conn

    async def viva(self) -> bool:
        try:
            async with self._pool.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def cerrar(self) -> None:
        await self._pool.close()


async def abrir_base(url: str, *, minimo: int = 1, maximo: int = 10) -> BaseConocimiento:
    pool = AsyncConnectionPool(
        url, min_size=minimo, max_size=maximo, configure=_configurar, open=False
    )
    await pool.open(wait=True, timeout=15)
    return BaseConocimiento(pool)
