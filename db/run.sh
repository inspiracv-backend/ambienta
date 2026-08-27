#!/usr/bin/env bash
# Crea el esquema completo, aplica los cambios de esquema y carga los datos.
#
#   bash db/run.sh                 # usa la DATABASE_URL por defecto
#   bash db/run.sh --with-tests    # ademas corre el smoke test
#   bash db/run.sh --sin-demo      # sin los datos de ejemplo
#   DATABASE_URL=... bash db/run.sh
#
# La lista de archivos de abajo tiene que coincidir con el init de
# docker-compose.yml. Si se agrega un archivo aca y no alla (o al reves), las
# bases creadas por un camino quedan distintas de las creadas por el otro.
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://postgres:ambienta@localhost:5432/ambienta}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_TESTS=false
CON_DEMO=true
for arg in "$@"; do
    [[ "$arg" == "--with-tests" ]] && RUN_TESTS=true
    [[ "$arg" == "--sin-demo" ]] && CON_DEMO=false
done

run() {
    echo "→ $(basename "$1")"
    psql "$DB_URL" -v ON_ERROR_STOP=1 -q -f "$1"
}

echo "Base: ${DB_URL%%\?*}"
run "$DIR/01_schema.sql"
run "$DIR/04_clerk_auth.sql"
run "$DIR/05_user_permissions.sql"
run "$DIR/06_ticket_number.sql"
run "$DIR/07_rol_aplicacion.sql"
run "$DIR/08_perfil_normativo.sql"
run "$DIR/03_seed_catalogos.sql"
$CON_DEMO && run "$DIR/02_seed.sql"
run "$DIR/09_roles_por_codigo.sql"
run "$DIR/10_acceso_invitado.sql"
run "$DIR/11_solicitud_de_invitado.sql"
run "$DIR/12_reportabilidad_retc.sql"
run "$DIR/13_usuario_interno_con_departamento.sql"
run "$DIR/14_ds90_es_de_la_bcn.sql"
run "$DIR/15_declaracion_ante_su_sistema.sql"
run "$DIR/16_evidencia_del_articulo.sql"
run "$DIR/17_avisos_sin_duplicados.sql"
run "$DIR/18_control_documental.sql"
run "$DIR/21_significancia_del_aspecto.sql"

if $RUN_TESTS; then
    echo "→ smoke test"
    # El smoke test hace ROLLBACK: no deja datos.
    psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$DIR/02_smoke_test.sql" 2>&1 | grep -E "OK |FALLO" || true
fi

echo
psql "$DB_URL" -t -A -F' · ' -c "
SELECT 'tablas: '   || count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
       WHERE c.relkind='r' AND n.nspname='public'
UNION ALL SELECT 'policies RLS: ' || count(*) FROM pg_policies WHERE schemaname='public';"
echo "Listo."
