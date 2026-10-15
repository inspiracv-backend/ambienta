"""
Aplica las migraciones de `servicio/migraciones/` en orden.

    python -m ambienta_ia.conocimiento.migrar

Necesita un usuario administrador (`DATABASE_URL_ADMIN`) y las claves de los dos roles
(`CLAVE_IA_CONSULTA`, `CLAVE_IA_SINCRONIZADOR`). Lleva registro de lo aplicado en la tabla
`migracion`; correrlo dos veces no hace nada la segunda.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys

import psycopg
from psycopg import sql

CARPETA = pathlib.Path(os.environ.get("MIGRACIONES_DIR") or pathlib.Path(__file__).resolve().parents[3] / "migraciones")


def _sustituir(texto: str, valores: dict[str, str | int]) -> str:
    """Reemplaza :nombre y :'nombre' al estilo psql, con literales escapados."""

    def literal(m: re.Match[str]) -> str:
        return sql.Literal(str(valores[m.group(1)])).as_string(None)

    texto = re.sub(r":'(\w+)'", literal, texto)
    return re.sub(r"(?<!:):(\w+)\b", lambda m: str(valores[m.group(1)]) if m.group(1) in valores else m.group(0), texto)


def migrar(url_admin: str, *, dimension: int, clave_consulta: str, clave_sincronizador: str,
           carpeta: pathlib.Path = CARPETA) -> list[str]:
    valores: dict[str, str | int] = {
        "dimension": dimension,
        "clave_consulta": clave_consulta,
        "clave_sincronizador": clave_sincronizador,
    }
    aplicadas: list[str] = []
    with psycopg.connect(url_admin, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS migracion (version text PRIMARY KEY, "
            "aplicada_en timestamptz NOT NULL DEFAULT now())"
        )
        hechas = {r[0] for r in conn.execute("SELECT version FROM migracion")}
        for archivo in sorted(carpeta.glob("*.sql")):
            version = archivo.stem
            # 000_roles se aplica siempre: son roles del clúster y las claves pueden rotar
            if version in hechas and not version.startswith("000_"):
                continue
            with conn.transaction():
                conn.execute(_sustituir(archivo.read_text(encoding="utf-8"), valores))
                conn.execute(
                    "INSERT INTO migracion (version) VALUES (%s) ON CONFLICT DO NOTHING", (version,)
                )
            aplicadas.append(version)
    return aplicadas


def main() -> None:
    try:
        url = os.environ["DATABASE_URL_ADMIN"]
        dimension = int(os.environ.get("DIMENSION_EMBEDDINGS", "1536"))
        consulta = os.environ["CLAVE_IA_CONSULTA"]
        sincronizador = os.environ["CLAVE_IA_SINCRONIZADOR"]
    except KeyError as e:
        sys.exit(f"Falta la variable {e.args[0]}")
    hechas = migrar(url, dimension=dimension, clave_consulta=consulta, clave_sincronizador=sincronizador)
    print("Aplicadas:", ", ".join(hechas) or "ninguna")


if __name__ == "__main__":
    main()
