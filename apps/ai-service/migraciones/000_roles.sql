-- Roles de la base de conocimiento (SPEC-03).
--
-- Corre con un usuario administrador. Los roles son del clúster, no de la base, así que el
-- script es idempotente. Las claves llegan como parámetros desde `migrar.py`, nunca escritas
-- acá.
--
--   ia_consulta       lee, con RLS. Es con el que atiende las consultas.
--   ia_sincronizador  escribe el catálogo público. Solo filas con tenant_id nulo.
--
-- Ninguno es dueño de las tablas ni tiene BYPASSRLS: el dueño se salta RLS salvo FORCE, y por
-- eso las tablas quedan a nombre del administrador.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_consulta') THEN
        CREATE ROLE ia_consulta LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ia_sincronizador') THEN
        CREATE ROLE ia_sincronizador LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

ALTER ROLE ia_consulta NOBYPASSRLS PASSWORD :'clave_consulta';
ALTER ROLE ia_sincronizador NOBYPASSRLS PASSWORD :'clave_sincronizador';
