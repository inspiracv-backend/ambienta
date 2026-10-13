# syntax=docker/dockerfile:1
#
# Imagen de PRODUCCION de @ambienta/api (FastAPI). Usuario no-root, sin reload.
# El contexto de build es la RAIZ del repo (context: . en el compose).

FROM python:3.12-slim
WORKDIR /repo/apps/api

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# `pg_dump` y `pg_restore` para la tarea de respaldo (RNF-19).
#
# **De la version 16, igual que el servidor** (`pgvector/pgvector:pg16`): un
# `pg_dump` mas viejo que el servidor se niega a correr ("server version
# mismatch"), y uno mas nuevo restaura hacia atras sin garantia. Que el respaldo
# falle por la version del cliente es el tipo de cosa que se descubre el dia que
# hace falta restaurar.
#
# El nombre de la distribucion **se deriva de la imagen**, no se escribe a mano:
# `python:3.12-slim` paso de bookworm a trixie sin avisar, y con el codename
# fijo el build fallo con "held broken packages", que no se parece en nada a la
# causa.
RUN apt-get update     && apt-get install -y --no-install-recommends ca-certificates curl     && . /etc/os-release     && install -d /usr/share/postgresql-common/pgdg     && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc          -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc     && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main"          > /etc/apt/sources.list.d/pgdg.list     && apt-get update     && apt-get install -y --no-install-recommends postgresql-client-16     && apt-get purge -y curl     && apt-get autoremove -y     && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app

# Donde la rotacion mensual deja el registro de auditoria archivado
# (`RUTA_ARCHIVO_AUDITORIA`, apps/api/app/config.py). Se crea **en la imagen**
# y con dueno `appuser` a proposito: un volumen nombrado hereda el dueno del
# directorio que la imagen ya tiene en ese punto de montaje, y uno creado vacio
# en tiempo de ejecucion seria de root — el proceso no corre como root y la
# rotacion fallaria al escribir.
RUN mkdir -p /var/lib/ambienta/auditoria /var/lib/ambienta/respaldos

# Usuario sin privilegios: si el proceso se ve comprometido, no corre como root.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser /repo /var/lib/ambienta
USER appuser

EXPOSE 8000

# `--no-server-header`: sin esto uvicorn agrega su propia cabecera `server:
# uvicorn` **despues** de que la aplicacion respondio, asi que la respuesta
# sale con la cabecera dos veces y la primera delata el servidor. El
# middleware de la aplicacion no puede quitarla: se agrega mas abajo, en el
# protocolo. Lo detecto una comprobacion contra el sistema corriendo, no las
# pruebas: `TestClient` no pasa por uvicorn y no la veia.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
