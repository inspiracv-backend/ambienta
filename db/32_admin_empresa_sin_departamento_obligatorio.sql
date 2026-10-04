-- ============================================================================
-- El Admin Empresa no necesita departamento para existir (RF-08, RF-10, RF-11)
-- ============================================================================
--
-- `13_usuario_interno_con_departamento.sql` exige departamento a `internal` y a
-- `tenant_admin`. Lo segundo **impedia dar de alta cualquier empresa nueva**:
--
--   1. El Admin Empresa es quien crea los departamentos, en Perfil Empresa
--      (RF-10: "primer paso del Admin Empresa").
--   2. Para crear al Admin Empresa hacia falta un departamento.
--   3. Una empresa recien creada no tiene ninguno, y el Admin Global no puede
--      crearlos: no edita contenido de una empresa (CLAUDE.md §4).
--
-- No se veia porque las empresas del seed ya traian departamentos.
--
-- ## Por que esto sigue siendo RF-11 y no una excepcion
--
-- RF-11 dice *"todo Usuario Interno"*, y RF-08 enumera los tipos por separado:
-- Superadmin, **Admin Empresa**, **Usuario Interno**, Cliente, Gestor. Admin
-- Empresa no es un Usuario Interno. La migracion 13 los junto, y es la misma
-- lectura de mas que ella misma advierte sobre el `NOT NULL` plano.
--
-- Lo que NO cambia: un `internal` sigue sin poder existir sin departamento, ni
-- al crearse ni al editarse. Y no se inventa un departamento "Sin asignar" —
-- la migracion 13 lo descarto por buenas razones.
--
-- Idempotente. Relaja la restriccion, asi que ninguna fila existente la incumple.
-- ============================================================================

BEGIN;

ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_interno_con_departamento;
ALTER TABLE users ADD CONSTRAINT ck_users_interno_con_departamento
    CHECK (
        user_type <> 'internal'
        OR department_id IS NOT NULL
    );

COMMENT ON CONSTRAINT ck_users_interno_con_departamento ON users IS
  'RF-11: todo Usuario Interno pertenece a un Departamento. Solo `internal`: '
  'el Admin Empresa (`tenant_admin`) es quien crea los departamentos, y un '
  'Admin Global o un Gestor no pertenecen a uno de una empresa cliente.';

COMMIT;
