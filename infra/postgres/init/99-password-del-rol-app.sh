#!/bin/sh
# =============================================================================
# 99 · Contrasena real para el rol con el que se conecta la API
# =============================================================================
# `db/07_rol_aplicacion.sql` crea `ambienta_app` con la contrasena
# `ambienta_app_dev`, escrita en un archivo que se versiona en un repositorio
# publico. El propio archivo lo dice: "en cualquier entorno real hay que
# cambiarla y pasarla por variable de entorno". Esto es ese paso.
#
# Que Postgres no publique puertos en produccion lo hace menos grave, no
# inofensivo: cualquiera con un tunel SSH al servidor, o con acceso a otro
# contenedor de la red interna, entra a la base con una contrasena publicada.
#
# Corre **una sola vez**, cuando el volumen de datos se inicializa. Sobre un
# volumen que ya existe los scripts de init no se ejecutan: el ALTER manual
# para ese caso esta en docs/despliegue.md.
#
# Va en `.sh` y no en `.sql` porque los `.sql` de initdb no leen variables de
# entorno; los `.sh` si.
# =============================================================================
set -eu

if [ -z "${APP_DB_PASSWORD:-}" ]; then
  echo "99-password-del-rol-app: falta APP_DB_PASSWORD" >&2
  exit 1
fi

if [ "$APP_DB_PASSWORD" = "ambienta_app_dev" ]; then
  echo "99-password-del-rol-app: APP_DB_PASSWORD es la contrasena de desarrollo, que esta publicada en db/07_rol_aplicacion.sql" >&2
  exit 1
fi

# `-v` pasa la contrasena como variable de psql y `:'password'` la cita: asi no
# se interpola en el texto del SQL ni aparece en el historial del shell.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v password="$APP_DB_PASSWORD" <<'SQL'
ALTER ROLE ambienta_app WITH LOGIN PASSWORD :'password';
SQL

echo "99-password-del-rol-app: OK · ambienta_app quedo con la contrasena de este entorno"
