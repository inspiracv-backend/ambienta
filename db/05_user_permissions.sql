-- ============================================================================
-- 05 — Permisos individuales y unicidad de matriz (RF-12)
-- ============================================================================
-- Spec: openspec/changes/sistema-actores-roles-rbac/specs/rbac/spec.md
--
-- Lleva a una base YA CREADA los tres cambios que se agregaron a
-- 01_schema.sql. Sin esto existen solo en bases nuevas, y nadie se entera de
-- la diferencia hasta que algo falla contra su propio esquema.
--
-- Los tres viajan juntos porque entraron en la misma edicion del esquema:
--   1. Tabla user_permissions
--   2. article_compliance: unicidad que trate los NULL como iguales
--   3. tenant_legal_matrices: una matriz por empresa, ano, planta y version
--
-- Idempotente: se puede correr sobre una base nueva (donde 01_schema ya lo
-- creo todo) y sobre una vieja, las veces que haga falta.
--
-- NOTA sobre migraciones: el repositorio todavia no tiene herramienta
-- (ABA-12 sigue abierta). Mientras tanto los cambios de esquema van como
-- archivos numerados. Cuando se elija la herramienta, este archivo se porta
-- como la migracion correspondiente.
-- ============================================================================

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
--  1. user_permissions
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_permissions (
    user_id       uuid         NOT NULL,
    permission_id smallint     NOT NULL,
    tenant_id     uuid         NOT NULL,
    granted       boolean      NOT NULL DEFAULT true,
    granted_by    uuid,
    granted_at    timestamptz  NOT NULL DEFAULT now(),
    reason        text,
    PRIMARY KEY (user_id, permission_id)
);

COMMENT ON TABLE user_permissions IS
  'Concesion o denegacion individual, por encima del rol (RF-12).';
COMMENT ON COLUMN user_permissions.granted IS
  'false = denegacion explicita; gana sobre lo que otorgue cualquier rol.';
