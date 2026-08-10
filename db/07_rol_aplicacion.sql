-- =============================================================================
-- 07 · La API se conecta con un rol que NO puede saltarse RLS
-- =============================================================================
-- Hasta ahora la API se conectaba como `ambienta`, que es superusuario con
-- BYPASSRLS. Row Level Security no se le aplicaba **en absoluto**: lo unico que
-- protegia era el `SET LOCAL ROLE ambienta_app` que hace `get_tenant_db`, una
-- linea por transaccion.
--
-- Eso convertia el aislamiento entre empresas en algo que se pierde solo:
--
--   * `SET LOCAL` muere con la transaccion. Despues de un `db.commit()` la
--     conexion vuelve a ser superusuario y ve las 2 empresas en vez de 1.
--     Medido: de 4 usuarios visibles a 6.
--   * Un endpoint escrito con `get_db` en vez de `get_tenant_db` no falla ni
--     avisa: devuelve datos de todas las empresas con normalidad.
--
-- Y no habia nada detras: ninguna consulta de la aplicacion filtra por
-- `tenant_id`. RLS no es la segunda barrera, es la unica.
--
-- Con este cambio la barrera vive en la conexion. Aunque alguien olvide el
-- `SET LOCAL ROLE`, las policies se evaluan igual y una consulta sin tenant
-- declarado devuelve cero filas en vez de todo.
--
-- NOTA DE PRODUCCION: la contrasena de abajo es para desarrollo, igual que la
-- de `ambienta`. En cualquier entorno real hay que cambiarla y pasarla por
-- variable de entorno. Si se filtra, el alcance es menor que antes —este rol no
-- es superusuario y RLS le aplica— pero sigue siendo acceso a la base.
--
-- Idempotente: se puede correr sobre una base ya migrada.
-- =============================================================================

ALTER ROLE ambienta_app WITH LOGIN PASSWORD 'ambienta_app_dev';

-- El GRANT de `01_schema` corre una sola vez, sobre lo que existia entonces.
-- Se repite aca para que una base ya migrada —con tablas y secuencias nacidas
-- en 04, 05 y 06— no deje al rol sin permisos sobre ellas.
GRANT USAGE ON SCHEMA public TO ambienta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ambienta_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ambienta_app;

-- El registro de auditoria es inmutable (RNF-08, RNF-25): se escribe y se lee,
-- nunca se corrige. Lo sostiene la base, no la aplicacion.
REVOKE UPDATE, DELETE ON audit_log FROM ambienta_app;
REVOKE UPDATE, DELETE ON entity_status_history FROM ambienta_app;

DO $$
DECLARE
    salta_rls boolean;
BEGIN
    SELECT rolbypassrls OR rolsuper INTO salta_rls
    FROM pg_roles WHERE rolname = 'ambienta_app';

    IF salta_rls THEN
        RAISE EXCEPTION
            'ambienta_app puede saltarse RLS: conectar la API con el no '
            'protegeria nada. Revisar que no sea superusuario ni tenga '
            'BYPASSRLS.';
    END IF;

    RAISE NOTICE 'OK · ambienta_app puede conectarse y RLS le aplica';
END $$;
