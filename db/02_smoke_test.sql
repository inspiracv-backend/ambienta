-- ═══════════════════════════════════════════════════════════════════════════
--  Smoke test del esquema.
--
--  No verifica que los objetos existan (eso lo dice el catalogo), sino que las
--  garantias que el esquema promete se cumplan de verdad:
--    1. RLS aisla los datos entre empresas
--    2. RLS impide escribir en otra empresa
--    3. El audit log es inmutable para la aplicacion
--    4. Los CHECK de negocio rechazan estados invalidos
--    5. El ciclo documents <-> document_versions se puede poblar
--
--  Ejecutar despues de 01_schema.sql. Deja la base como la encontro.
-- ═══════════════════════════════════════════════════════════════════════════

\set ON_ERROR_STOP on
\pset pager off

BEGIN;

-- ── Datos de prueba (como superusuario: RLS no aplica) ────────────────────
-- Se resuelve el pais por su ISO en vez de asumir id=1: el test debe correr
-- igual sobre una base recien creada o sobre una que ya tiene los catalogos.

INSERT INTO countries (iso2, iso3, name) VALUES ('CL','CHL','Chile')
ON CONFLICT (iso2) DO NOTHING;

INSERT INTO tenants (id, country_id, rut_tax_id, legal_name, status)
SELECT v.id::uuid, (SELECT id FROM countries WHERE iso2 = 'CL'), v.rut, v.nombre, 'active'
FROM (VALUES
    ('11111111-1111-1111-1111-111111111111', '76.111.111-1', 'Empresa A'),
    ('22222222-2222-2222-2222-222222222222', '76.222.222-2', 'Empresa B')
) AS v(id, rut, nombre);

INSERT INTO users (id, tenant_id, email, full_name, user_type, status)
VALUES ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
        'ana@empresa-a.cl', 'Ana Perez', 'tenant_admin', 'active'),
       ('bbbbbbbb-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
        'beto@empresa-b.cl', 'Beto Soto', 'tenant_admin', 'active');

INSERT INTO facilities (id, tenant_id, code, name, facility_type)
VALUES ('aaaaaaaa-0000-0000-0000-00000000000f', '11111111-1111-1111-1111-111111111111',
        'PL-01', 'Planta Rancagua', 'planta'),
       ('bbbbbbbb-0000-0000-0000-00000000000f', '22222222-2222-2222-2222-222222222222',
        'PL-01', 'Planta Talca', 'planta');

-- Mismo `code` en ambas empresas: la unicidad es por tenant, no global.
-- Si esto fallara, dos clientes no podrian usar sus propios codigos internos.

INSERT INTO audit_log (tenant_id, action, entity_type, entity_id)
VALUES ('11111111-1111-1111-1111-111111111111', 'create', 'facility',
        'aaaaaaaa-0000-0000-0000-00000000000f');


-- ── 1. RLS aisla la lectura ───────────────────────────────────────────────

SET LOCAL ROLE ambienta_app;
SET LOCAL ambienta.tenant_id = '11111111-1111-1111-1111-111111111111';

DO $$
DECLARE n int; nombre text;
BEGIN
    SELECT count(*) INTO n FROM facilities;
    IF n <> 1 THEN
        RAISE EXCEPTION 'FALLO 1a: la empresa A ve % plantas, deberia ver 1', n;
    END IF;

    SELECT name INTO nombre FROM facilities;
    IF nombre <> 'Planta Rancagua' THEN
        RAISE EXCEPTION 'FALLO 1b: la empresa A ve "%", que no es suya', nombre;
    END IF;

    SELECT count(*) INTO n FROM users;
    IF n <> 1 THEN
        RAISE EXCEPTION 'FALLO 1c: la empresa A ve % usuarios, deberia ver 1', n;
    END IF;

    RAISE NOTICE 'OK 1 · RLS aisla la lectura entre empresas';
END $$;


-- ── 2. RLS impide escribir en otra empresa ────────────────────────────────

DO $$
BEGIN
    BEGIN
        INSERT INTO facilities (tenant_id, code, name, facility_type)
        VALUES ('22222222-2222-2222-2222-222222222222', 'PL-99', 'Planta infiltrada', 'planta');
        RAISE EXCEPTION 'FALLO 2: se pudo insertar una fila en otra empresa';
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'OK 2 · RLS bloquea escribir en otra empresa';
    END;