COMMENT ON COLUMN user_permissions.reason IS
  'Por que se dio o quito. Lo pide RNF-08 para permisos fuera del rol.';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_userperm_user') THEN
        ALTER TABLE user_permissions ADD CONSTRAINT fk_userperm_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_userperm_permission') THEN
        ALTER TABLE user_permissions ADD CONSTRAINT fk_userperm_permission
            FOREIGN KEY (permission_id) REFERENCES permissions(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_userperm_tenant') THEN
        ALTER TABLE user_permissions ADD CONSTRAINT fk_userperm_tenant
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_userperm_granted_by') THEN
        ALTER TABLE user_permissions ADD CONSTRAINT fk_userperm_granted_by
            FOREIGN KEY (granted_by) REFERENCES users(id);
    END IF;
END $$;

-- La PK (user_id, permission_id) ya cubre "que permisos tiene este usuario".
-- Este indice cubre el sentido inverso, que es el de RLS: filtrar por empresa.
CREATE INDEX IF NOT EXISTS ix_userperm_tenant ON user_permissions (tenant_id);

-- ───────────────────────────────────────────────────────────────────────────
--  1b. RLS y permisos del rol de aplicacion
--
--  IMPRESCINDIBLE, y facil de olvidar: en 01_schema.sql las politicas RLS las
--  crea un bucle sobre las tablas con tenant_id, y los permisos del rol salen
--  de un GRANT ON ALL TABLES. Los dos corren UNA vez, al crear el esquema.
--
--  Una tabla creada despues por una migracion no hereda ninguno de los dos:
--  quedaria sin aislamiento entre empresas y sin permisos para la aplicacion.
-- ───────────────────────────────────────────────────────────────────────────

ALTER TABLE user_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_permissions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON user_permissions;
CREATE POLICY tenant_isolation ON user_permissions
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ambienta_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON user_permissions TO ambienta_app;
    END IF;
END $$;

-- ───────────────────────────────────────────────────────────────────────────
--  2. article_compliance: los NULL dejan de ser distintos entre si
--
--  facility_id nullable significa "evaluacion a nivel empresa", que es un
--  valor con significado y no un dato faltante. Con la unicidad por defecto
--  los NULL no colisionan, asi que se podia evaluar el mismo articulo a nivel
--  empresa tantas veces como se quisiera.
-- ───────────────────────────────────────────────────────────────────────────

DO $$
DECLARE duplicados bigint;
BEGIN
    -- La restriccion nueva es MAS estricta. Si ya hay duplicados, recrearla
    -- falla a mitad de camino: mejor decir cuantos hay y detenerse.
    SELECT count(*) INTO duplicados FROM (
        SELECT matrix_norm_id, article_id, facility_id
        FROM article_compliance
        WHERE deleted_at IS NULL
        GROUP BY matrix_norm_id, article_id, facility_id
        HAVING count(*) > 1
    ) d;

    IF duplicados > 0 THEN
        RAISE EXCEPTION
            'Hay % combinaciones duplicadas en article_compliance. Resolverlas '
            'antes de aplicar la unicidad nueva: SELECT matrix_norm_id, '
            'article_id, facility_id, count(*) FROM article_compliance GROUP BY '
            '1,2,3 HAVING count(*) > 1;', duplicados;
    END IF;

    -- La bandera NULLS NOT DISTINCT vive en el INDICE que respalda al
    -- constraint (pg_index.indnullsnotdistinct), no en pg_constraint. Se llega
    -- por conindid. Consultarla en pg_constraint falla: esa columna no existe.
    IF EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_index i ON i.indexrelid = c.conindid
        WHERE c.conname = 'uq_article_compliance'
          AND c.conrelid = 'article_compliance'::regclass
          AND i.indnullsnotdistinct IS NOT TRUE
    ) THEN
        ALTER TABLE article_compliance DROP CONSTRAINT uq_article_compliance;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_article_compliance'
    ) THEN
        ALTER TABLE article_compliance
            ADD CONSTRAINT uq_article_compliance
            UNIQUE NULLS NOT DISTINCT (matrix_norm_id, article_id, facility_id);
    END IF;
END $$;

-- ───────────────────────────────────────────────────────────────────────────
--  3. tenant_legal_matrices: una matriz por empresa, ano, planta y version
--
--  Va como indice parcial y no como CONSTRAINT por el borrado logico: una
--  matriz archivada no debe impedir crear la del mismo periodo de nuevo.
-- ───────────────────────────────────────────────────────────────────────────

DO $$
DECLARE duplicados bigint;
BEGIN
    SELECT count(*) INTO duplicados FROM (
        SELECT tenant_id, period_year, facility_id, version_no
        FROM tenant_legal_matrices
        WHERE deleted_at IS NULL
        GROUP BY tenant_id, period_year, facility_id, version_no
        HAVING count(*) > 1
    ) d;

    IF duplicados > 0 THEN
        RAISE EXCEPTION
            'Hay % periodos con mas de una matriz vigente. Archivar las '
            'sobrantes (deleted_at) antes de aplicar la unicidad.', duplicados;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_matrices_periodo ON tenant_legal_matrices
    (tenant_id, period_year, facility_id, version_no) NULLS NOT DISTINCT
    WHERE deleted_at IS NULL;

COMMIT;


-- ───────────────────────────────────────────────────────────────────────────
--  Verificacion rapida tras aplicar
-- ───────────────────────────────────────────────────────────────────────────
--
--   SELECT relrowsecurity, relforcerowsecurity
--     FROM pg_class WHERE relname = 'user_permissions';
--   -- ambas deben ser true
--
--   SELECT polname FROM pg_policy p
--     JOIN pg_class c ON c.oid = p.polrelid
--    WHERE c.relname = 'user_permissions';
--   -- debe devolver tenant_isolation
--
--   SELECT i.indnullsnotdistinct FROM pg_constraint c
--     JOIN pg_index i ON i.indexrelid = c.conindid
--    WHERE c.conname = 'uq_article_compliance';
--   -- debe ser true
