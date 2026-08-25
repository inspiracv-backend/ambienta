-- ============================================================================
-- Todo Usuario Interno pertenece a un Departamento (RF-11, #101)
-- ============================================================================
--
-- `openspec/analisis/seccion-perfil-empresa.md:12`, literal: *"todo Usuario
-- Interno debe pertenecer obligatoriamente a un Departamento definido en el
-- Perfil Empresa"*. Hasta hoy `users.department_id` era nullable y nada lo
-- exigia.
--
-- ## Por que NO es un `NOT NULL` a secas
--
-- Seria la lectura literal y estaria mal. `users.user_type` admite cinco
-- valores y **solo dos son "Usuario Interno"**:
--
--   `internal`, `tenant_admin`   personas de la empresa -> SI llevan departamento
--   `platform_admin`             es nuestro, no de la empresa
--   `manager`                    opera sobre varias empresas
--   `guest`                      ni siquiera deberia existir como fila (D2 del
--                                cambio de credenciales), pero el CHECK lo admite
--
-- Un `NOT NULL` plano obligaria al Admin Global a pertenecer a un departamento
-- de una empresa cliente, que no significa nada. Peor: como el CHECK de
-- `user_type` ya admite esos valores, la restriccion habria que romperla el dia
-- que entre el primero — y romper una restriccion siempre termina en quitarla.
--
-- Por eso va un CHECK **condicionado al tipo**, que es exactamente lo que dice
-- el requisito.
--
-- ## El relleno previo, y por que hace falta mirarlo
--
-- Un CHECK nuevo se valida contra las filas existentes: si alguna lo incumple,
-- **la migracion falla entera**. Hoy las 7 filas tienen departamento (medido
-- antes de escribir esto), asi que no hay nada que rellenar. El bloque de abajo
-- existe igual porque esta migracion tambien corre sobre bases que no son esta.
--
-- El relleno **no inventa un departamento nuevo**: usa el primero de la empresa.
-- Crear uno "Sin asignar" seria una categoria que despues nadie vacia, y el
-- equipo eligio explicitamente la via estricta.
--
-- Si una empresa tiene usuarios internos y **ningun** departamento, la
-- migracion se detiene con un mensaje. Es a proposito: significa que hay datos
-- que alguien tiene que mirar, y adivinar por ellos seria peor.
-- ============================================================================

DO $$
DECLARE
    huerfanos int;
    empresas_sin_departamento text;
BEGIN
    SELECT count(*) INTO huerfanos
    FROM users
    WHERE deleted_at IS NULL
      AND department_id IS NULL
      AND user_type IN ('internal', 'tenant_admin');

    IF huerfanos = 0 THEN
        RAISE NOTICE 'Sin usuarios internos huerfanos: no hay nada que rellenar.';
    ELSE
        SELECT string_agg(DISTINCT u.tenant_id::text, ', ')
          INTO empresas_sin_departamento
        FROM users u
        WHERE u.deleted_at IS NULL
          AND u.department_id IS NULL
          AND u.user_type IN ('internal', 'tenant_admin')
          AND NOT EXISTS (
              SELECT 1 FROM departments d
              WHERE d.tenant_id = u.tenant_id AND d.deleted_at IS NULL
          );

        IF empresas_sin_departamento IS NOT NULL THEN
            RAISE EXCEPTION
              'Hay usuarios internos sin departamento en empresas que no tienen '
              'ningun departamento creado: %. Creales al menos uno antes de '
              'aplicar esta migracion — elegir por ellas seria inventar '
              'estructura organizacional.', empresas_sin_departamento;
        END IF;

        UPDATE users u
        SET department_id = (
            SELECT d.id FROM departments d
            WHERE d.tenant_id = u.tenant_id AND d.deleted_at IS NULL
            ORDER BY d.created_at, d.id
            LIMIT 1
        )
        WHERE u.deleted_at IS NULL
          AND u.department_id IS NULL
          AND u.user_type IN ('internal', 'tenant_admin');

        RAISE NOTICE 'Rellenados % usuarios internos con el primer departamento de su empresa.', huerfanos;
    END IF;
END $$;


-- El CHECK condicionado al tipo. `NOT VALID` no se usa a proposito: se quiere
-- que falle ahora si algo quedo mal, y no dentro de seis meses al primer UPDATE.
ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_interno_con_departamento;
ALTER TABLE users ADD CONSTRAINT ck_users_interno_con_departamento
    CHECK (
        user_type NOT IN ('internal', 'tenant_admin')
        OR department_id IS NOT NULL
    );

COMMENT ON CONSTRAINT ck_users_interno_con_departamento ON users IS
  'RF-11: todo Usuario Interno pertenece a un Departamento. Solo aplica a '
  '`internal` y `tenant_admin` — un Admin Global o un Gestor no pertenecen a '
  'un departamento de una empresa cliente.';


-- Indice para la comprobacion de "este departamento tiene gente", que ahora
-- corre en cada intento de borrado. Sin el, borrar un departamento hace un
-- recorrido completo de `users`.
CREATE INDEX IF NOT EXISTS ix_users_department
    ON users (department_id) WHERE deleted_at IS NULL AND department_id IS NOT NULL;
