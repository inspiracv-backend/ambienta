-- ═══════════════════════════════════════════════════════════════════════════
--  AMBIENTA — Esquema PostgreSQL
--  Basado en modelo_preliminar_PostgreSQL v2 (backend senior, 31-jul-2026)
--  + 4 entidades de ISO 14001 que el modelo v2 no cubria.
--
--  Motor objetivo: PostgreSQL 16 + pgvector
--  Ejecutar:  psql -f 01_schema.sql
--
--  ─────────────────────────────────────────────────────────────────────────
--  ALCANCE Y SUPUESTOS — leer antes de ejecutar
--  ─────────────────────────────────────────────────────────────────────────
--
--  Este script implementa las 47 tablas entregadas por el backend senior mas
--  las 4 entidades de ISO 14001 (environmental_aspects, risks_opportunities,
--  regulated_equipment, equipment_operators) que el frontend ya usa y el
--  modelo v2 no contemplaba.
--
--  NO implementa el borrador v1.8 del Analisis Funcional (RF-90 a RF-114:
--  instrumentos de auditoria, checklist por clausula, entidad Hallazgo
--  separada, informacion documentada y colaboracion). Ese borrador tiene 9
--  decisiones abiertas y CLAUDE.md §1 exige spec aprobada antes de
--  implementar. Va en una migracion posterior.
--
--  Decisiones tomadas por defecto, pendientes de confirmar con el equipo:
--
--   * Severidad de un hallazgo: se usa minor/major/critical del modelo del
--     backend. RF-100 del borrador v1.8 pide que la escala sea configurable
--     por empresa; cuando se apruebe, este CHECK pasa a ser tabla de catalogo.
--
--   * Estados de un hallazgo: se usan los 6 del backend. El frontend maneja 3
--     y el borrador v1.8 modela las etapas como entidad. Se conservan los 6 y
--     se agrega improvement_stages como JSONB para no perder lo que el
--     frontend ya guarda.
--
--   * El stack del backend (NestJS vs FastAPI) NO afecta este script: el
--     esquema es el mismo en ambos casos.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
--  1. EXTENSIONES
-- ───────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;     -- correos case-insensitive
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- busqueda por similitud
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector (RAG del catalogo)


-- ───────────────────────────────────────────────────────────────────────────
--  2. FUNCIONES DE APOYO
-- ───────────────────────────────────────────────────────────────────────────

-- Mantiene updated_at sin que cada repositorio tenga que acordarse.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Tenant activo de la sesion. Lo setea la API con
--   SET LOCAL ambienta.tenant_id = '<uuid>';
-- Devuelve NULL si no hay ninguno, lo que hace que las policies RLS no
-- devuelvan filas: preferible a fallar abierto.
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS uuid AS $$
BEGIN
    RETURN nullif(current_setting('ambienta.tenant_id', true), '')::uuid;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;


-- ───────────────────────────────────────────────────────────────────────────
--  3. TABLAS
--
--  Se crean sin claves foraneas; todas las FK se agregan en la seccion 4.
--  Motivo: el modelo tiene dos ciclos reales (tenants.created_by -> users y
--  documents.current_version_id -> document_versions) que impiden un orden
--  de creacion valido. Separarlo evita tener que ordenar 51 tablas a mano.
-- ───────────────────────────────────────────────────────────────────────────

-- ── 3.1 Multi-tenant, organizacion y RBAC ─────────────────────────────────

CREATE TABLE countries (
    id                  smallserial   PRIMARY KEY,
    iso2                char(2)       NOT NULL UNIQUE,
    iso3                char(3)       NOT NULL UNIQUE,
    name                varchar(120)  NOT NULL,
    default_timezone    varchar(64)   NOT NULL DEFAULT 'America/Santiago',
    metadata            jsonb         NOT NULL DEFAULT '{}'::jsonb
);
COMMENT ON TABLE countries IS 'Catalogo global de paises. Sin tenant_id.';

CREATE TABLE tenants (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    country_id          smallint      NOT NULL,
    parent_tenant_id    uuid,
    tenant_type         varchar(24)   NOT NULL DEFAULT 'company'
                        CHECK (tenant_type IN ('company','manager','managed_client','platform')),
    rut_tax_id          varchar(32)   NOT NULL,
    legal_name          varchar(240)  NOT NULL,
    trade_name          varchar(180),
    business_activity   varchar(300),
    status              varchar(24)   NOT NULL DEFAULT 'trial'
                        CHECK (status IN ('trial','active','suspended','closed')),
    settings            jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz
);
COMMENT ON COLUMN tenants.parent_tenant_id IS 'Gestor padre cuando opera como sub-tenant (RF-65).';

CREATE TABLE facilities (
    id                        uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                 uuid          NOT NULL,
    code                      varchar(50)   NOT NULL,
    name                      varchar(180)  NOT NULL,
    facility_type             varchar(40)   NOT NULL,
    address                   varchar(300),
    region_code               varchar(20),
    commune_code              varchar(20),
    latitude                  numeric(9,6),
    longitude                 numeric(9,6),
    environmental_identifiers jsonb         NOT NULL DEFAULT '{}'::jsonb,
    active                    boolean       NOT NULL DEFAULT true,
    created_at                timestamptz   NOT NULL DEFAULT now(),
    created_by                uuid,
    updated_at                timestamptz   NOT NULL DEFAULT now(),
    updated_by                uuid,
    deleted_at                timestamptz,
    CONSTRAINT uq_facilities_tenant_code UNIQUE (tenant_id, code)
);
COMMENT ON COLUMN facilities.environmental_identifiers IS 'IDs sectoriales: RETC, SIDREP, SINADER.';

CREATE TABLE departments (
    id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid          NOT NULL,
    facility_id          uuid,
    parent_department_id uuid,
    code                 varchar(50)   NOT NULL,
    name                 varchar(160)  NOT NULL,
    active               boolean       NOT NULL DEFAULT true,
    created_at           timestamptz   NOT NULL DEFAULT now(),
    created_by           uuid,
    updated_at           timestamptz   NOT NULL DEFAULT now(),
    updated_by           uuid,
    deleted_at           timestamptz,
    CONSTRAINT uq_departments_tenant_code UNIQUE (tenant_id, code)
);

CREATE TABLE users (
    id             uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid          NOT NULL,
    department_id  uuid,
    rut_tax_id     varchar(32),
    email          citext        NOT NULL UNIQUE,
    full_name      varchar(180)  NOT NULL,
    user_type      varchar(32)   NOT NULL
                   CHECK (user_type IN ('platform_admin','tenant_admin','internal','guest','manager')),
    status         varchar(24)   NOT NULL DEFAULT 'invited'
                   CHECK (status IN ('invited','active','blocked','disabled')),
    password_hash  varchar(255),
    preferences    jsonb         NOT NULL DEFAULT '{}'::jsonb,
    last_login_at  timestamptz,
    created_at     timestamptz   NOT NULL DEFAULT now(),
    created_by     uuid,
    updated_at     timestamptz   NOT NULL DEFAULT now(),
    updated_by     uuid,
    deleted_at     timestamptz
);
COMMENT ON COLUMN users.password_hash IS 'Argon2id o bcrypt. Nunca texto plano (RNF-05).';

CREATE TABLE roles (
    id          uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid          NOT NULL,
    code        varchar(60)   NOT NULL,
    name        varchar(120)  NOT NULL,
    is_system   boolean       NOT NULL DEFAULT false,
    description text,
    created_at  timestamptz   NOT NULL DEFAULT now(),
    created_by  uuid,
    updated_at  timestamptz   NOT NULL DEFAULT now(),
    updated_by  uuid,
    deleted_at  timestamptz,
    CONSTRAINT uq_roles_tenant_code UNIQUE (tenant_id, code)
);

CREATE TABLE permissions (
    id          smallserial   PRIMARY KEY,
    code        varchar(100)  NOT NULL UNIQUE,
    module      varchar(50)   NOT NULL,
    description varchar(300)  NOT NULL
);
COMMENT ON TABLE permissions IS 'Catalogo global de permisos atomicos. Ej: legal_matrix.article.evaluate';

CREATE TABLE role_permissions (
    role_id       uuid      NOT NULL,
    permission_id smallint  NOT NULL,
    granted       boolean   NOT NULL DEFAULT true,
    PRIMARY KEY (role_id, permission_id)
);
COMMENT ON COLUMN role_permissions.granted IS 'false = denegacion explicita, gana sobre cualquier concesion.';

CREATE TABLE user_roles (
    user_id       uuid         NOT NULL,
    role_id       uuid         NOT NULL,
    tenant_id     uuid         NOT NULL,
    facility_id   uuid,
    department_id uuid,
    valid_from    timestamptz  NOT NULL DEFAULT now(),
    valid_to      timestamptz,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT ck_user_roles_vigencia CHECK (valid_to IS NULL OR valid_to > valid_from)
);

