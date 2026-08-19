-- ============================================================================
-- Crear un usuario de servicio (solo lectura) para una integracion
-- ============================================================================
-- Para el servicio de IA, un conector externo, o cualquier cosa que consulte
-- Ambienta sin modificarlo.
--
-- ## Antes de correr esto
--
-- La persona o el proceso necesita **una cuenta en Clerk**, porque la API no
-- emite tokens propios: valida los de Clerk. Los pasos previos son:
--
--   1. Clerk -> Restrictions -> Allowlist: agregar su correo. Sin esto el
--      registro esta cerrado y no puede entrar.
--   2. Que entre una vez (con Google o con clave) para que Clerk le cree el id.
--   3. Clerk -> Users -> su usuario -> Public metadata:
--          {"tenant_id": "<uuid de la empresa>"}
--      Sin este paso entra y recibe 403 en todo: el claim `tenant_id` sale de
--      ahi, y sin el la API no sabe que datos mostrarle.
--   4. Copiar su User ID de Clerk (empieza con `user_`).
--
-- ## Como se corre
--
--   docker compose exec -T postgres psql -U ambienta -d ambienta \
--     -v correo="'ia@ejemplo.cl'" \
--     -v nombre="'Servicio IA'" \
--     -v clerk="'user_XXXXXXXXXXXX'" \
--     -v empresa="'a0000000-0000-0000-0000-000000000001'" \
--     -f db/scripts/crear_usuario_de_servicio.sql
--
-- ## Que ve y que no
--
-- **Una empresa, no todas.** `roles.tenant_id` es NOT NULL y RLS acota cada
-- consulta a la empresa declarada. Si la integracion necesita varias, necesita
-- un usuario por cada una — que es la respuesta correcta, no un atajo: un
-- usuario de solo lectura que cruzara empresas seria PEOR que uno de escritura
-- que respeta el aislamiento, porque leeria todo.
--
-- **Solo los 15 permisos `.read`.** No incluye `chatbot.use`: usar el chatbot
-- crea conversaciones y mensajes, o sea escribe. Si la integracion tiene que
-- guardar la conversacion, eso deberia hacerse con la sesion de la **persona**
-- que conversa, no con la cuenta de servicio — el registro de auditoria
-- necesita un responsable con nombre, y "el servicio" no lo es.
--
-- Idempotente: correrlo dos veces no duplica nada.
-- ============================================================================

BEGIN;

-- El usuario. `user_type = 'internal'`: pertenece a la empresa, no la
-- administra. Lo que puede hacer lo decide su rol, no este campo.
INSERT INTO users (tenant_id, email, full_name, user_type, status, clerk_id)
VALUES (:empresa::uuid, :correo, :nombre, 'internal', 'active', :clerk)
-- `email` es UNIQUE **global**, no por empresa: la misma direccion no puede
-- ser usuario de dos empresas. Para una integracion que consulte varias hacen
-- falta correos distintos —`ia+andes@`, `ia+eco@` no sirve, las subdirecciones
-- estan bloqueadas en Clerk— o cuentas separadas.
ON CONFLICT (email) DO UPDATE
    SET clerk_id = EXCLUDED.clerk_id,
        full_name = EXCLUDED.full_name,
        status = 'active';

-- El rol de solo lectura de esa empresa. Lo crea `09_roles_por_codigo.sql`
-- para todas, asi que aca solo se vincula.
INSERT INTO user_roles (user_id, role_id, tenant_id)
SELECT u.id, r.id, u.tenant_id
FROM users u
JOIN roles r ON r.tenant_id = u.tenant_id AND r.code = 'servicio_lectura'
WHERE u.email = :correo AND u.tenant_id = :empresa::uuid
ON CONFLICT (user_id, role_id) DO NOTHING;

COMMIT;

-- Comprobacion: que quedo con rol y con cuantos permisos.
SELECT u.email,
       r.code AS rol,
       count(*) FILTER (WHERE rp.granted) AS permisos,
       count(*) FILTER (WHERE rp.granted AND p.code NOT LIKE '%.read') AS escrituras
FROM users u
JOIN user_roles ur ON ur.user_id = u.id
JOIN roles r ON r.id = ur.role_id
LEFT JOIN role_permissions rp ON rp.role_id = r.id
LEFT JOIN permissions p ON p.id = rp.permission_id
WHERE u.email = :correo
GROUP BY u.email, r.code;
