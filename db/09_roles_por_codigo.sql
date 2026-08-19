-- ============================================================================
-- 09 — Corrige los permisos de cada rol y agrega el rol de servicio
-- ============================================================================
-- Spec: openspec/changes/sistema-actores-roles-rbac/specs/rbac/spec.md
--
-- ## El bug que corrige
--
-- `02_seed.sql` asignaba permisos a los roles **por id numerico**:
--
--     INSERT INTO role_permissions (role_id, permission_id, granted) VALUES
--       ('e000...001', 1, true), ('e000...001', 2, true), ...
--
-- Esos ids se eligieron para un catalogo de 20 permisos que el mismo archivo
-- intentaba insertar (`obligations.view`, `catalog.edit`, `documents.view`...).
-- Pero `03_seed_catalogos.sql` corre ANTES y ya siembra los 39 reales, asi que
-- el INSERT de `02_seed` no hace nada —lleva `ON CONFLICT (id) DO NOTHING`— y
-- los ids quedan apuntando a permisos **completamente distintos**:
--
--     id 1  se creyo `obligations.view`  y es `company_profile.read`
--     id 16 se creyo `tenants.manage`    y es `nonconformity.read`
--     id 20 se creyo `documents.edit`    y es `action_plan.write`
--
-- Resultado: los permisos de los tres roles **no estan incompletos, estan
-- mal**. El Admin Empresa quedaba sin `user.read`, `user.write` ni
-- `role.manage` — o sea sin poder administrar a sus propios empleados, que es
-- literalmente su definicion en CLAUDE.md §5.
--
-- No se noto nunca porque **ninguna ruta verificaba permisos todavia**. El dia
-- que se conecte la guarda, esto habria dejado a todo el mundo afuera con un
-- 403 inexplicable.
--
-- ## Como se corrige
--
-- Asignando **por codigo**, no por id. Un codigo dice que permiso es; un id no
-- dice nada, y cuando el catalogo cambia el error es silencioso.
--
-- Idempotente.
-- ============================================================================

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
--  1. Se borra la asignacion vieja de los tres roles del sistema
-- ───────────────────────────────────────────────────────────────────────────
--
-- Se borra en vez de completarse: lo que hay no es un subconjunto correcto al
-- que le falten filas, son filas equivocadas. Sumarle las que faltan dejaria
-- las erradas adentro.

DELETE FROM role_permissions
WHERE role_id IN (
    SELECT id FROM roles
    WHERE code IN ('admin_empresa', 'encargado_ambiental', 'operador')
);

-- ───────────────────────────────────────────────────────────────────────────
--  1b. Los tres roles del sistema existen en TODAS las empresas
-- ───────────────────────────────────────────────────────────────────────────
--
-- `roles.tenant_id` es NOT NULL: un rol pertenece a una empresa. `02_seed`
-- solo los creo para Minera Andes, asi que los usuarios de EcoGestion no
-- tenian ningun rol al que pertenecer — y por lo tanto ningun permiso.
--
-- No se noto porque nada verificaba permisos. Conectar la guarda habria dejado
-- a media empresa sin poder trabajar, y el sintoma —403 en todo— no apunta a
-- que le falten roles a su tenant.

INSERT INTO roles (tenant_id, code, name, is_system, description)
SELECT t.id, v.code, v.name, true, v.description
FROM tenants t
CROSS JOIN (VALUES
    ('admin_empresa', 'Administrador de Empresa',
     'Acceso total a la gestion de la empresa, incluidos usuarios y permisos'),
    ('encargado_ambiental', 'Encargado Ambiental',
     'Gestion de cumplimiento y obligaciones. No administra usuarios'),
    ('operador', 'Operador',
     'Lectura y ejecucion de las tareas que se le asignan')
) AS v(code, name, description)
WHERE t.deleted_at IS NULL
ON CONFLICT (tenant_id, code) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
--  2. Admin Empresa: todo lo de su empresa, nada de la plataforma
-- ───────────────────────────────────────────────────────────────────────────
--
-- "Gestiona su empresa y empleados" (CLAUDE.md §5). Eso incluye usuarios y
-- permisos: es quien decide quien hace que dentro de la empresa.
--
-- Lo unico que NO tiene es `platform.*`: administrar otras empresas o el
-- soporte de la plataforma es del Admin Global, y darselo le permitiria ver la
-- cartera de clientes.

INSERT INTO role_permissions (role_id, permission_id, granted)
SELECT r.id, p.id, true
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'admin_empresa'
  AND p.code NOT LIKE 'platform.%'
ON CONFLICT (role_id, permission_id) DO UPDATE SET granted = true;

