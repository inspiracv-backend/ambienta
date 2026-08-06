-- ============================================================================
-- 04 — Vinculo con Clerk (ADR-006)
-- ============================================================================
-- Spec: openspec/changes/integracion-clerk-auth/
--
-- Clerk es el proveedor de identidad; el usuario sigue viviendo en `users`.
-- Esta columna es el unico puente entre ambos mundos.
--
-- NOTA: el repositorio todavia no tiene herramienta de migraciones (ABA-12
-- sigue abierta). Mientras tanto los cambios de esquema van como archivos
-- numerados que se aplican en orden. Cuando se elija la herramienta, este
-- archivo se porta como la migracion correspondiente.
-- ============================================================================

BEGIN;

-- Nullable a proposito: los usuarios del seed de desarrollo no existen en
-- Clerk. Con NOT NULL, `db/02_seed.sql` dejaria de cargar y no se podria
-- levantar el proyecto sin una cuenta del proveedor.
--
-- UNIQUE admite varios NULL en PostgreSQL, asi que no hay conflicto entre
-- todos los usuarios locales.
ALTER TABLE users ADD COLUMN IF NOT EXISTS clerk_id text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_clerk_id'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT uq_users_clerk_id UNIQUE (clerk_id);
    END IF;
END $$;

COMMENT ON COLUMN users.clerk_id IS
    'Identificador del usuario en Clerk (user_2abc...). NULL para usuarios '
    'creados directo en la base, como los del seed de desarrollo. '
    'El webhook de Clerk lo usa para encontrar a quien actualizar.';

-- El webhook busca por esta columna en cada evento. El UNIQUE ya crea un
-- indice, asi que no hace falta uno adicional.

COMMIT;