END $$;


-- ── 3. El audit log es inmutable para la aplicacion ───────────────────────

DO $$
BEGIN
    BEGIN
        UPDATE audit_log SET action = 'delete';
        RAISE EXCEPTION 'FALLO 3a: la aplicacion pudo modificar el audit log';
    EXCEPTION
        WHEN insufficient_privilege THEN NULL;
    END;

    BEGIN
        DELETE FROM audit_log;
        RAISE EXCEPTION 'FALLO 3b: la aplicacion pudo borrar del audit log';
    EXCEPTION
        WHEN insufficient_privilege THEN NULL;
    END;

    RAISE NOTICE 'OK 3 · El audit log no admite UPDATE ni DELETE (RNF-25)';
END $$;

RESET ROLE;


-- ── 4. Los CHECK de negocio rechazan estados invalidos ────────────────────

DO $$
DECLARE nc_id uuid;
BEGIN
    -- Un hallazgo cerrado sin fecha de cierre no deberia existir (RF-49).
    BEGIN
        INSERT INTO nonconformities (tenant_id, code, title, description, severity, status)
        VALUES ('11111111-1111-1111-1111-111111111111', 'NC-BAD', 'x', 'y', 'major', 'closed');
        RAISE EXCEPTION 'FALLO 4a: se acepto un hallazgo cerrado sin closed_at';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    -- Un plan de accion sin origen no es trazable.
    BEGIN
        INSERT INTO action_plans (tenant_id, title, objective)
        VALUES ('11111111-1111-1111-1111-111111111111', 'Plan huerfano', 'z');
        RAISE EXCEPTION 'FALLO 4b: se acepto un plan de accion sin origen';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    -- Un riesgo que dice venir de un aspecto ambiental debe referenciarlo.
    BEGIN
        INSERT INTO risks_opportunities (tenant_id, code, entry_type, description, origin)
        VALUES ('11111111-1111-1111-1111-111111111111', 'R-01', 'risk', 'x', 'environmental_aspect');
        RAISE EXCEPTION 'FALLO 4c: se acepto un riesgo sin el aspecto que dice originarlo';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    -- Un contrato no puede ser de una empresa consigo misma.
    BEGIN
        INSERT INTO contracts (tenant_id, manager_tenant_id, client_tenant_id,
                               contract_number, title, start_date)
        VALUES ('11111111-1111-1111-1111-111111111111',
                '11111111-1111-1111-1111-111111111111',
                '11111111-1111-1111-1111-111111111111', 'C-01', 'x', current_date);
        RAISE EXCEPTION 'FALLO 4d: se acepto un contrato de una empresa consigo misma';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    -- El caso valido si debe pasar.
    INSERT INTO nonconformities (tenant_id, code, title, description, severity, status,
                                 closed_at, record_type)
    VALUES ('11111111-1111-1111-1111-111111111111', 'NC-OK', 'Hallazgo', 'desc',
            'major', 'closed', now(), 'no_conformidad')
    RETURNING id INTO nc_id;

    IF nc_id IS NULL THEN
        RAISE EXCEPTION 'FALLO 4e: no se pudo insertar un hallazgo valido';
    END IF;

    RAISE NOTICE 'OK 4 · Los CHECK de negocio rechazan lo invalido y aceptan lo valido';
END $$;


-- ── 5. El ciclo documents <-> document_versions se puede poblar ───────────
--     Es el unico punto donde la FK diferida es imprescindible: el documento
--     apunta a su version vigente y la version apunta al documento.

DO $$
DECLARE doc_id uuid; ver_id uuid;
BEGIN
    INSERT INTO documents (tenant_id, document_type, title)
    VALUES ('11111111-1111-1111-1111-111111111111', 'evidence', 'Informe de ensayo')
    RETURNING id INTO doc_id;

    INSERT INTO document_versions (tenant_id, document_id, version_no, storage_provider,
                                   storage_key, file_name, mime_type, size_bytes)
    VALUES ('11111111-1111-1111-1111-111111111111', doc_id, 1, 'google_drive',
            'drive-key-abc', 'informe.pdf', 'application/pdf', 12345)
    RETURNING id INTO ver_id;

    UPDATE documents SET current_version_id = ver_id WHERE id = doc_id;

    RAISE NOTICE 'OK 5 · El ciclo documento <-> version se puede poblar';