-- ───────────────────────────────────────────────────────────────────────────
--  3. Encargado Ambiental: opera el cumplimiento, no administra la empresa
-- ───────────────────────────────────────────────────────────────────────────
--
-- "Operativo — crea/envia declaraciones" (CLAUDE.md §5). Hace el trabajo de
-- cumplimiento completo, pero no toca usuarios, permisos ni el perfil de la
-- empresa: eso es administracion.

INSERT INTO role_permissions (role_id, permission_id, granted)
SELECT r.id, p.id, true
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'encargado_ambiental'
  AND p.code IN (
    'company_profile.read',
    'legal_matrix.read', 'legal_matrix.write', 'legal_matrix.article.evaluate',
    'catalog.read',
    'obligation.read', 'obligation.write', 'obligation.submit',
    'task.read', 'task.write',
    'audit.read', 'audit.write',
    'nonconformity.read', 'nonconformity.write',
    'action_plan.read', 'action_plan.write',
    'environmental_aspect.read', 'environmental_aspect.write',
    'risk_opportunity.read', 'risk_opportunity.write',
    'equipment.read', 'equipment.write',
    'document.read', 'document.write',
    'report.generate', 'chatbot.use',
    'user.read'
  )
ON CONFLICT (role_id, permission_id) DO UPDATE SET granted = true;

-- `legal_matrix.approve` y `nonconformity.close` quedan fuera a proposito:
-- aprobar el cumplimiento y cerrar una no conformidad son actos de
-- responsabilidad, y el analisis pidio separarlos de editar la evidencia.

-- ───────────────────────────────────────────────────────────────────────────
--  4. Operador: ejecuta lo que le asignan
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO role_permissions (role_id, permission_id, granted)
SELECT r.id, p.id, true
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'operador'
  AND p.code IN (
    'company_profile.read',
    'legal_matrix.read', 'catalog.read',
    'obligation.read',
    'task.read', 'task.write',
    'audit.read', 'nonconformity.read', 'action_plan.read',
    'document.read', 'chatbot.use'
  )
ON CONFLICT (role_id, permission_id) DO UPDATE SET granted = true;

-- ───────────────────────────────────────────────────────────────────────────
--  5. Rol de servicio: solo lectura, para integraciones
-- ───────────────────────────────────────────────────────────────────────────
--
-- Para que el servicio de IA —o cualquier integracion— consulte sin poder
-- modificar nada. Los 15 permisos `.read` y ninguno mas.
--
-- **Sigue sujeto a RLS.** Un rol de solo lectura que se saltara el aislamiento
-- seria PEOR que uno de escritura que lo respeta: leeria todas las empresas.
-- Por eso es un rol de aplicacion como cualquier otro, con su `tenant_id`, y
-- no un rol de PostgreSQL con BYPASSRLS.
--
-- Se crea uno por empresa porque `roles.tenant_id` es NOT NULL: un usuario de
-- servicio ve **una** empresa. Si una integracion necesita varias, necesita un
-- usuario por cada una — que es la respuesta correcta, no un atajo.

INSERT INTO roles (tenant_id, code, name, is_system, description)
SELECT t.id, 'servicio_lectura', 'Servicio (solo lectura)', true,
       'Integraciones y servicio de IA. Solo consulta; no modifica nada.'
FROM tenants t
WHERE t.deleted_at IS NULL
ON CONFLICT (tenant_id, code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id, granted)
SELECT r.id, p.id, true
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'servicio_lectura'
  AND p.code LIKE '%.read'
ON CONFLICT (role_id, permission_id) DO UPDATE SET granted = true;

-- ───────────────────────────────────────────────────────────────────────────
--  6. Nadie del sistema se queda sin rol
-- ───────────────────────────────────────────────────────────────────────────
--
-- Un usuario sin rol no tiene ningun permiso: con la guarda conectada recibe
-- 403 en todo. Los usuarios cargados a mano —los de desarrollo, los que entran
-- por SSO antes de que exista el webhook— no tienen ninguno, y sin esto
-- quedarian bloqueados de su propio sistema el dia que se active.
--
-- `tenant_admin` recibe Admin Empresa; el resto, Encargado Ambiental. Es el
-- criterio conservador: nadie queda sin poder trabajar, y nadie recibe mas de
-- lo que su tipo de usuario ya declaraba.

INSERT INTO user_roles (user_id, role_id, tenant_id)
SELECT u.id, r.id, u.tenant_id
FROM users u
JOIN roles r ON r.tenant_id = u.tenant_id
             AND r.code = CASE
                 WHEN u.user_type = 'tenant_admin' THEN 'admin_empresa'
                 ELSE 'encargado_ambiental'
             END
WHERE u.deleted_at IS NULL
  AND u.user_type IN ('tenant_admin', 'internal')
  AND NOT EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id)
ON CONFLICT (user_id, role_id) DO NOTHING;

COMMIT;
