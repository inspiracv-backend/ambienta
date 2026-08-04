#!/usr/bin/env bash
# Crea el esquema completo y carga los catalogos base.
#
#   bash db/run.sh                 # usa la DATABASE_URL por defecto
#   bash db/run.sh --with-tests    # ademas corre el smoke test
#   DATABASE_URL=... bash db/run.sh
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://postgres:ambienta@localhost:5432/ambienta}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_TESTS=false
[[ "${1:-}" == "--with-tests" ]] && RUN_TESTS=true

run() {
    echo "→ $(basename "$1")"
    psql "$DB_URL" -v ON_ERROR_STOP=1 -q -f "$1"
}

echo "Base: ${DB_URL%%\?*}"
run "$DIR/01_schema.sql"
run "$DIR/03_seed_catalogos.sql"

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
