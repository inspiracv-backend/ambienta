from __future__ import annotations

import psycopg


async def guardar_estado(
    database_url: str, nombre: str, estado: str, *, elementos: int = 0, detalle: str | None = None,
) -> None:
    async with await psycopg.AsyncConnection.connect(database_url) as conn:
        await conn.execute(
            "INSERT INTO ai_job_estado (nombre, estado, iniciado_en, finalizado_en, elementos, detalle) "
            "VALUES (%s,%s,now(), "
            "CASE WHEN %s='ejecutando' THEN NULL ELSE now() END,%s,%s) "
            "ON CONFLICT (nombre) DO UPDATE SET estado=excluded.estado, "
            "iniciado_en=CASE WHEN excluded.estado='ejecutando' THEN now() "
            "ELSE coalesce(ai_job_estado.iniciado_en, now()) END, "
            "finalizado_en=CASE WHEN excluded.estado='ejecutando' THEN NULL ELSE now() END, "
            "elementos=excluded.elementos, detalle=excluded.detalle, actualizado_en=now()",
            (nombre, estado, estado, elementos, detalle),
        )
        await conn.commit()