END $$;


-- ── 6. La unicidad por tenant permite codigos repetidos entre empresas ────

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM facilities WHERE code = 'PL-01';
    IF n <> 2 THEN
        RAISE EXCEPTION 'FALLO 6: se esperaban 2 plantas con codigo PL-01 (una por empresa), hay %', n;
    END IF;

    BEGIN
        INSERT INTO facilities (tenant_id, code, name, facility_type)
        VALUES ('11111111-1111-1111-1111-111111111111', 'PL-01', 'Duplicada', 'planta');
        RAISE EXCEPTION 'FALLO 6b: se acepto un codigo de planta duplicado dentro de la misma empresa';
    EXCEPTION
        WHEN unique_violation THEN NULL;
    END;

    RAISE NOTICE 'OK 6 · El codigo es unico por empresa, no globalmente';
END $$;


-- ── 7. Sin tenant en la sesion no se ve nada (falla cerrado) ──────────────

SET LOCAL ROLE ambienta_app;
RESET ambienta.tenant_id;

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM facilities;
    IF n <> 0 THEN
        RAISE EXCEPTION 'FALLO 7: sin tenant en la sesion se ven % filas; deberia fallar cerrado', n;
    END IF;
    RAISE NOTICE 'OK 7 · Sin tenant en la sesion no se devuelve ninguna fila';
END $$;

RESET ROLE;


-- ── 8. Una matriz por empresa, ano, instalacion y version ─────────────────
--
-- El caso que importa es facility_id NULL ("nivel empresa"). Con la unicidad
-- por defecto de PostgreSQL los NULL no colisionan entre si, asi que se
-- podrian crear infinitas matrices de empresa para el mismo ano sin que la
-- base dijera nada. Lo cubre NULLS NOT DISTINCT en uq_matrices_periodo.

DO $$
BEGIN
    INSERT INTO tenant_legal_matrices (tenant_id, name, period_year, version_no)
    VALUES ('11111111-1111-1111-1111-111111111111', 'Matriz 2026', 2026, 1);

    BEGIN
        INSERT INTO tenant_legal_matrices (tenant_id, name, period_year, version_no)
        VALUES ('11111111-1111-1111-1111-111111111111', 'Matriz 2026 otra vez', 2026, 1);
        RAISE EXCEPTION 'FALLO 8: se acepto una segunda matriz de empresa para el mismo ano y version';
    EXCEPTION
        WHEN unique_violation THEN NULL;
    END;

    RAISE NOTICE 'OK 8 · No se duplica la matriz de un periodo, ni a nivel empresa';
END $$;


-- ── 9. Permisos individuales por encima del rol (RF-12) ───────────────────

DO $$
DECLARE pid smallint;
BEGIN
    SELECT id INTO pid FROM permissions ORDER BY id LIMIT 1;
    IF pid IS NULL THEN
        RAISE EXCEPTION 'FALLO 9: no hay permisos sembrados; corre 03_seed_catalogos.sql antes';
    END IF;

    -- Denegacion explicita: el caso que no se puede expresar solo con roles.
    INSERT INTO user_permissions (user_id, permission_id, tenant_id, granted, reason)
    VALUES ('aaaaaaaa-0000-0000-0000-000000000001', pid,
            '11111111-1111-1111-1111-111111111111', false, 'Smoke test');

    BEGIN
        INSERT INTO user_permissions (user_id, permission_id, tenant_id)
        VALUES ('aaaaaaaa-0000-0000-0000-000000000001', pid,
                '11111111-1111-1111-1111-111111111111');
        RAISE EXCEPTION 'FALLO 9b: se acepto el mismo permiso dos veces para el mismo usuario';
    EXCEPTION
        WHEN unique_violation THEN NULL;
    END;

    RAISE NOTICE 'OK 9 · Se puede conceder y denegar un permiso a un usuario concreto';
END $$;


ROLLBACK;