-- Permisos concedidos o revocados a UN usuario concreto, por encima de sus
-- roles (RF-12). Existe porque el frontend ya modela `User.permisos` como algo
-- distinto de "los permisos de su rol": el analisis de actores lo resume en que
-- un Usuario Interno "no es una fila unica sino un espacio de configuracion".
--
-- Resolucion del permiso efectivo, en este orden:
--   1. Si hay fila en user_permissions para (usuario, permiso) -> manda esa.
--   2. Si no, se une lo que otorguen sus roles vigentes en user_roles.
--   3. En ambos niveles, granted = false gana sobre cualquier concesion.
--
-- El paso 3 es lo que permite quitarle UN permiso a alguien sin sacarlo del rol
-- ni inventar un rol nuevo por excepcion.
CREATE TABLE user_permissions (
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

CREATE TABLE processes (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid          NOT NULL,
    department_id       uuid,
    parent_process_id   uuid,
    code                varchar(50)   NOT NULL,
    name                varchar(180)  NOT NULL,
    process_type        varchar(24)   NOT NULL
                        CHECK (process_type IN ('strategic','operational','support')),
    description         text,
    responsible_user_id uuid,
    inputs              jsonb         NOT NULL DEFAULT '[]'::jsonb,
    outputs             jsonb         NOT NULL DEFAULT '[]'::jsonb,
    display_order       integer       NOT NULL DEFAULT 0,
    active              boolean       NOT NULL DEFAULT true,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz,
    CONSTRAINT uq_processes_tenant_code UNIQUE (tenant_id, code)
);

CREATE TABLE facility_processes (
    facility_id uuid         NOT NULL,
    process_id  uuid         NOT NULL,
    tenant_id   uuid         NOT NULL,
    is_primary  boolean      NOT NULL DEFAULT false,
    scope_notes text,
    active_from date,
    active_to   date,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    created_by  uuid,
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    updated_by  uuid,
    deleted_at  timestamptz,
    PRIMARY KEY (facility_id, process_id)
);

CREATE TABLE contracts (
    id                uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid          NOT NULL,
    manager_tenant_id uuid          NOT NULL,
    client_tenant_id  uuid          NOT NULL,
    contract_number   varchar(100)  NOT NULL,
    title             varchar(240)  NOT NULL,
    status            varchar(24)   NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','pending_signature','active','suspended','expired','terminated')),
    start_date        date          NOT NULL,
    end_date          date,
    scope             jsonb         NOT NULL DEFAULT '{}'::jsonb,
    terms_snapshot    jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at        timestamptz   NOT NULL DEFAULT now(),
    created_by        uuid,
    updated_at        timestamptz   NOT NULL DEFAULT now(),
    updated_by        uuid,
    deleted_at        timestamptz,
    CONSTRAINT uq_contracts_manager_number UNIQUE (manager_tenant_id, contract_number),
    CONSTRAINT ck_contracts_partes CHECK (manager_tenant_id <> client_tenant_id),
    CONSTRAINT ck_contracts_fechas CHECK (end_date IS NULL OR end_date >= start_date)
);
COMMENT ON TABLE contracts IS 'Contrato formal que habilita la sub-tenancy (RF-66).';


-- ── 3.2 Catalogo normativo global ─────────────────────────────────────────

CREATE TABLE legal_sources (
    id               smallserial   PRIMARY KEY,
    country_id       smallint      NOT NULL,
    code             varchar(40)   NOT NULL UNIQUE,
    name             varchar(160)  NOT NULL,
    base_url         varchar(500),
    connector_config jsonb         NOT NULL DEFAULT '{}'::jsonb,
    active           boolean       NOT NULL DEFAULT true
);

CREATE TABLE legal_norms (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    country_id          smallint      NOT NULL,
    source_id           smallint      NOT NULL,
    external_norm_id    varchar(80),
    norm_type           varchar(80)   NOT NULL,
    norm_number         varchar(60),
    title               text          NOT NULL,
    issuing_body        varchar(240),
    publication_date    date,
    promulgation_date   date,
    effective_from      date,
    repeal_date         date,
    status              varchar(32)   NOT NULL DEFAULT 'desconocida'
                        CHECK (status IN ('draft','vigente','parcialmente_vigente','derogada','desconocida')),
    official_url        varchar(700),
    subjects            text[]        NOT NULL DEFAULT '{}'::text[],
    source_payload      jsonb         NOT NULL DEFAULT '{}'::jsonb,
    last_source_sync_at timestamptz,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz,
    CONSTRAINT uq_legal_norms_source_external UNIQUE (source_id, external_norm_id)
);
COMMENT ON TABLE legal_norms IS
  'Catalogo global: sin tenant_id a proposito. La norma es la misma para todos '
  'los tenants; lo que se registra por empresa es la aplicabilidad y el cumplimiento.';

CREATE TABLE legal_norm_versions (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    norm_id             uuid          NOT NULL,
    external_version_id varchar(100),
    version_label       varchar(160),
    valid_from          date          NOT NULL,
    valid_to            date,
    is_current          boolean       NOT NULL DEFAULT false,
    content_hash        char(64)      NOT NULL,
    full_text           text,
    xml_payload         jsonb         NOT NULL DEFAULT '{}'::jsonb,
    change_summary      text,
    source_retrieved_at timestamptz   NOT NULL DEFAULT now(),
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz,
    CONSTRAINT uq_norm_versions_hash UNIQUE (norm_id, content_hash),
    CONSTRAINT ck_norm_versions_vigencia CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE legal_articles (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    norm_version_id     uuid          NOT NULL,
    parent_article_id   uuid,
    external_article_id varchar(120),
    article_type        varchar(32)   NOT NULL DEFAULT 'article'
                        CHECK (article_type IN ('article','transitory','paragraph','subsection','numeral','letter')),
    article_number      varchar(40)   NOT NULL,
    heading             text,
    content             text          NOT NULL,
    display_order       integer       NOT NULL,
    effective_from      date,
    effective_to        date,
    structured_content  jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz,
    CONSTRAINT uq_legal_articles_external UNIQUE (norm_version_id, external_article_id)
);
COMMENT ON TABLE legal_articles IS
  'El articulo cuelga de una VERSION, no de la norma: el texto legal cambia y '
  'una auditoria pregunta bajo que texto se evaluo en una fecha dada.';

CREATE TABLE legal_relations (
    id                bigserial    PRIMARY KEY,
    source_norm_id    uuid         NOT NULL,
    source_article_id uuid,
    target_norm_id    uuid         NOT NULL,
    target_article_id uuid,
    relation_type     varchar(40)  NOT NULL
                      CHECK (relation_type IN ('modifica','deroga','reglamenta','concordancia','referencia','refundido')),
    effective_date    date,
    metadata          jsonb        NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE sectors (
    id          smallserial   PRIMARY KEY,
    country_id  smallint,
    parent_id   smallint,
    code        varchar(40)   NOT NULL UNIQUE,
    name        varchar(180)  NOT NULL,
    description text,
    metadata    jsonb         NOT NULL DEFAULT '{}'::jsonb
);
COMMENT ON COLUMN sectors.code IS 'Codigo estable; puede mapear CIIU u otra clasificacion.';

CREATE TABLE norm_sectors (
    norm_id             uuid          NOT NULL,
    sector_id           smallint      NOT NULL,
    article_id          uuid,
    applicability_level varchar(24)   NOT NULL DEFAULT 'directa'
                        CHECK (applicability_level IN ('directa','indirecta','referencial')),
    rationale           text,
    source              varchar(20)   NOT NULL DEFAULT 'analyst'
                        CHECK (source IN ('automatic','analyst','client')),
    confidence          numeric(5,4)
                        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    PRIMARY KEY (norm_id, sector_id)
);

CREATE TABLE norm_sync_runs (
    id                 bigserial    PRIMARY KEY,
    source_id          smallint     NOT NULL,
    started_at         timestamptz  NOT NULL DEFAULT now(),
    finished_at        timestamptz,
    status             varchar(20)  NOT NULL DEFAULT 'running'
                       CHECK (status IN ('running','success','partial','failed')),
    request_parameters jsonb        NOT NULL DEFAULT '{}'::jsonb,
    response_metadata  jsonb        NOT NULL DEFAULT '{}'::jsonb,
    norms_created      integer      NOT NULL DEFAULT 0,
    norms_updated      integer      NOT NULL DEFAULT 0,
    versions_created   integer      NOT NULL DEFAULT 0,
    error_detail       text
);

CREATE TABLE facility_norm_assignments (
    id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid          NOT NULL,
    facility_id          uuid          NOT NULL,
    norm_id              uuid          NOT NULL,
    assigned_version_id  uuid,
    assignment_status    varchar(24)   NOT NULL DEFAULT 'pending_review'
                         CHECK (assignment_status IN ('suggested','assigned','rejected','pending_review')),
    applicability_reason text,
    assigned_by          uuid,
    assigned_at          timestamptz   NOT NULL DEFAULT now(),
    source               varchar(24)   NOT NULL DEFAULT 'manual'
                         CHECK (source IN ('manual','rule','import','ai_assisted')),
    metadata             jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at           timestamptz   NOT NULL DEFAULT now(),
    created_by           uuid,
    updated_at           timestamptz   NOT NULL DEFAULT now(),
    updated_by           uuid,
    deleted_at           timestamptz
);


-- ── 3.3 Matriz legal y evaluacion de cumplimiento ─────────────────────────

CREATE TABLE tenant_legal_matrices (
    id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid          NOT NULL,
    name             varchar(180)  NOT NULL,
    period_year      smallint      NOT NULL,
    facility_id      uuid,
    status           varchar(24)   NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft','in_review','approved','archived')),
    version_no       integer       NOT NULL DEFAULT 1,
    approved_at      timestamptz,
    approved_by      uuid,
    scope_definition jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz   NOT NULL DEFAULT now(),
    created_by       uuid,
    updated_at       timestamptz   NOT NULL DEFAULT now(),
    updated_by       uuid,
    deleted_at       timestamptz,
    CONSTRAINT ck_matrices_aprobacion
      CHECK ((status = 'approved') = (approved_at IS NOT NULL))
);
COMMENT ON CONSTRAINT ck_matrices_aprobacion ON tenant_legal_matrices IS
  'Una matriz aprobada tiene fecha de aprobacion, y solo una aprobada la tiene.';

CREATE TABLE matrix_norms (
    id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid          NOT NULL,
    matrix_id            uuid          NOT NULL,
    norm_id              uuid          NOT NULL,
    selected_version_id  uuid          NOT NULL,
    sector_id            smallint,
    applicability        varchar(28)   NOT NULL DEFAULT 'pending_analysis'
                         CHECK (applicability IN ('applicable','not_applicable','pending_analysis')),
    applicability_reason text,
    owner_user_id        uuid,
    review_frequency     varchar(24)   NOT NULL DEFAULT 'annual'
                         CHECK (review_frequency IN ('annual','semiannual','quarterly','event_based')),
    next_review_date     date,
    snapshot             jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at           timestamptz   NOT NULL DEFAULT now(),
    created_by           uuid,
    updated_at           timestamptz   NOT NULL DEFAULT now(),
    updated_by           uuid,
    deleted_at           timestamptz,
    CONSTRAINT uq_matrix_norms UNIQUE (matrix_id, norm_id)
);
COMMENT ON COLUMN matrix_norms.selected_version_id IS
  'Version congelada usada para evaluar. Sin esto no se puede reconstruir una evaluacion pasada.';

CREATE TABLE article_compliance (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid          NOT NULL,
    matrix_norm_id      uuid          NOT NULL,
    article_id          uuid          NOT NULL,
    facility_id         uuid,
    department_id       uuid,
    compliance_status   varchar(24)   NOT NULL DEFAULT 'pending'
                        CHECK (compliance_status IN ('compliant','non_compliant','partial','not_applicable','pending')),
    compliance_method   text,
    assessment_reason   text,
    risk_level          varchar(16)
                        CHECK (risk_level IS NULL OR risk_level IN ('low','medium','high','critical')),
    responsible_user_id uuid,
    assessed_at         timestamptz,
    assessed_by         uuid,
    approved_at         timestamptz,
    approved_by         uuid,
    attributes          jsonb         NOT NULL DEFAULT '{}'::jsonb,
    row_version         integer       NOT NULL DEFAULT 1,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz,
    -- NULLS NOT DISTINCT es imprescindible: facility_id es nullable (NULL =
    -- evaluacion a nivel empresa). Con el comportamiento por defecto los NULL
    -- no colisionan entre si, asi que se podria evaluar el mismo articulo a
    -- nivel empresa tantas veces como se quisiera.
    CONSTRAINT uq_article_compliance
      UNIQUE NULLS NOT DISTINCT (matrix_norm_id, article_id, facility_id)
);
COMMENT ON COLUMN article_compliance.row_version IS 'Control optimista de concurrencia.';


-- ── 3.4 Obligaciones, tareas y declaraciones ──────────────────────────────

CREATE TABLE obligation_templates (
    id                uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    country_id        smallint      NOT NULL,
    code              varchar(60)   NOT NULL UNIQUE,
    name              varchar(200)  NOT NULL,
    authority         varchar(200),
    frequency_rule    varchar(500),
    default_lead_days smallint      NOT NULL DEFAULT 30,
    template_config   jsonb         NOT NULL DEFAULT '{}'::jsonb,
    active            boolean       NOT NULL DEFAULT true,
    created_at        timestamptz   NOT NULL DEFAULT now(),
    created_by        uuid,
    updated_at        timestamptz   NOT NULL DEFAULT now(),
    updated_by        uuid,
    deleted_at        timestamptz
);
COMMENT ON COLUMN obligation_templates.frequency_rule IS 'Compatible con RRULE.';

CREATE TABLE obligations (
    id                    uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid          NOT NULL,
    template_id           uuid,
    matrix_norm_id        uuid,
    article_compliance_id uuid,
    facility_id           uuid,
    code                  varchar(60)   NOT NULL,
    title                 varchar(240)  NOT NULL,
    period_start          date,
    period_end            date,
    due_at                timestamptz,
    status                varchar(24)   NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','open','in_progress','submitted','accepted','rejected','overdue','closed')),
    owner_user_id         uuid,
    submitted_at          timestamptz,
    external_receipt      varchar(160),
    data                  jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at            timestamptz   NOT NULL DEFAULT now(),
    created_by            uuid,
    updated_at            timestamptz   NOT NULL DEFAULT now(),
    updated_by            uuid,
    deleted_at            timestamptz,
    CONSTRAINT uq_obligations_tenant_code UNIQUE (tenant_id, code),
    CONSTRAINT ck_obligations_periodo CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start)
);

CREATE TABLE tasks (
    id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid          NOT NULL,
    obligation_id    uuid,
    parent_task_id   uuid,
    task_type        varchar(32)   NOT NULL DEFAULT 'task'
                     CHECK (task_type IN ('task','milestone','approval','evidence_request','support_ticket')),
    title            varchar(240)  NOT NULL,
    description      text,
    status           varchar(24)   NOT NULL DEFAULT 'todo'
                     CHECK (status IN ('todo','in_progress','blocked','review','done','cancelled')),
    priority         varchar(16)   NOT NULL DEFAULT 'medium'
                     CHECK (priority IN ('low','medium','high','critical')),
    start_at         timestamptz,
    due_at           timestamptz,
    completed_at     timestamptz,
    assignee_user_id uuid,
    department_id    uuid,
    progress_percent numeric(5,2)  NOT NULL DEFAULT 0
                     CHECK (progress_percent >= 0 AND progress_percent <= 100),
    metadata         jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz   NOT NULL DEFAULT now(),
    created_by       uuid,
    updated_at       timestamptz   NOT NULL DEFAULT now(),
    updated_by       uuid,
    deleted_at       timestamptz
);
COMMENT ON TABLE tasks IS 'Ticket unico de Calendario, Gantt y Obligaciones (RF-28). No se duplica.';

CREATE TABLE declaration_templates (
    id                 uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    country_id         smallint      NOT NULL,
    system_code        varchar(40)   NOT NULL,
    name               varchar(220)  NOT NULL,
    version            varchar(40)   NOT NULL,
    valid_from         date,
    valid_to           date,
    schema_definition  jsonb         NOT NULL DEFAULT '{}'::jsonb,
    workbook_structure jsonb         NOT NULL DEFAULT '{}'::jsonb,
    source_document_id uuid,
    active             boolean       NOT NULL DEFAULT true,
    created_at         timestamptz   NOT NULL DEFAULT now(),
    created_by         uuid,
    updated_at         timestamptz   NOT NULL DEFAULT now(),
    updated_by         uuid,
    deleted_at         timestamptz,
    CONSTRAINT uq_declaration_templates UNIQUE (system_code, version)
);

CREATE TABLE declaration_submissions (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid          NOT NULL,
    obligation_id       uuid          NOT NULL,
    template_id         uuid,
    facility_id         uuid,
    period_label        varchar(80),
    version_no          integer       NOT NULL DEFAULT 1,
    status              varchar(24)   NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','validation_error','ready','submitted','accepted','rejected','rectified')),
    prepared_by         uuid,
    reviewed_by         uuid,
    submitted_by        uuid,
    submitted_at        timestamptz,
    external_folio      varchar(160),
    submission_data     jsonb         NOT NULL DEFAULT '{}'::jsonb,
    validation_result   jsonb         NOT NULL DEFAULT '{}'::jsonb,
    receipt_document_id uuid,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz
);


-- ── 3.5 Documentos y evidencias ───────────────────────────────────────────

CREATE TABLE documents (
    id                 uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid          NOT NULL,
    document_type      varchar(40)   NOT NULL
                       CHECK (document_type IN ('evidence','declaration_template','receipt','contract','audit','email_attachment','other')),
    current_version_id uuid,
    title              varchar(240)  NOT NULL,
    classification     varchar(20)   NOT NULL DEFAULT 'internal'
                       CHECK (classification IN ('public','internal','confidential','restricted')),
    status             varchar(20)   NOT NULL DEFAULT 'active'
                       CHECK (status IN ('draft','active','archived','deleted')),
    tags               text[]        NOT NULL DEFAULT '{}'::text[],
    metadata           jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at         timestamptz   NOT NULL DEFAULT now(),
    created_by         uuid,
    updated_at         timestamptz   NOT NULL DEFAULT now(),
    updated_by         uuid,
    deleted_at         timestamptz
);
COMMENT ON TABLE documents IS 'Solo metadatos. El binario vive en object storage, Drive u OneDrive.';

CREATE TABLE document_versions (
    id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid          NOT NULL,
    document_id      uuid          NOT NULL,
    version_no       integer       NOT NULL,
    storage_provider varchar(32)   NOT NULL
                     CHECK (storage_provider IN ('s3','backblaze','google_drive','onedrive')),
    storage_key      varchar(1000) NOT NULL,
    file_name        varchar(255)  NOT NULL,
    mime_type        varchar(150)  NOT NULL,
    size_bytes       bigint        NOT NULL CHECK (size_bytes >= 0),
    checksum_sha256  char(64),
    source           varchar(24)   NOT NULL DEFAULT 'upload'
                     CHECK (source IN ('upload','generated','imported','email')),
    version_metadata jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz   NOT NULL DEFAULT now(),
    created_by       uuid,
    CONSTRAINT uq_document_versions UNIQUE (document_id, version_no)
);
COMMENT ON COLUMN document_versions.storage_key IS 'Clave o ID externo. Nunca una URL firmada.';

CREATE TABLE entity_documents (
    id          bigserial    PRIMARY KEY,
    tenant_id   uuid         NOT NULL,
    document_id uuid         NOT NULL,
    entity_type varchar(40)  NOT NULL
                CHECK (entity_type IN ('article_compliance','obligation','task','action_plan','audit',
                                       'nonconformity','contract','environmental_aspect','risk_opportunity',
                                       'regulated_equipment','declaration_submission')),
    entity_id   uuid         NOT NULL,
    purpose     varchar(32)  NOT NULL
                CHECK (purpose IN ('evidence','support','template','result','approval')),
    is_required boolean      NOT NULL DEFAULT false,
    valid_from  date,
    valid_to    date,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    created_by  uuid,
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    updated_by  uuid,
    deleted_at  timestamptz
);
COMMENT ON TABLE entity_documents IS
  'Vinculo polimorfico controlado. Evita 11 tablas de union casi identicas; a cambio '
  'la integridad de entity_id la valida el servicio, no la base.';


-- ── 3.6 Auditorias y mejora continua ──────────────────────────────────────

CREATE TABLE audits (
    id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid          NOT NULL,
    facility_id          uuid,
    code                 varchar(60)   NOT NULL,
    title                varchar(240)  NOT NULL,
    audit_type           varchar(24)   NOT NULL
                         CHECK (audit_type IN ('internal','external','regulatory','supplier')),
    scope                text          NOT NULL,
    lead_auditor_user_id uuid,
    planned_start        timestamptz,
    planned_end          timestamptz,
    actual_start         timestamptz,
    actual_end           timestamptz,
    status               varchar(20)   NOT NULL DEFAULT 'planned'
                         CHECK (status IN ('planned','active','reporting','closed','cancelled')),
    criteria             jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at           timestamptz   NOT NULL DEFAULT now(),
    created_by           uuid,
    updated_at           timestamptz   NOT NULL DEFAULT now(),
    updated_by           uuid,
    deleted_at           timestamptz,
    CONSTRAINT uq_audits_tenant_code UNIQUE (tenant_id, code)
);

CREATE TABLE audit_items (
    id                    uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid          NOT NULL,
    audit_id              uuid          NOT NULL,
    article_compliance_id uuid,
    sequence              integer       NOT NULL,
    question              text          NOT NULL,
    result                varchar(24)   NOT NULL DEFAULT 'pending'
                          CHECK (result IN ('conform','nonconform','observation','not_applicable','pending')),
    notes                 text,
    auditor_user_id       uuid,
    assessed_at           timestamptz,
    created_at            timestamptz   NOT NULL DEFAULT now(),
    created_by            uuid,
    updated_at            timestamptz   NOT NULL DEFAULT now(),
    updated_by            uuid,
    deleted_at            timestamptz,
    CONSTRAINT uq_audit_items_seq UNIQUE (audit_id, sequence)
);

CREATE TABLE audit_participants (
    audit_id          uuid          NOT NULL,
    user_id           uuid          NOT NULL,
    tenant_id         uuid          NOT NULL,
    external_name     varchar(180),
    external_email    citext,
    participant_role  varchar(32)   NOT NULL
                      CHECK (participant_role IN ('lead_auditor','auditor','auditee','observer','approver')),
    attendance_status varchar(20)   NOT NULL DEFAULT 'invited'
                      CHECK (attendance_status IN ('invited','confirmed','declined','attended')),
    notes             text,
    created_at        timestamptz   NOT NULL DEFAULT now(),
    created_by        uuid,
    updated_at        timestamptz   NOT NULL DEFAULT now(),
    updated_by        uuid,
    deleted_at        timestamptz,
    PRIMARY KEY (audit_id, user_id)
);

CREATE TABLE nonconformities (
    id                    uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid          NOT NULL,
    facility_id           uuid,
    audit_item_id         uuid,
    article_compliance_id uuid,
    code                  varchar(60)   NOT NULL,
    title                 varchar(240)  NOT NULL,
    description           text          NOT NULL,
    severity              varchar(16)   NOT NULL
                          CHECK (severity IN ('minor','major','critical')),
    status                varchar(24)   NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','analysis','action_plan','verification','closed','rejected')),
    -- Campos que el frontend ya usa y el modelo v2 no tenia.
    record_type           varchar(24)
                          CHECK (record_type IS NULL OR record_type IN
                                ('salida_no_conforme','no_conformidad','riesgo','oportunidad','reclamo')),
    detection_origin      varchar(24)
                          CHECK (detection_origin IS NULL OR detection_origin IN
                                ('interna','externa','analisis_foda','auditoria_interna','auditoria_externa')),
    root_cause_answers    jsonb         NOT NULL DEFAULT '[]'::jsonb,
    improvement_stages    jsonb         NOT NULL DEFAULT '{}'::jsonb,
    detected_at           timestamptz   NOT NULL DEFAULT now(),
    detected_by           uuid,
    owner_user_id         uuid,
    due_date              date,
    closed_at             timestamptz,
    closure_notes         text,
    created_at            timestamptz   NOT NULL DEFAULT now(),
    created_by            uuid,
    updated_at            timestamptz   NOT NULL DEFAULT now(),
    updated_by            uuid,
    deleted_at            timestamptz,
    CONSTRAINT uq_nonconformities_tenant_code UNIQUE (tenant_id, code),
    CONSTRAINT ck_nonconformities_cierre
      CHECK ((status = 'closed') = (closed_at IS NOT NULL))
);
COMMENT ON COLUMN nonconformities.record_type IS
  'Tipo de registro de mejora (borrador v1.8 RF-96). El frontend ya lo usa para el flujo corto.';
COMMENT ON COLUMN nonconformities.improvement_stages IS
  'Etapas del tratamiento (RF-97). JSONB de forma provisoria: el modelado relacional '
  'depende de la decision abierta sobre donde viven las etapas.';
COMMENT ON CONSTRAINT ck_nonconformities_cierre ON nonconformities IS
  'RF-49: un hallazgo cerrado tiene fecha de cierre, y solo un cerrado la tiene.';

CREATE TABLE action_plans (
    id                    uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid          NOT NULL,
    article_compliance_id uuid,
    nonconformity_id      uuid,
    title                 varchar(240)  NOT NULL,
    root_cause            text,
    objective             text          NOT NULL,
    status                varchar(24)   NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','approved','in_progress','completed','verified','cancelled')),
    priority              varchar(16)   NOT NULL DEFAULT 'medium'
                          CHECK (priority IN ('low','medium','high','critical')),
    owner_user_id         uuid,
    target_date           date,
    verified_at           timestamptz,
    verified_by           uuid,
    success_criteria      jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at            timestamptz   NOT NULL DEFAULT now(),
    created_by            uuid,
    updated_at            timestamptz   NOT NULL DEFAULT now(),
    updated_by            uuid,
    deleted_at            timestamptz,
    CONSTRAINT ck_action_plans_origen
      CHECK (article_compliance_id IS NOT NULL OR nonconformity_id IS NOT NULL)
);
COMMENT ON CONSTRAINT ck_action_plans_origen ON action_plans IS
  'Un plan nace de un incumplimiento legal o de un hallazgo. Sin origen no es trazable.';

CREATE TABLE entity_status_history (
    id          bigserial    PRIMARY KEY,
    tenant_id   uuid         NOT NULL,
    entity_type varchar(40)  NOT NULL
                CHECK (entity_type IN ('obligation','declaration_submission','audit','nonconformity','action_plan','task')),
    entity_id   uuid         NOT NULL,
    from_status varchar(40),
    to_status   varchar(40)  NOT NULL,
    changed_at  timestamptz  NOT NULL DEFAULT now(),
    changed_by  uuid,
    reason      text,
    metadata    jsonb        NOT NULL DEFAULT '{}'::jsonb
);
COMMENT ON TABLE entity_status_history IS
  'Historial funcional que alimenta el timeline de la UI. No reemplaza a audit_log.';


-- ── 3.7 Notificaciones, soporte, chatbot y sistema ────────────────────────

CREATE TABLE notification_templates (
    id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid          NOT NULL,
    code             varchar(80)   NOT NULL,
    name             varchar(180)  NOT NULL,
    event_type       varchar(60)   NOT NULL,
    channel          varchar(20)   NOT NULL CHECK (channel IN ('email','in_app')),
    locale           varchar(12)   NOT NULL DEFAULT 'es-CL',
    subject_template varchar(400),
    body_template    text          NOT NULL,
    variables_schema jsonb         NOT NULL DEFAULT '{}'::jsonb,
    version_no       integer       NOT NULL DEFAULT 1,
    active           boolean       NOT NULL DEFAULT true,
    created_at       timestamptz   NOT NULL DEFAULT now(),
    created_by       uuid,
    updated_at       timestamptz   NOT NULL DEFAULT now(),
    updated_by       uuid,
    deleted_at       timestamptz,
    CONSTRAINT uq_notification_templates UNIQUE (tenant_id, code)
);

CREATE TABLE notification_rules (
    id             uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid          NOT NULL,
    event_type     varchar(60)   NOT NULL,
    channel        varchar(20)   NOT NULL CHECK (channel IN ('email','in_app')),
    lead_minutes   integer       NOT NULL DEFAULT 0,
    recipient_rule jsonb         NOT NULL DEFAULT '{}'::jsonb,
    template_code  varchar(80)   NOT NULL,
    active         boolean       NOT NULL DEFAULT true,
    created_at     timestamptz   NOT NULL DEFAULT now(),
    created_by     uuid,
    updated_at     timestamptz   NOT NULL DEFAULT now(),
    updated_by     uuid,
    deleted_at     timestamptz
);
COMMENT ON COLUMN notification_rules.lead_minutes IS 'Anticipacion. Negativo = aviso posterior al vencimiento.';

CREATE TABLE notifications (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid          NOT NULL,
    rule_id             uuid,
    recipient_user_id   uuid,
    channel             varchar(20)   NOT NULL CHECK (channel IN ('email','in_app')),
    subject             varchar(300),
    body                text          NOT NULL,
    status              varchar(20)   NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','sent','delivered','failed','read','cancelled')),
    scheduled_at        timestamptz   NOT NULL DEFAULT now(),
    sent_at             timestamptz,
    read_at             timestamptz,
    provider_message_id varchar(200),
    context             jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz
);
COMMENT ON COLUMN notifications.provider_message_id IS 'ID de Resend (decision cerrada #18 de la v1.7).';

CREATE TABLE support_tickets (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid          NOT NULL,
    ticket_number       varchar(40)   NOT NULL UNIQUE,
    created_by_user_id  uuid,
    guest_name          varchar(180),
    guest_email         citext,
    category            varchar(32)   NOT NULL
                        CHECK (category IN ('technical','access','data','legal','billing','other')),
    subject             varchar(240)  NOT NULL,
    description         text          NOT NULL,
    priority            varchar(16)   NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('low','medium','high','critical')),
    status              varchar(24)   NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','assigned','waiting_user','in_progress','resolved','closed')),
    assigned_to         uuid,
    related_entity_type varchar(40),
    related_entity_id   uuid,
    resolved_at         timestamptz,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz,
    CONSTRAINT ck_support_tickets_autor
      CHECK (created_by_user_id IS NOT NULL OR guest_email IS NOT NULL)
);
COMMENT ON CONSTRAINT ck_support_tickets_autor ON support_tickets IS
  'Un ticket lo abre un usuario registrado o un invitado con correo (RF-02).';

CREATE TABLE support_ticket_messages (
    id                 bigserial    PRIMARY KEY,
    tenant_id          uuid         NOT NULL,
    ticket_id          uuid         NOT NULL,
    author_user_id     uuid,
    author_guest_email citext,
    message_type       varchar(24)  NOT NULL DEFAULT 'comment'
                       CHECK (message_type IN ('comment','internal_note','status_change','attachment')),
    body               text         NOT NULL,
    is_internal        boolean      NOT NULL DEFAULT false,
    created_at         timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE chatbot_conversations (
    id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid          NOT NULL,
    user_id          uuid          NOT NULL,
    title            varchar(240),
    scope            varchar(24)   NOT NULL DEFAULT 'tenant'
                     CHECK (scope IN ('tenant','facility','legal_matrix','platform')),
    facility_id      uuid,
    status           varchar(20)   NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','archived','deleted')),
    context_snapshot jsonb         NOT NULL DEFAULT '{}'::jsonb,
    last_message_at  timestamptz,
    created_at       timestamptz   NOT NULL DEFAULT now(),
    created_by       uuid,
    updated_at       timestamptz   NOT NULL DEFAULT now(),
    updated_by       uuid,
    deleted_at       timestamptz
);

CREATE TABLE chatbot_messages (
    id              bigserial    PRIMARY KEY,
    tenant_id       uuid         NOT NULL,
    conversation_id uuid         NOT NULL,
    role            varchar(16)  NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content         text         NOT NULL,
    cited_norm_ids  uuid[]       NOT NULL DEFAULT '{}'::uuid[],
    citations       jsonb        NOT NULL DEFAULT '[]'::jsonb,
    model_name      varchar(100),
    token_usage     jsonb        NOT NULL DEFAULT '{}'::jsonb,
    feedback        jsonb        NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON COLUMN chatbot_messages.cited_norm_ids IS
  'RF-63: el agente debe citar fuente normativa. Esto lo hace verificable.';

CREATE TABLE integration_accounts (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid          NOT NULL,
    provider            varchar(40)   NOT NULL
                        CHECK (provider IN ('google_drive','onedrive','microsoft_oauth','google_oauth','resend')),
    external_account_id varchar(255),
    display_name        varchar(180),
    status              varchar(20)   NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','expired','revoked','error')),
    scopes              text[]        NOT NULL DEFAULT '{}'::text[],
    secret_reference    varchar(500),
    metadata            jsonb         NOT NULL DEFAULT '{}'::jsonb,
    last_sync_at        timestamptz,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz
);
COMMENT ON COLUMN integration_accounts.secret_reference IS
  'Referencia al secret manager. NUNCA el token en claro.';

CREATE TABLE audit_log (
    id            bigserial    PRIMARY KEY,
    tenant_id     uuid         NOT NULL,
    occurred_at   timestamptz  NOT NULL DEFAULT now(),
    actor_user_id uuid,
    action        varchar(60)  NOT NULL
                  CHECK (action IN ('create','update','delete','approve','login','download','sync')),
    entity_type   varchar(60)  NOT NULL,
    entity_id     uuid,
    request_id    uuid,
    ip_address    inet,
    reason        text,
    before_data   jsonb,
    after_data    jsonb,
    metadata      jsonb        NOT NULL DEFAULT '{}'::jsonb
);
COMMENT ON TABLE audit_log IS
  'Registro inmutable (RNF-08, RNF-25). La inmutabilidad se refuerza en la seccion 7 '
  'revocando UPDATE y DELETE al rol de aplicacion.';


-- ── 3.8 ISO 14001 — entidades que faltaban en el modelo v2 ────────────────

CREATE TABLE environmental_aspects (
    id                    uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid          NOT NULL,
    facility_id           uuid          NOT NULL,
    process_id            uuid,
    article_compliance_id uuid,
    activity              varchar(240)  NOT NULL,
    aspect                varchar(240)  NOT NULL,
    impact_type           varchar(120)  NOT NULL,
    operating_condition   varchar(20)   NOT NULL DEFAULT 'normal'
                          CHECK (operating_condition IN ('normal','anormal','emergencia')),
    severity_score        smallint      CHECK (severity_score IS NULL OR severity_score BETWEEN 1 AND 10),
    frequency_score       smallint      CHECK (frequency_score IS NULL OR frequency_score BETWEEN 1 AND 10),
    legal_score           smallint      CHECK (legal_score IS NULL OR legal_score BETWEEN 1 AND 10),
    total_score           integer,
    significance          varchar(20)   NOT NULL DEFAULT 'pending'
                          CHECK (significance IN ('compliant','partial','non_compliant','pending')),
    responsible_user_id   uuid,
    controls              jsonb         NOT NULL DEFAULT '[]'::jsonb,
    created_at            timestamptz   NOT NULL DEFAULT now(),
    created_by            uuid,
    updated_at            timestamptz   NOT NULL DEFAULT now(),
    updated_by            uuid,
    deleted_at            timestamptz
);
COMMENT ON TABLE environmental_aspects IS
  'ISO 14001 §6.1.2. No estaba en el modelo v2; la pantalla ya existe en el frontend.';

CREATE TABLE risks_opportunities (
    id                      uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               uuid          NOT NULL,
    facility_id             uuid,
    environmental_aspect_id uuid,
    action_plan_id          uuid,
    code                    varchar(40)   NOT NULL,
    entry_type              varchar(16)   NOT NULL
                            CHECK (entry_type IN ('risk','opportunity')),
    description             text          NOT NULL,
    origin                  varchar(32)   NOT NULL
                            CHECK (origin IN ('environmental_aspect','context','climate_change','compliance','other')),
    risk_level              varchar(16)   NOT NULL DEFAULT 'medium'
                            CHECK (risk_level IN ('low','medium','high','critical')),
    treatment               varchar(20)
                            CHECK (treatment IS NULL OR treatment IN ('mitigate','avoid','transfer','accept','exploit')),
    status                  varchar(20)   NOT NULL DEFAULT 'identified'
                            CHECK (status IN ('identified','in_treatment','controlled','closed')),
    owner_user_id           uuid,
    review_date             date,
    created_at              timestamptz   NOT NULL DEFAULT now(),
    created_by              uuid,
    updated_at              timestamptz   NOT NULL DEFAULT now(),
    updated_by              uuid,
    deleted_at              timestamptz,
    CONSTRAINT uq_risks_opportunities_code UNIQUE (tenant_id, code),
    CONSTRAINT ck_risks_origen_aspecto
      CHECK (origin <> 'environmental_aspect' OR environmental_aspect_id IS NOT NULL)
);
COMMENT ON CONSTRAINT ck_risks_origen_aspecto ON risks_opportunities IS
  'Si el origen declarado es un aspecto ambiental, el aspecto tiene que estar referenciado. '
  'ISO 14001 deriva §6.1.4 de §6.1.2 y esa trazabilidad es lo que pide un auditor.';

CREATE TABLE regulated_equipment (
    id                     uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id              uuid          NOT NULL,
    facility_id            uuid          NOT NULL,
    name                   varchar(180)  NOT NULL,
    equipment_type         varchar(80)   NOT NULL,
    brand                  varchar(120),
    model                  varchar(120),
    registration_authority varchar(40)
                           CHECK (registration_authority IS NULL OR
                                  registration_authority IN ('SEC','SISS','SEREMI_SALUD','DGA','SMA','OTRO')),
    registration_number    varchar(80),
    registration_expires_at date,
    status                 varchar(20)   NOT NULL DEFAULT 'operational'
                           CHECK (status IN ('operational','stopped','decommissioned')),
    technical_specs        jsonb         NOT NULL DEFAULT '{}'::jsonb,
    created_at             timestamptz   NOT NULL DEFAULT now(),
    created_by             uuid,
    updated_at             timestamptz   NOT NULL DEFAULT now(),
    updated_by             uuid,
    deleted_at             timestamptz
);

CREATE TABLE equipment_operators (
    equipment_id             uuid         NOT NULL,
    user_id                  uuid         NOT NULL,
    tenant_id                uuid         NOT NULL,
    certification_class      varchar(40),
    certification_number     varchar(80),
    certification_expires_at date,
    is_primary               boolean      NOT NULL DEFAULT false,
    created_at               timestamptz  NOT NULL DEFAULT now(),
    created_by               uuid,
    updated_at               timestamptz  NOT NULL DEFAULT now(),
    updated_by               uuid,
    deleted_at               timestamptz,
    PRIMARY KEY (equipment_id, user_id)
);
COMMENT ON TABLE equipment_operators IS
  'Un equipo sin operador con certificacion vigente es un incumplimiento; la pantalla lo marca.';


-- ───────────────────────────────────────────────────────────────────────────
--  4. CLAVES FORANEAS
-- ───────────────────────────────────────────────────────────────────────────

-- Organizacion y RBAC
ALTER TABLE tenants            ADD CONSTRAINT fk_tenants_country       FOREIGN KEY (country_id)        REFERENCES countries(id);
ALTER TABLE tenants            ADD CONSTRAINT fk_tenants_parent        FOREIGN KEY (parent_tenant_id)  REFERENCES tenants(id);
ALTER TABLE tenants            ADD CONSTRAINT fk_tenants_created_by    FOREIGN KEY (created_by)        REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE tenants            ADD CONSTRAINT fk_tenants_updated_by    FOREIGN KEY (updated_by)        REFERENCES users(id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE facilities         ADD CONSTRAINT fk_facilities_tenant     FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE departments        ADD CONSTRAINT fk_departments_tenant    FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE departments        ADD CONSTRAINT fk_departments_facility  FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE departments        ADD CONSTRAINT fk_departments_parent    FOREIGN KEY (parent_department_id) REFERENCES departments(id);

ALTER TABLE users              ADD CONSTRAINT fk_users_tenant          FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE users              ADD CONSTRAINT fk_users_department      FOREIGN KEY (department_id)     REFERENCES departments(id);

ALTER TABLE roles              ADD CONSTRAINT fk_roles_tenant          FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE role_permissions   ADD CONSTRAINT fk_roleperm_role         FOREIGN KEY (role_id)           REFERENCES roles(id) ON DELETE CASCADE;
ALTER TABLE role_permissions   ADD CONSTRAINT fk_roleperm_permission   FOREIGN KEY (permission_id)     REFERENCES permissions(id);

ALTER TABLE user_roles         ADD CONSTRAINT fk_userroles_user        FOREIGN KEY (user_id)           REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_roles         ADD CONSTRAINT fk_userroles_role        FOREIGN KEY (role_id)           REFERENCES roles(id) ON DELETE CASCADE;
ALTER TABLE user_roles         ADD CONSTRAINT fk_userroles_tenant      FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE user_roles         ADD CONSTRAINT fk_userroles_facility    FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE user_roles         ADD CONSTRAINT fk_userroles_department  FOREIGN KEY (department_id)     REFERENCES departments(id);

ALTER TABLE user_permissions   ADD CONSTRAINT fk_userperm_user         FOREIGN KEY (user_id)           REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_permissions   ADD CONSTRAINT fk_userperm_permission   FOREIGN KEY (permission_id)     REFERENCES permissions(id);
ALTER TABLE user_permissions   ADD CONSTRAINT fk_userperm_tenant       FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE user_permissions   ADD CONSTRAINT fk_userperm_granted_by   FOREIGN KEY (granted_by)        REFERENCES users(id);

ALTER TABLE processes          ADD CONSTRAINT fk_processes_tenant      FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE processes          ADD CONSTRAINT fk_processes_department  FOREIGN KEY (department_id)     REFERENCES departments(id);
ALTER TABLE processes          ADD CONSTRAINT fk_processes_parent      FOREIGN KEY (parent_process_id) REFERENCES processes(id);
ALTER TABLE processes          ADD CONSTRAINT fk_processes_responsible FOREIGN KEY (responsible_user_id) REFERENCES users(id);

ALTER TABLE facility_processes ADD CONSTRAINT fk_facproc_facility      FOREIGN KEY (facility_id)       REFERENCES facilities(id) ON DELETE CASCADE;
ALTER TABLE facility_processes ADD CONSTRAINT fk_facproc_process       FOREIGN KEY (process_id)        REFERENCES processes(id) ON DELETE CASCADE;
ALTER TABLE facility_processes ADD CONSTRAINT fk_facproc_tenant        FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;

ALTER TABLE contracts          ADD CONSTRAINT fk_contracts_tenant      FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE contracts          ADD CONSTRAINT fk_contracts_manager     FOREIGN KEY (manager_tenant_id) REFERENCES tenants(id);
ALTER TABLE contracts          ADD CONSTRAINT fk_contracts_client      FOREIGN KEY (client_tenant_id)  REFERENCES tenants(id);

-- Catalogo normativo
ALTER TABLE legal_sources      ADD CONSTRAINT fk_legalsources_country  FOREIGN KEY (country_id)        REFERENCES countries(id);
ALTER TABLE legal_norms        ADD CONSTRAINT fk_legalnorms_country    FOREIGN KEY (country_id)        REFERENCES countries(id);
ALTER TABLE legal_norms        ADD CONSTRAINT fk_legalnorms_source     FOREIGN KEY (source_id)         REFERENCES legal_sources(id);
ALTER TABLE legal_norm_versions ADD CONSTRAINT fk_normversions_norm    FOREIGN KEY (norm_id)           REFERENCES legal_norms(id) ON DELETE CASCADE;
ALTER TABLE legal_articles     ADD CONSTRAINT fk_articles_version      FOREIGN KEY (norm_version_id)   REFERENCES legal_norm_versions(id) ON DELETE CASCADE;
ALTER TABLE legal_articles     ADD CONSTRAINT fk_articles_parent       FOREIGN KEY (parent_article_id) REFERENCES legal_articles(id);

ALTER TABLE legal_relations    ADD CONSTRAINT fk_relations_srcnorm     FOREIGN KEY (source_norm_id)    REFERENCES legal_norms(id) ON DELETE CASCADE;
ALTER TABLE legal_relations    ADD CONSTRAINT fk_relations_srcart      FOREIGN KEY (source_article_id) REFERENCES legal_articles(id);
ALTER TABLE legal_relations    ADD CONSTRAINT fk_relations_tgtnorm     FOREIGN KEY (target_norm_id)    REFERENCES legal_norms(id) ON DELETE CASCADE;
ALTER TABLE legal_relations    ADD CONSTRAINT fk_relations_tgtart      FOREIGN KEY (target_article_id) REFERENCES legal_articles(id);

ALTER TABLE sectors            ADD CONSTRAINT fk_sectors_country       FOREIGN KEY (country_id)        REFERENCES countries(id);
ALTER TABLE sectors            ADD CONSTRAINT fk_sectors_parent        FOREIGN KEY (parent_id)         REFERENCES sectors(id);
ALTER TABLE norm_sectors       ADD CONSTRAINT fk_normsectors_norm      FOREIGN KEY (norm_id)           REFERENCES legal_norms(id) ON DELETE CASCADE;
ALTER TABLE norm_sectors       ADD CONSTRAINT fk_normsectors_sector    FOREIGN KEY (sector_id)         REFERENCES sectors(id);
ALTER TABLE norm_sectors       ADD CONSTRAINT fk_normsectors_article   FOREIGN KEY (article_id)        REFERENCES legal_articles(id);
ALTER TABLE norm_sync_runs     ADD CONSTRAINT fk_syncruns_source       FOREIGN KEY (source_id)         REFERENCES legal_sources(id);

ALTER TABLE facility_norm_assignments ADD CONSTRAINT fk_fna_tenant     FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE facility_norm_assignments ADD CONSTRAINT fk_fna_facility   FOREIGN KEY (facility_id)       REFERENCES facilities(id) ON DELETE CASCADE;
ALTER TABLE facility_norm_assignments ADD CONSTRAINT fk_fna_norm       FOREIGN KEY (norm_id)           REFERENCES legal_norms(id);
ALTER TABLE facility_norm_assignments ADD CONSTRAINT fk_fna_version    FOREIGN KEY (assigned_version_id) REFERENCES legal_norm_versions(id);
ALTER TABLE facility_norm_assignments ADD CONSTRAINT fk_fna_assignedby FOREIGN KEY (assigned_by)       REFERENCES users(id);

-- Matriz legal
ALTER TABLE tenant_legal_matrices ADD CONSTRAINT fk_matrices_tenant    FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE tenant_legal_matrices ADD CONSTRAINT fk_matrices_facility  FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE tenant_legal_matrices ADD CONSTRAINT fk_matrices_approver  FOREIGN KEY (approved_by)       REFERENCES users(id);

ALTER TABLE matrix_norms       ADD CONSTRAINT fk_matrixnorms_tenant    FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE matrix_norms       ADD CONSTRAINT fk_matrixnorms_matrix    FOREIGN KEY (matrix_id)         REFERENCES tenant_legal_matrices(id) ON DELETE CASCADE;
ALTER TABLE matrix_norms       ADD CONSTRAINT fk_matrixnorms_norm      FOREIGN KEY (norm_id)           REFERENCES legal_norms(id);
ALTER TABLE matrix_norms       ADD CONSTRAINT fk_matrixnorms_version   FOREIGN KEY (selected_version_id) REFERENCES legal_norm_versions(id);
ALTER TABLE matrix_norms       ADD CONSTRAINT fk_matrixnorms_sector    FOREIGN KEY (sector_id)         REFERENCES sectors(id);
ALTER TABLE matrix_norms       ADD CONSTRAINT fk_matrixnorms_owner     FOREIGN KEY (owner_user_id)     REFERENCES users(id);

ALTER TABLE article_compliance ADD CONSTRAINT fk_ac_tenant             FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE article_compliance ADD CONSTRAINT fk_ac_matrixnorm         FOREIGN KEY (matrix_norm_id)    REFERENCES matrix_norms(id) ON DELETE CASCADE;
ALTER TABLE article_compliance ADD CONSTRAINT fk_ac_article            FOREIGN KEY (article_id)        REFERENCES legal_articles(id);
ALTER TABLE article_compliance ADD CONSTRAINT fk_ac_facility           FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE article_compliance ADD CONSTRAINT fk_ac_department         FOREIGN KEY (department_id)     REFERENCES departments(id);
ALTER TABLE article_compliance ADD CONSTRAINT fk_ac_responsible        FOREIGN KEY (responsible_user_id) REFERENCES users(id);
ALTER TABLE article_compliance ADD CONSTRAINT fk_ac_assessedby         FOREIGN KEY (assessed_by)       REFERENCES users(id);
ALTER TABLE article_compliance ADD CONSTRAINT fk_ac_approvedby         FOREIGN KEY (approved_by)       REFERENCES users(id);

-- Obligaciones
ALTER TABLE obligation_templates ADD CONSTRAINT fk_obltmpl_country     FOREIGN KEY (country_id)        REFERENCES countries(id);
ALTER TABLE obligations        ADD CONSTRAINT fk_obligations_tenant    FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE obligations        ADD CONSTRAINT fk_obligations_template  FOREIGN KEY (template_id)       REFERENCES obligation_templates(id);
ALTER TABLE obligations        ADD CONSTRAINT fk_obligations_matrixnorm FOREIGN KEY (matrix_norm_id)   REFERENCES matrix_norms(id);
ALTER TABLE obligations        ADD CONSTRAINT fk_obligations_ac        FOREIGN KEY (article_compliance_id) REFERENCES article_compliance(id);
ALTER TABLE obligations        ADD CONSTRAINT fk_obligations_facility  FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE obligations        ADD CONSTRAINT fk_obligations_owner     FOREIGN KEY (owner_user_id)     REFERENCES users(id);

ALTER TABLE tasks              ADD CONSTRAINT fk_tasks_tenant          FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE tasks              ADD CONSTRAINT fk_tasks_obligation      FOREIGN KEY (obligation_id)     REFERENCES obligations(id) ON DELETE CASCADE;
ALTER TABLE tasks              ADD CONSTRAINT fk_tasks_parent          FOREIGN KEY (parent_task_id)    REFERENCES tasks(id);
ALTER TABLE tasks              ADD CONSTRAINT fk_tasks_assignee        FOREIGN KEY (assignee_user_id)  REFERENCES users(id);
ALTER TABLE tasks              ADD CONSTRAINT fk_tasks_department      FOREIGN KEY (department_id)     REFERENCES departments(id);

ALTER TABLE declaration_templates ADD CONSTRAINT fk_dectmpl_country    FOREIGN KEY (country_id)        REFERENCES countries(id);
ALTER TABLE declaration_templates ADD CONSTRAINT fk_dectmpl_document   FOREIGN KEY (source_document_id) REFERENCES documents(id);

ALTER TABLE declaration_submissions ADD CONSTRAINT fk_ds_tenant        FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE declaration_submissions ADD CONSTRAINT fk_ds_obligation    FOREIGN KEY (obligation_id)     REFERENCES obligations(id) ON DELETE CASCADE;
ALTER TABLE declaration_submissions ADD CONSTRAINT fk_ds_template      FOREIGN KEY (template_id)       REFERENCES declaration_templates(id);
ALTER TABLE declaration_submissions ADD CONSTRAINT fk_ds_facility      FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE declaration_submissions ADD CONSTRAINT fk_ds_preparedby    FOREIGN KEY (prepared_by)       REFERENCES users(id);
ALTER TABLE declaration_submissions ADD CONSTRAINT fk_ds_reviewedby    FOREIGN KEY (reviewed_by)       REFERENCES users(id);
ALTER TABLE declaration_submissions ADD CONSTRAINT fk_ds_submittedby   FOREIGN KEY (submitted_by)      REFERENCES users(id);
ALTER TABLE declaration_submissions ADD CONSTRAINT fk_ds_receipt       FOREIGN KEY (receipt_document_id) REFERENCES documents(id);

-- Documentos
ALTER TABLE documents          ADD CONSTRAINT fk_documents_tenant      FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE documents          ADD CONSTRAINT fk_documents_curversion  FOREIGN KEY (current_version_id) REFERENCES document_versions(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE document_versions  ADD CONSTRAINT fk_docversions_tenant    FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE document_versions  ADD CONSTRAINT fk_docversions_document  FOREIGN KEY (document_id)       REFERENCES documents(id) ON DELETE CASCADE;
ALTER TABLE document_versions  ADD CONSTRAINT fk_docversions_createdby FOREIGN KEY (created_by)        REFERENCES users(id);
ALTER TABLE entity_documents   ADD CONSTRAINT fk_entdocs_tenant        FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE entity_documents   ADD CONSTRAINT fk_entdocs_document      FOREIGN KEY (document_id)       REFERENCES documents(id) ON DELETE CASCADE;

-- Auditorias y mejora
ALTER TABLE audits             ADD CONSTRAINT fk_audits_tenant         FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE audits             ADD CONSTRAINT fk_audits_facility       FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE audits             ADD CONSTRAINT fk_audits_lead           FOREIGN KEY (lead_auditor_user_id) REFERENCES users(id);

ALTER TABLE audit_items        ADD CONSTRAINT fk_auditems_tenant       FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE audit_items        ADD CONSTRAINT fk_auditems_audit        FOREIGN KEY (audit_id)          REFERENCES audits(id) ON DELETE CASCADE;
ALTER TABLE audit_items        ADD CONSTRAINT fk_auditems_ac           FOREIGN KEY (article_compliance_id) REFERENCES article_compliance(id);
ALTER TABLE audit_items        ADD CONSTRAINT fk_auditems_auditor      FOREIGN KEY (auditor_user_id)   REFERENCES users(id);

ALTER TABLE audit_participants ADD CONSTRAINT fk_auditpart_audit       FOREIGN KEY (audit_id)          REFERENCES audits(id) ON DELETE CASCADE;
ALTER TABLE audit_participants ADD CONSTRAINT fk_auditpart_user        FOREIGN KEY (user_id)           REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE audit_participants ADD CONSTRAINT fk_auditpart_tenant      FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;

ALTER TABLE nonconformities    ADD CONSTRAINT fk_nc_tenant             FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE nonconformities    ADD CONSTRAINT fk_nc_facility           FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE nonconformities    ADD CONSTRAINT fk_nc_audititem          FOREIGN KEY (audit_item_id)     REFERENCES audit_items(id);
ALTER TABLE nonconformities    ADD CONSTRAINT fk_nc_ac                 FOREIGN KEY (article_compliance_id) REFERENCES article_compliance(id);
ALTER TABLE nonconformities    ADD CONSTRAINT fk_nc_detectedby         FOREIGN KEY (detected_by)       REFERENCES users(id);
ALTER TABLE nonconformities    ADD CONSTRAINT fk_nc_owner              FOREIGN KEY (owner_user_id)     REFERENCES users(id);

ALTER TABLE action_plans       ADD CONSTRAINT fk_ap_tenant             FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE action_plans       ADD CONSTRAINT fk_ap_ac                 FOREIGN KEY (article_compliance_id) REFERENCES article_compliance(id);
ALTER TABLE action_plans       ADD CONSTRAINT fk_ap_nc                 FOREIGN KEY (nonconformity_id)  REFERENCES nonconformities(id) ON DELETE CASCADE;
ALTER TABLE action_plans       ADD CONSTRAINT fk_ap_owner              FOREIGN KEY (owner_user_id)     REFERENCES users(id);
ALTER TABLE action_plans       ADD CONSTRAINT fk_ap_verifiedby         FOREIGN KEY (verified_by)       REFERENCES users(id);

ALTER TABLE entity_status_history ADD CONSTRAINT fk_esh_tenant         FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE entity_status_history ADD CONSTRAINT fk_esh_changedby      FOREIGN KEY (changed_by)        REFERENCES users(id);

-- Notificaciones, soporte, chatbot, sistema
ALTER TABLE notification_templates ADD CONSTRAINT fk_nt_tenant         FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE notification_rules ADD CONSTRAINT fk_nr_tenant             FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE notifications      ADD CONSTRAINT fk_notif_tenant          FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE notifications      ADD CONSTRAINT fk_notif_rule            FOREIGN KEY (rule_id)           REFERENCES notification_rules(id);
ALTER TABLE notifications      ADD CONSTRAINT fk_notif_recipient       FOREIGN KEY (recipient_user_id) REFERENCES users(id);

ALTER TABLE support_tickets    ADD CONSTRAINT fk_tickets_tenant        FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE support_tickets    ADD CONSTRAINT fk_tickets_createdby     FOREIGN KEY (created_by_user_id) REFERENCES users(id);
ALTER TABLE support_tickets    ADD CONSTRAINT fk_tickets_assignedto    FOREIGN KEY (assigned_to)       REFERENCES users(id);
ALTER TABLE support_ticket_messages ADD CONSTRAINT fk_tktmsg_tenant    FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE support_ticket_messages ADD CONSTRAINT fk_tktmsg_ticket    FOREIGN KEY (ticket_id)         REFERENCES support_tickets(id) ON DELETE CASCADE;
ALTER TABLE support_ticket_messages ADD CONSTRAINT fk_tktmsg_author    FOREIGN KEY (author_user_id)    REFERENCES users(id);

ALTER TABLE chatbot_conversations ADD CONSTRAINT fk_conv_tenant        FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE chatbot_conversations ADD CONSTRAINT fk_conv_user          FOREIGN KEY (user_id)           REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE chatbot_conversations ADD CONSTRAINT fk_conv_facility      FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE chatbot_messages   ADD CONSTRAINT fk_msg_tenant            FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE chatbot_messages   ADD CONSTRAINT fk_msg_conversation      FOREIGN KEY (conversation_id)   REFERENCES chatbot_conversations(id) ON DELETE CASCADE;

ALTER TABLE integration_accounts ADD CONSTRAINT fk_intacc_tenant       FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE audit_log          ADD CONSTRAINT fk_auditlog_tenant       FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE audit_log          ADD CONSTRAINT fk_auditlog_actor        FOREIGN KEY (actor_user_id)     REFERENCES users(id);

-- ISO 14001
ALTER TABLE environmental_aspects ADD CONSTRAINT fk_ea_tenant          FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE environmental_aspects ADD CONSTRAINT fk_ea_facility        FOREIGN KEY (facility_id)       REFERENCES facilities(id) ON DELETE CASCADE;
ALTER TABLE environmental_aspects ADD CONSTRAINT fk_ea_process         FOREIGN KEY (process_id)        REFERENCES processes(id);
ALTER TABLE environmental_aspects ADD CONSTRAINT fk_ea_ac              FOREIGN KEY (article_compliance_id) REFERENCES article_compliance(id);
ALTER TABLE environmental_aspects ADD CONSTRAINT fk_ea_responsible     FOREIGN KEY (responsible_user_id) REFERENCES users(id);

ALTER TABLE risks_opportunities ADD CONSTRAINT fk_ro_tenant            FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE risks_opportunities ADD CONSTRAINT fk_ro_facility          FOREIGN KEY (facility_id)       REFERENCES facilities(id);
ALTER TABLE risks_opportunities ADD CONSTRAINT fk_ro_aspect            FOREIGN KEY (environmental_aspect_id) REFERENCES environmental_aspects(id);
ALTER TABLE risks_opportunities ADD CONSTRAINT fk_ro_actionplan        FOREIGN KEY (action_plan_id)    REFERENCES action_plans(id);
ALTER TABLE risks_opportunities ADD CONSTRAINT fk_ro_owner             FOREIGN KEY (owner_user_id)     REFERENCES users(id);

ALTER TABLE regulated_equipment ADD CONSTRAINT fk_re_tenant            FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE regulated_equipment ADD CONSTRAINT fk_re_facility          FOREIGN KEY (facility_id)       REFERENCES facilities(id) ON DELETE CASCADE;
ALTER TABLE equipment_operators ADD CONSTRAINT fk_eo_equipment         FOREIGN KEY (equipment_id)      REFERENCES regulated_equipment(id) ON DELETE CASCADE;
ALTER TABLE equipment_operators ADD CONSTRAINT fk_eo_user              FOREIGN KEY (user_id)           REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE equipment_operators ADD CONSTRAINT fk_eo_tenant            FOREIGN KEY (tenant_id)         REFERENCES tenants(id) ON DELETE CASCADE;


-- ───────────────────────────────────────────────────────────────────────────
--  5. INDICES
--
--  Los indices de tenant son parciales (WHERE deleted_at IS NULL) porque toda
--  consulta de negocio filtra por tenant y descarta lo borrado logicamente.
-- ───────────────────────────────────────────────────────────────────────────

CREATE INDEX ix_facilities_tenant      ON facilities (tenant_id)   WHERE deleted_at IS NULL;
CREATE INDEX ix_departments_tenant     ON departments (tenant_id)  WHERE deleted_at IS NULL;
CREATE INDEX ix_users_tenant           ON users (tenant_id)        WHERE deleted_at IS NULL;
CREATE INDEX ix_users_status           ON users (tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_roles_tenant           ON roles (tenant_id)        WHERE deleted_at IS NULL;
-- La PK (user_id, permission_id) ya cubre "que permisos tiene este usuario".
-- Este indice cubre el sentido inverso, que es el de RLS: filtrar por tenant.
CREATE INDEX ix_userperm_tenant        ON user_permissions (tenant_id);
CREATE INDEX ix_processes_tenant       ON processes (tenant_id)    WHERE deleted_at IS NULL;
CREATE INDEX ix_contracts_manager      ON contracts (manager_tenant_id);
CREATE INDEX ix_contracts_client       ON contracts (client_tenant_id);
CREATE INDEX ix_tenants_parent         ON tenants (parent_tenant_id) WHERE parent_tenant_id IS NOT NULL;

CREATE INDEX ix_legal_norms_status     ON legal_norms (status)      WHERE deleted_at IS NULL;
CREATE INDEX ix_legal_norms_type       ON legal_norms (norm_type);
CREATE INDEX ix_legal_norms_subjects   ON legal_norms USING gin (subjects);
CREATE INDEX ix_norm_versions_norm     ON legal_norm_versions (norm_id);
CREATE INDEX ix_norm_versions_current  ON legal_norm_versions (norm_id) WHERE is_current;
CREATE INDEX ix_articles_version       ON legal_articles (norm_version_id, display_order);
CREATE INDEX ix_articles_fts           ON legal_articles USING gin (to_tsvector('spanish', content));
CREATE INDEX ix_norm_versions_fts      ON legal_norm_versions USING gin (to_tsvector('spanish', coalesce(full_text,'')));
CREATE INDEX ix_relations_source       ON legal_relations (source_norm_id);
CREATE INDEX ix_relations_target       ON legal_relations (target_norm_id);

CREATE INDEX ix_matrices_tenant_year   ON tenant_legal_matrices (tenant_id, period_year) WHERE deleted_at IS NULL;
-- Unicidad de la matriz: una sola por empresa, ano, instalacion y version.
-- Va como indice parcial y no como CONSTRAINT por el borrado logico: una matriz
-- archivada con deleted_at no debe impedir crear la del mismo periodo de nuevo.
-- NULLS NOT DISTINCT porque facility_id NULL significa "nivel empresa", que es
-- un valor con significado y no un dato faltante: sin esto se podrian crear
-- infinitas matrices de empresa para el mismo ano.
CREATE UNIQUE INDEX uq_matrices_periodo ON tenant_legal_matrices
    (tenant_id, period_year, facility_id, version_no) NULLS NOT DISTINCT
    WHERE deleted_at IS NULL;
CREATE INDEX ix_matrixnorms_matrix     ON matrix_norms (matrix_id)  WHERE deleted_at IS NULL;
CREATE INDEX ix_matrixnorms_review     ON matrix_norms (next_review_date) WHERE deleted_at IS NULL;
CREATE INDEX ix_ac_tenant_status       ON article_compliance (tenant_id, compliance_status) WHERE deleted_at IS NULL;
CREATE INDEX ix_ac_matrixnorm          ON article_compliance (matrix_norm_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_ac_attributes          ON article_compliance USING gin (attributes);

CREATE INDEX ix_obligations_tenant_due ON obligations (tenant_id, due_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_obligations_status     ON obligations (tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_tasks_tenant_due       ON tasks (tenant_id, due_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_tasks_assignee         ON tasks (assignee_user_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_tasks_obligation       ON tasks (obligation_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_ds_obligation          ON declaration_submissions (obligation_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_ds_folio               ON declaration_submissions (external_folio) WHERE external_folio IS NOT NULL;

CREATE INDEX ix_documents_tenant       ON documents (tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_documents_tags         ON documents USING gin (tags);
CREATE INDEX ix_docversions_document   ON document_versions (document_id);
CREATE INDEX ix_entdocs_entity         ON entity_documents (entity_type, entity_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_entdocs_vencimiento    ON entity_documents (valid_to) WHERE valid_to IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX ix_audits_tenant_status   ON audits (tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_auditems_audit         ON audit_items (audit_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_nc_tenant_status       ON nonconformities (tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_nc_due                 ON nonconformities (due_date) WHERE deleted_at IS NULL;
CREATE INDEX ix_ap_tenant_status       ON action_plans (tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_esh_entity             ON entity_status_history (entity_type, entity_id, changed_at DESC);

CREATE INDEX ix_notifications_pending  ON notifications (scheduled_at) WHERE status = 'queued';
CREATE INDEX ix_notifications_user     ON notifications (recipient_user_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_tickets_tenant_status  ON support_tickets (tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_tktmsg_ticket          ON support_ticket_messages (ticket_id, created_at);
CREATE INDEX ix_conv_user              ON chatbot_conversations (user_id, last_message_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX ix_msg_conversation       ON chatbot_messages (conversation_id, created_at);
CREATE INDEX ix_msg_citednorms         ON chatbot_messages USING gin (cited_norm_ids);

-- BRIN en vez de B-tree: el audit log crece mucho y se consulta por rango de
-- fecha sobre datos que ya llegan ordenados en el tiempo.
CREATE INDEX ix_auditlog_occurred      ON audit_log USING brin (occurred_at);
CREATE INDEX ix_auditlog_entity        ON audit_log (entity_type, entity_id);
CREATE INDEX ix_auditlog_actor         ON audit_log (actor_user_id, occurred_at DESC);

CREATE INDEX ix_ea_tenant_facility     ON environmental_aspects (tenant_id, facility_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_ea_significance        ON environmental_aspects (tenant_id, significance) WHERE deleted_at IS NULL;
CREATE INDEX ix_ro_tenant_type         ON risks_opportunities (tenant_id, entry_type, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_ro_aspect              ON risks_opportunities (environmental_aspect_id) WHERE environmental_aspect_id IS NOT NULL;
CREATE INDEX ix_re_tenant_facility     ON regulated_equipment (tenant_id, facility_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_re_vencimiento         ON regulated_equipment (registration_expires_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_eo_user                ON equipment_operators (user_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_eo_cert_vencimiento    ON equipment_operators (certification_expires_at) WHERE deleted_at IS NULL;


-- ───────────────────────────────────────────────────────────────────────────
--  6. TRIGGERS updated_at
-- ───────────────────────────────────────────────────────────────────────────

DO $$
DECLARE t text;
BEGIN
    FOR t IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE c.relkind = 'r'
          AND n.nspname = 'public'
          AND a.attname = 'updated_at'
          AND NOT a.attisdropped
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    END LOOP;
END $$;


-- ───────────────────────────────────────────────────────────────────────────
--  7. ROW LEVEL SECURITY
--
--  CLAUDE.md §4: el filtro por tenant_id en la aplicacion es la primera
--  barrera; RLS es la segunda. Un bug de repositorio que olvide el WHERE no
--  debe poder filtrar datos de otra empresa.
--
--  La API debe abrir cada transaccion con:
--      SET LOCAL ambienta.tenant_id = '<uuid del tenant de la sesion>';
--
--  El catalogo global (countries, legal_*, sectors, permissions) NO lleva RLS:
--  es contenido publico compartido entre todos los tenants.
-- ───────────────────────────────────────────────────────────────────────────

DO $$
DECLARE t text;
BEGIN
    FOR t IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE c.relkind = 'r'
          AND n.nspname = 'public'
          AND a.attname = 'tenant_id'
          AND NOT a.attisdropped
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I
             USING (tenant_id = current_tenant_id())
             WITH CHECK (tenant_id = current_tenant_id())', t);
    END LOOP;
END $$;


-- ───────────────────────────────────────────────────────────────────────────
--  8. ROL DE APLICACION
--
--  El audit log debe ser inmutable (RNF-08, RNF-25): la aplicacion inserta y
--  lee, pero no puede modificar ni borrar. Esto se cumple en la base, no por
--  disciplina del codigo.
-- ───────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ambienta_app') THEN
        CREATE ROLE ambienta_app NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO ambienta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ambienta_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ambienta_app;

REVOKE UPDATE, DELETE ON audit_log FROM ambienta_app;
REVOKE UPDATE, DELETE ON entity_status_history FROM ambienta_app;

COMMIT;
