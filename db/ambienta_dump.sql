--
-- PostgreSQL database dump
--

\restrict TVBkszhBvDI9XErzstYsbif3MFqaTtSbs0xpPskOd1aoF0qq9SWI1tWcXFWg8du

-- Dumped from database version 16.14 (Debian 16.14-1.pgdg12+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg12+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: ai; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ai;


--
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;


--
-- Name: EXTENSION citext; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: current_tenant_id(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.current_tenant_id() RETURNS uuid
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN nullif(current_setting('ambienta.tenant_id', true), '')::uuid;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: action_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.action_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    article_compliance_id uuid,
    nonconformity_id uuid,
    title character varying(240) NOT NULL,
    root_cause text,
    objective text NOT NULL,
    status character varying(24) DEFAULT 'draft'::character varying NOT NULL,
    priority character varying(16) DEFAULT 'medium'::character varying NOT NULL,
    owner_user_id uuid,
    target_date date,
    verified_at timestamp with time zone,
    verified_by uuid,
    success_criteria jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT action_plans_priority_check CHECK (((priority)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'critical'::character varying])::text[]))),
    CONSTRAINT action_plans_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'approved'::character varying, 'in_progress'::character varying, 'completed'::character varying, 'verified'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT ck_action_plans_origen CHECK (((article_compliance_id IS NOT NULL) OR (nonconformity_id IS NOT NULL)))
);

ALTER TABLE ONLY public.action_plans FORCE ROW LEVEL SECURITY;


--
-- Name: CONSTRAINT ck_action_plans_origen ON action_plans; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON CONSTRAINT ck_action_plans_origen ON public.action_plans IS 'Un plan nace de un incumplimiento legal o de un hallazgo. Sin origen no es trazable.';


--
-- Name: article_compliance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.article_compliance (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    matrix_norm_id uuid NOT NULL,
    article_id uuid NOT NULL,
    facility_id uuid,
    department_id uuid,
    compliance_status character varying(24) DEFAULT 'pending'::character varying NOT NULL,
    compliance_method text,
    assessment_reason text,
    risk_level character varying(16),
    responsible_user_id uuid,
    assessed_at timestamp with time zone,
    assessed_by uuid,
    approved_at timestamp with time zone,
    approved_by uuid,
    attributes jsonb DEFAULT '{}'::jsonb NOT NULL,
    row_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT article_compliance_compliance_status_check CHECK (((compliance_status)::text = ANY ((ARRAY['compliant'::character varying, 'non_compliant'::character varying, 'partial'::character varying, 'not_applicable'::character varying, 'pending'::character varying])::text[]))),
    CONSTRAINT article_compliance_risk_level_check CHECK (((risk_level IS NULL) OR ((risk_level)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'critical'::character varying])::text[]))))
);

ALTER TABLE ONLY public.article_compliance FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN article_compliance.row_version; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.article_compliance.row_version IS 'Control optimista de concurrencia.';


--
-- Name: audit_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    audit_id uuid NOT NULL,
    article_compliance_id uuid,
    sequence integer NOT NULL,
    question text NOT NULL,
    result character varying(24) DEFAULT 'pending'::character varying NOT NULL,
    notes text,
    auditor_user_id uuid,
    assessed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT audit_items_result_check CHECK (((result)::text = ANY ((ARRAY['conform'::character varying, 'nonconform'::character varying, 'observation'::character varying, 'not_applicable'::character varying, 'pending'::character varying])::text[])))
);

ALTER TABLE ONLY public.audit_items FORCE ROW LEVEL SECURITY;


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id bigint NOT NULL,
    tenant_id uuid NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    actor_user_id uuid,
    action character varying(60) NOT NULL,
    entity_type character varying(60) NOT NULL,
    entity_id uuid,
    request_id uuid,
    ip_address inet,
    reason text,
    before_data jsonb,
    after_data jsonb,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT audit_log_action_check CHECK (((action)::text = ANY ((ARRAY['create'::character varying, 'update'::character varying, 'delete'::character varying, 'approve'::character varying, 'login'::character varying, 'download'::character varying, 'sync'::character varying])::text[])))
);

ALTER TABLE ONLY public.audit_log FORCE ROW LEVEL SECURITY;


--
-- Name: TABLE audit_log; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.audit_log IS 'Registro inmutable (RNF-08, RNF-25). La inmutabilidad se refuerza en la seccion 7 revocando UPDATE y DELETE al rol de aplicacion.';


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: audit_participants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_participants (
    audit_id uuid NOT NULL,
    user_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    external_name character varying(180),
    external_email public.citext,
    participant_role character varying(32) NOT NULL,
    attendance_status character varying(20) DEFAULT 'invited'::character varying NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT audit_participants_attendance_status_check CHECK (((attendance_status)::text = ANY ((ARRAY['invited'::character varying, 'confirmed'::character varying, 'declined'::character varying, 'attended'::character varying])::text[]))),
    CONSTRAINT audit_participants_participant_role_check CHECK (((participant_role)::text = ANY ((ARRAY['lead_auditor'::character varying, 'auditor'::character varying, 'auditee'::character varying, 'observer'::character varying, 'approver'::character varying])::text[])))
);

ALTER TABLE ONLY public.audit_participants FORCE ROW LEVEL SECURITY;


--
-- Name: audits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audits (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid,
    code character varying(60) NOT NULL,
    title character varying(240) NOT NULL,
    audit_type character varying(24) NOT NULL,
    scope text NOT NULL,
    lead_auditor_user_id uuid,
    planned_start timestamp with time zone,
    planned_end timestamp with time zone,
    actual_start timestamp with time zone,
    actual_end timestamp with time zone,
    status character varying(20) DEFAULT 'planned'::character varying NOT NULL,
    criteria jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT audits_audit_type_check CHECK (((audit_type)::text = ANY ((ARRAY['internal'::character varying, 'external'::character varying, 'regulatory'::character varying, 'supplier'::character varying])::text[]))),
    CONSTRAINT audits_status_check CHECK (((status)::text = ANY ((ARRAY['planned'::character varying, 'active'::character varying, 'reporting'::character varying, 'closed'::character varying, 'cancelled'::character varying])::text[])))
);

ALTER TABLE ONLY public.audits FORCE ROW LEVEL SECURITY;


--
-- Name: chatbot_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chatbot_conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    title character varying(240),
    scope character varying(24) DEFAULT 'tenant'::character varying NOT NULL,
    facility_id uuid,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    context_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    last_message_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT chatbot_conversations_scope_check CHECK (((scope)::text = ANY ((ARRAY['tenant'::character varying, 'facility'::character varying, 'legal_matrix'::character varying, 'platform'::character varying])::text[]))),
    CONSTRAINT chatbot_conversations_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'archived'::character varying, 'deleted'::character varying])::text[])))
);

ALTER TABLE ONLY public.chatbot_conversations FORCE ROW LEVEL SECURITY;


--
-- Name: chatbot_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chatbot_messages (
    id bigint NOT NULL,
    tenant_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    role character varying(16) NOT NULL,
    content text NOT NULL,
    cited_norm_ids uuid[] DEFAULT '{}'::uuid[] NOT NULL,
    citations jsonb DEFAULT '[]'::jsonb NOT NULL,
    model_name character varying(100),
    token_usage jsonb DEFAULT '{}'::jsonb NOT NULL,
    feedback jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chatbot_messages_role_check CHECK (((role)::text = ANY ((ARRAY['user'::character varying, 'assistant'::character varying, 'system'::character varying, 'tool'::character varying])::text[])))
);

ALTER TABLE ONLY public.chatbot_messages FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN chatbot_messages.cited_norm_ids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.chatbot_messages.cited_norm_ids IS 'RF-63: el agente debe citar fuente normativa. Esto lo hace verificable.';


--
-- Name: chatbot_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chatbot_messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chatbot_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chatbot_messages_id_seq OWNED BY public.chatbot_messages.id;


--
-- Name: contracts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contracts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    manager_tenant_id uuid NOT NULL,
    client_tenant_id uuid NOT NULL,
    contract_number character varying(100) NOT NULL,
    title character varying(240) NOT NULL,
    status character varying(24) DEFAULT 'draft'::character varying NOT NULL,
    start_date date NOT NULL,
    end_date date,
    scope jsonb DEFAULT '{}'::jsonb NOT NULL,
    terms_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_contracts_fechas CHECK (((end_date IS NULL) OR (end_date >= start_date))),
    CONSTRAINT ck_contracts_partes CHECK ((manager_tenant_id <> client_tenant_id)),
    CONSTRAINT contracts_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'pending_signature'::character varying, 'active'::character varying, 'suspended'::character varying, 'expired'::character varying, 'terminated'::character varying])::text[])))
);

ALTER TABLE ONLY public.contracts FORCE ROW LEVEL SECURITY;


--
-- Name: TABLE contracts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.contracts IS 'Contrato formal que habilita la sub-tenancy (RF-66).';


--
-- Name: countries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.countries (
    id smallint NOT NULL,
    iso2 character(2) NOT NULL,
    iso3 character(3) NOT NULL,
    name character varying(120) NOT NULL,
    default_timezone character varying(64) DEFAULT 'America/Santiago'::character varying NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: TABLE countries; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.countries IS 'Catalogo global de paises. Sin tenant_id.';


--
-- Name: countries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.countries_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: countries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.countries_id_seq OWNED BY public.countries.id;


--
-- Name: declaration_submissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.declaration_submissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    obligation_id uuid NOT NULL,
    template_id uuid,
    facility_id uuid,
    period_label character varying(80),
    version_no integer DEFAULT 1 NOT NULL,
    status character varying(24) DEFAULT 'draft'::character varying NOT NULL,
    prepared_by uuid,
    reviewed_by uuid,
    submitted_by uuid,
    submitted_at timestamp with time zone,
    external_folio character varying(160),
    submission_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    validation_result jsonb DEFAULT '{}'::jsonb NOT NULL,
    receipt_document_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT declaration_submissions_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'validation_error'::character varying, 'ready'::character varying, 'submitted'::character varying, 'accepted'::character varying, 'rejected'::character varying, 'rectified'::character varying])::text[])))
);

ALTER TABLE ONLY public.declaration_submissions FORCE ROW LEVEL SECURITY;


--
-- Name: declaration_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.declaration_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    country_id smallint NOT NULL,
    system_code character varying(40) NOT NULL,
    name character varying(220) NOT NULL,
    version character varying(40) NOT NULL,
    valid_from date,
    valid_to date,
    schema_definition jsonb DEFAULT '{}'::jsonb NOT NULL,
    workbook_structure jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_document_id uuid,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone
);


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid,
    parent_department_id uuid,
    code character varying(50) NOT NULL,
    name character varying(160) NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone
);

ALTER TABLE ONLY public.departments FORCE ROW LEVEL SECURITY;


--
-- Name: document_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    document_id uuid NOT NULL,
    version_no integer NOT NULL,
    storage_provider character varying(32) NOT NULL,
    storage_key character varying(1000) NOT NULL,
    file_name character varying(255) NOT NULL,
    mime_type character varying(150) NOT NULL,
    size_bytes bigint NOT NULL,
    checksum_sha256 character(64),
    source character varying(24) DEFAULT 'upload'::character varying NOT NULL,
    version_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    CONSTRAINT document_versions_size_bytes_check CHECK ((size_bytes >= 0)),
    CONSTRAINT document_versions_source_check CHECK (((source)::text = ANY ((ARRAY['upload'::character varying, 'generated'::character varying, 'imported'::character varying, 'email'::character varying])::text[]))),
    CONSTRAINT document_versions_storage_provider_check CHECK (((storage_provider)::text = ANY ((ARRAY['s3'::character varying, 'backblaze'::character varying, 'google_drive'::character varying, 'onedrive'::character varying])::text[])))
);

ALTER TABLE ONLY public.document_versions FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN document_versions.storage_key; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.document_versions.storage_key IS 'Clave o ID externo. Nunca una URL firmada.';


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    document_type character varying(40) NOT NULL,
    current_version_id uuid,
    title character varying(240) NOT NULL,
    classification character varying(20) DEFAULT 'internal'::character varying NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT documents_classification_check CHECK (((classification)::text = ANY ((ARRAY['public'::character varying, 'internal'::character varying, 'confidential'::character varying, 'restricted'::character varying])::text[]))),
    CONSTRAINT documents_document_type_check CHECK (((document_type)::text = ANY ((ARRAY['evidence'::character varying, 'declaration_template'::character varying, 'receipt'::character varying, 'contract'::character varying, 'audit'::character varying, 'email_attachment'::character varying, 'other'::character varying])::text[]))),
    CONSTRAINT documents_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'active'::character varying, 'archived'::character varying, 'deleted'::character varying])::text[])))
);

ALTER TABLE ONLY public.documents FORCE ROW LEVEL SECURITY;


--
-- Name: TABLE documents; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.documents IS 'Solo metadatos. El binario vive en object storage, Drive u OneDrive.';


--
-- Name: entity_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_documents (
    id bigint NOT NULL,
    tenant_id uuid NOT NULL,
    document_id uuid NOT NULL,
    entity_type character varying(40) NOT NULL,
    entity_id uuid NOT NULL,
    purpose character varying(32) NOT NULL,
    is_required boolean DEFAULT false NOT NULL,
    valid_from date,
    valid_to date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT entity_documents_entity_type_check CHECK (((entity_type)::text = ANY ((ARRAY['article_compliance'::character varying, 'obligation'::character varying, 'task'::character varying, 'action_plan'::character varying, 'audit'::character varying, 'nonconformity'::character varying, 'contract'::character varying, 'environmental_aspect'::character varying, 'risk_opportunity'::character varying, 'regulated_equipment'::character varying, 'declaration_submission'::character varying])::text[]))),
    CONSTRAINT entity_documents_purpose_check CHECK (((purpose)::text = ANY ((ARRAY['evidence'::character varying, 'support'::character varying, 'template'::character varying, 'result'::character varying, 'approval'::character varying])::text[])))
);

ALTER TABLE ONLY public.entity_documents FORCE ROW LEVEL SECURITY;


--
-- Name: TABLE entity_documents; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.entity_documents IS 'Vinculo polimorfico controlado. Evita 11 tablas de union casi identicas; a cambio la integridad de entity_id la valida el servicio, no la base.';


--
-- Name: entity_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.entity_documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: entity_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.entity_documents_id_seq OWNED BY public.entity_documents.id;


--
-- Name: entity_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_status_history (
    id bigint NOT NULL,
    tenant_id uuid NOT NULL,
    entity_type character varying(40) NOT NULL,
    entity_id uuid NOT NULL,
    from_status character varying(40),
    to_status character varying(40) NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by uuid,
    reason text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT entity_status_history_entity_type_check CHECK (((entity_type)::text = ANY ((ARRAY['obligation'::character varying, 'declaration_submission'::character varying, 'audit'::character varying, 'nonconformity'::character varying, 'action_plan'::character varying, 'task'::character varying])::text[])))
);

ALTER TABLE ONLY public.entity_status_history FORCE ROW LEVEL SECURITY;


--
-- Name: TABLE entity_status_history; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.entity_status_history IS 'Historial funcional que alimenta el timeline de la UI. No reemplaza a audit_log.';


--
-- Name: entity_status_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.entity_status_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: entity_status_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.entity_status_history_id_seq OWNED BY public.entity_status_history.id;


--
-- Name: environmental_aspects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.environmental_aspects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid NOT NULL,
    process_id uuid,
    article_compliance_id uuid,
    activity character varying(240) NOT NULL,
    aspect character varying(240) NOT NULL,
    impact_type character varying(120) NOT NULL,
    operating_condition character varying(20) DEFAULT 'normal'::character varying NOT NULL,
    severity_score smallint,
    frequency_score smallint,
    legal_score smallint,
    total_score integer,
    significance character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    responsible_user_id uuid,
    controls jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT environmental_aspects_frequency_score_check CHECK (((frequency_score IS NULL) OR ((frequency_score >= 1) AND (frequency_score <= 10)))),
    CONSTRAINT environmental_aspects_legal_score_check CHECK (((legal_score IS NULL) OR ((legal_score >= 1) AND (legal_score <= 10)))),
    CONSTRAINT environmental_aspects_operating_condition_check CHECK (((operating_condition)::text = ANY ((ARRAY['normal'::character varying, 'anormal'::character varying, 'emergencia'::character varying])::text[]))),
    CONSTRAINT environmental_aspects_severity_score_check CHECK (((severity_score IS NULL) OR ((severity_score >= 1) AND (severity_score <= 10)))),
    CONSTRAINT environmental_aspects_significance_check CHECK (((significance)::text = ANY ((ARRAY['compliant'::character varying, 'partial'::character varying, 'non_compliant'::character varying, 'pending'::character varying])::text[])))
);

ALTER TABLE ONLY public.environmental_aspects FORCE ROW LEVEL SECURITY;


--
-- Name: TABLE environmental_aspects; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.environmental_aspects IS 'ISO 14001 §6.1.2. No estaba en el modelo v2; la pantalla ya existe en el frontend.';


--
-- Name: equipment_operators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipment_operators (
    equipment_id uuid NOT NULL,
    user_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    certification_class character varying(40),
    certification_number character varying(80),
    certification_expires_at date,
    is_primary boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone
);

ALTER TABLE ONLY public.equipment_operators FORCE ROW LEVEL SECURITY;


--
-- Name: TABLE equipment_operators; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.equipment_operators IS 'Un equipo sin operador con certificacion vigente es un incumplimiento; la pantalla lo marca.';


--
-- Name: facilities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.facilities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(180) NOT NULL,
    facility_type character varying(40) NOT NULL,
    address character varying(300),
    region_code character varying(20),
    commune_code character varying(20),
    latitude numeric(9,6),
    longitude numeric(9,6),
    environmental_identifiers jsonb DEFAULT '{}'::jsonb NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone
);

ALTER TABLE ONLY public.facilities FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN facilities.environmental_identifiers; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.facilities.environmental_identifiers IS 'IDs sectoriales: RETC, SIDREP, SINADER.';


--
-- Name: facility_norm_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.facility_norm_assignments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid NOT NULL,
    norm_id uuid NOT NULL,
    assigned_version_id uuid,
    assignment_status character varying(24) DEFAULT 'pending_review'::character varying NOT NULL,
    applicability_reason text,
    assigned_by uuid,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL,
    source character varying(24) DEFAULT 'manual'::character varying NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT facility_norm_assignments_assignment_status_check CHECK (((assignment_status)::text = ANY ((ARRAY['suggested'::character varying, 'assigned'::character varying, 'rejected'::character varying, 'pending_review'::character varying])::text[]))),
    CONSTRAINT facility_norm_assignments_source_check CHECK (((source)::text = ANY ((ARRAY['manual'::character varying, 'rule'::character varying, 'import'::character varying, 'ai_assisted'::character varying])::text[])))
);

ALTER TABLE ONLY public.facility_norm_assignments FORCE ROW LEVEL SECURITY;


--
-- Name: facility_processes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.facility_processes (
    facility_id uuid NOT NULL,
    process_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    is_primary boolean DEFAULT false NOT NULL,
    scope_notes text,
    active_from date,
    active_to date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone
);

ALTER TABLE ONLY public.facility_processes FORCE ROW LEVEL SECURITY;


--
-- Name: integration_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.integration_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    provider character varying(40) NOT NULL,
    external_account_id character varying(255),
    display_name character varying(180),
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    scopes text[] DEFAULT '{}'::text[] NOT NULL,
    secret_reference character varying(500),
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    last_sync_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT integration_accounts_provider_check CHECK (((provider)::text = ANY ((ARRAY['google_drive'::character varying, 'onedrive'::character varying, 'microsoft_oauth'::character varying, 'google_oauth'::character varying, 'resend'::character varying])::text[]))),
    CONSTRAINT integration_accounts_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'expired'::character varying, 'revoked'::character varying, 'error'::character varying])::text[])))
);

ALTER TABLE ONLY public.integration_accounts FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN integration_accounts.secret_reference; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.integration_accounts.secret_reference IS 'Referencia al secret manager. NUNCA el token en claro.';


--
-- Name: legal_articles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_articles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    norm_version_id uuid NOT NULL,
    parent_article_id uuid,
    external_article_id character varying(120),
    article_type character varying(32) DEFAULT 'article'::character varying NOT NULL,
    article_number character varying(40) NOT NULL,
    heading text,
    content text NOT NULL,
    display_order integer NOT NULL,
    effective_from date,
    effective_to date,
    structured_content jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT legal_articles_article_type_check CHECK (((article_type)::text = ANY ((ARRAY['article'::character varying, 'transitory'::character varying, 'paragraph'::character varying, 'subsection'::character varying, 'numeral'::character varying, 'letter'::character varying])::text[])))
);


--
-- Name: TABLE legal_articles; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.legal_articles IS 'El articulo cuelga de una VERSION, no de la norma: el texto legal cambia y una auditoria pregunta bajo que texto se evaluo en una fecha dada.';


--
-- Name: legal_norm_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_norm_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    norm_id uuid NOT NULL,
    external_version_id character varying(100),
    version_label character varying(160),
    valid_from date NOT NULL,
    valid_to date,
    is_current boolean DEFAULT false NOT NULL,
    content_hash character(64) NOT NULL,
    full_text text,
    xml_payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    change_summary text,
    source_retrieved_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_norm_versions_vigencia CHECK (((valid_to IS NULL) OR (valid_to >= valid_from)))
);


--
-- Name: legal_norms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_norms (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    country_id smallint NOT NULL,
    source_id smallint NOT NULL,
    external_norm_id character varying(80),
    norm_type character varying(80) NOT NULL,
    norm_number character varying(60),
    title text NOT NULL,
    issuing_body character varying(240),
    publication_date date,
    promulgation_date date,
    effective_from date,
    repeal_date date,
    status character varying(32) DEFAULT 'desconocida'::character varying NOT NULL,
    official_url character varying(700),
    subjects text[] DEFAULT '{}'::text[] NOT NULL,
    source_payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    last_source_sync_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT legal_norms_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'vigente'::character varying, 'parcialmente_vigente'::character varying, 'derogada'::character varying, 'desconocida'::character varying])::text[])))
);


--
-- Name: TABLE legal_norms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.legal_norms IS 'Catalogo global: sin tenant_id a proposito. La norma es la misma para todos los tenants; lo que se registra por empresa es la aplicabilidad y el cumplimiento.';


--
-- Name: legal_relations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_relations (
    id bigint NOT NULL,
    source_norm_id uuid NOT NULL,
    source_article_id uuid,
    target_norm_id uuid NOT NULL,
    target_article_id uuid,
    relation_type character varying(40) NOT NULL,
    effective_date date,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT legal_relations_relation_type_check CHECK (((relation_type)::text = ANY ((ARRAY['modifica'::character varying, 'deroga'::character varying, 'reglamenta'::character varying, 'concordancia'::character varying, 'referencia'::character varying, 'refundido'::character varying])::text[])))
);


--
-- Name: legal_relations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.legal_relations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: legal_relations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.legal_relations_id_seq OWNED BY public.legal_relations.id;


--
-- Name: legal_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_sources (
    id smallint NOT NULL,
    country_id smallint NOT NULL,
    code character varying(40) NOT NULL,
    name character varying(160) NOT NULL,
    base_url character varying(500),
    connector_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    active boolean DEFAULT true NOT NULL
);


--
-- Name: legal_sources_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.legal_sources_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: legal_sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.legal_sources_id_seq OWNED BY public.legal_sources.id;


--
-- Name: matrix_norms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.matrix_norms (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    matrix_id uuid NOT NULL,
    norm_id uuid NOT NULL,
    selected_version_id uuid NOT NULL,
    sector_id smallint,
    applicability character varying(28) DEFAULT 'pending_analysis'::character varying NOT NULL,
    applicability_reason text,
    owner_user_id uuid,
    review_frequency character varying(24) DEFAULT 'annual'::character varying NOT NULL,
    next_review_date date,
    snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT matrix_norms_applicability_check CHECK (((applicability)::text = ANY ((ARRAY['applicable'::character varying, 'not_applicable'::character varying, 'pending_analysis'::character varying])::text[]))),
    CONSTRAINT matrix_norms_review_frequency_check CHECK (((review_frequency)::text = ANY ((ARRAY['annual'::character varying, 'semiannual'::character varying, 'quarterly'::character varying, 'event_based'::character varying])::text[])))
);

ALTER TABLE ONLY public.matrix_norms FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN matrix_norms.selected_version_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.matrix_norms.selected_version_id IS 'Version congelada usada para evaluar. Sin esto no se puede reconstruir una evaluacion pasada.';


--
-- Name: nonconformities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nonconformities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid,
    audit_item_id uuid,
    article_compliance_id uuid,
    code character varying(60) NOT NULL,
    title character varying(240) NOT NULL,
    description text NOT NULL,
    severity character varying(16) NOT NULL,
    status character varying(24) DEFAULT 'open'::character varying NOT NULL,
    record_type character varying(24),
    detection_origin character varying(24),
    root_cause_answers jsonb DEFAULT '[]'::jsonb NOT NULL,
    improvement_stages jsonb DEFAULT '{}'::jsonb NOT NULL,
    detected_at timestamp with time zone DEFAULT now() NOT NULL,
    detected_by uuid,
    owner_user_id uuid,
    due_date date,
    closed_at timestamp with time zone,
    closure_notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_nonconformities_cierre CHECK ((((status)::text = 'closed'::text) = (closed_at IS NOT NULL))),
    CONSTRAINT nonconformities_detection_origin_check CHECK (((detection_origin IS NULL) OR ((detection_origin)::text = ANY ((ARRAY['interna'::character varying, 'externa'::character varying, 'analisis_foda'::character varying, 'auditoria_interna'::character varying, 'auditoria_externa'::character varying])::text[])))),
    CONSTRAINT nonconformities_record_type_check CHECK (((record_type IS NULL) OR ((record_type)::text = ANY ((ARRAY['salida_no_conforme'::character varying, 'no_conformidad'::character varying, 'riesgo'::character varying, 'oportunidad'::character varying, 'reclamo'::character varying])::text[])))),
    CONSTRAINT nonconformities_severity_check CHECK (((severity)::text = ANY ((ARRAY['minor'::character varying, 'major'::character varying, 'critical'::character varying])::text[]))),
    CONSTRAINT nonconformities_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'analysis'::character varying, 'action_plan'::character varying, 'verification'::character varying, 'closed'::character varying, 'rejected'::character varying])::text[])))
);

ALTER TABLE ONLY public.nonconformities FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN nonconformities.record_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.nonconformities.record_type IS 'Tipo de registro de mejora (borrador v1.8 RF-96). El frontend ya lo usa para el flujo corto.';


--
-- Name: COLUMN nonconformities.improvement_stages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.nonconformities.improvement_stages IS 'Etapas del tratamiento (RF-97). JSONB de forma provisoria: el modelado relacional depende de la decision abierta sobre donde viven las etapas.';


--
-- Name: CONSTRAINT ck_nonconformities_cierre ON nonconformities; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON CONSTRAINT ck_nonconformities_cierre ON public.nonconformities IS 'RF-49: un hallazgo cerrado tiene fecha de cierre, y solo un cerrado la tiene.';


--
-- Name: norm_sectors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.norm_sectors (
    norm_id uuid NOT NULL,
    sector_id smallint NOT NULL,
    article_id uuid,
    applicability_level character varying(24) DEFAULT 'directa'::character varying NOT NULL,
    rationale text,
    source character varying(20) DEFAULT 'analyst'::character varying NOT NULL,
    confidence numeric(5,4),
    CONSTRAINT norm_sectors_applicability_level_check CHECK (((applicability_level)::text = ANY ((ARRAY['directa'::character varying, 'indirecta'::character varying, 'referencial'::character varying])::text[]))),
    CONSTRAINT norm_sectors_confidence_check CHECK (((confidence IS NULL) OR ((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))),
    CONSTRAINT norm_sectors_source_check CHECK (((source)::text = ANY ((ARRAY['automatic'::character varying, 'analyst'::character varying, 'client'::character varying])::text[])))
);


--
-- Name: norm_sync_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.norm_sync_runs (
    id bigint NOT NULL,
    source_id smallint NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    status character varying(20) DEFAULT 'running'::character varying NOT NULL,
    request_parameters jsonb DEFAULT '{}'::jsonb NOT NULL,
    response_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    norms_created integer DEFAULT 0 NOT NULL,
    norms_updated integer DEFAULT 0 NOT NULL,
    versions_created integer DEFAULT 0 NOT NULL,
    error_detail text,
    CONSTRAINT norm_sync_runs_status_check CHECK (((status)::text = ANY ((ARRAY['running'::character varying, 'success'::character varying, 'partial'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: norm_sync_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.norm_sync_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: norm_sync_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.norm_sync_runs_id_seq OWNED BY public.norm_sync_runs.id;


--
-- Name: notification_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    event_type character varying(60) NOT NULL,
    channel character varying(20) NOT NULL,
    lead_minutes integer DEFAULT 0 NOT NULL,
    recipient_rule jsonb DEFAULT '{}'::jsonb NOT NULL,
    template_code character varying(80) NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT notification_rules_channel_check CHECK (((channel)::text = ANY ((ARRAY['email'::character varying, 'in_app'::character varying])::text[])))
);

ALTER TABLE ONLY public.notification_rules FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN notification_rules.lead_minutes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.notification_rules.lead_minutes IS 'Anticipacion. Negativo = aviso posterior al vencimiento.';


--
-- Name: notification_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code character varying(80) NOT NULL,
    name character varying(180) NOT NULL,
    event_type character varying(60) NOT NULL,
    channel character varying(20) NOT NULL,
    locale character varying(12) DEFAULT 'es-CL'::character varying NOT NULL,
    subject_template character varying(400),
    body_template text NOT NULL,
    variables_schema jsonb DEFAULT '{}'::jsonb NOT NULL,
    version_no integer DEFAULT 1 NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT notification_templates_channel_check CHECK (((channel)::text = ANY ((ARRAY['email'::character varying, 'in_app'::character varying])::text[])))
);

ALTER TABLE ONLY public.notification_templates FORCE ROW LEVEL SECURITY;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    rule_id uuid,
    recipient_user_id uuid,
    channel character varying(20) NOT NULL,
    subject character varying(300),
    body text NOT NULL,
    status character varying(20) DEFAULT 'queued'::character varying NOT NULL,
    scheduled_at timestamp with time zone DEFAULT now() NOT NULL,
    sent_at timestamp with time zone,
    read_at timestamp with time zone,
    provider_message_id character varying(200),
    context jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT notifications_channel_check CHECK (((channel)::text = ANY ((ARRAY['email'::character varying, 'in_app'::character varying])::text[]))),
    CONSTRAINT notifications_status_check CHECK (((status)::text = ANY ((ARRAY['queued'::character varying, 'sent'::character varying, 'delivered'::character varying, 'failed'::character varying, 'read'::character varying, 'cancelled'::character varying])::text[])))
);

ALTER TABLE ONLY public.notifications FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN notifications.provider_message_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.notifications.provider_message_id IS 'ID de Resend (decision cerrada #18 de la v1.7).';


--
-- Name: obligation_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.obligation_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    country_id smallint NOT NULL,
    code character varying(60) NOT NULL,
    name character varying(200) NOT NULL,
    authority character varying(200),
    frequency_rule character varying(500),
    default_lead_days smallint DEFAULT 30 NOT NULL,
    template_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone
);


--
-- Name: COLUMN obligation_templates.frequency_rule; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.obligation_templates.frequency_rule IS 'Compatible con RRULE.';


--
-- Name: obligations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.obligations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    template_id uuid,
    matrix_norm_id uuid,
    article_compliance_id uuid,
    facility_id uuid,
    code character varying(60) NOT NULL,
    title character varying(240) NOT NULL,
    period_start date,
    period_end date,
    due_at timestamp with time zone,
    status character varying(24) DEFAULT 'draft'::character varying NOT NULL,
    owner_user_id uuid,
    submitted_at timestamp with time zone,
    external_receipt character varying(160),
    data jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_obligations_periodo CHECK (((period_end IS NULL) OR (period_start IS NULL) OR (period_end >= period_start))),
    CONSTRAINT obligations_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'open'::character varying, 'in_progress'::character varying, 'submitted'::character varying, 'accepted'::character varying, 'rejected'::character varying, 'overdue'::character varying, 'closed'::character varying])::text[])))
);

ALTER TABLE ONLY public.obligations FORCE ROW LEVEL SECURITY;


--
-- Name: permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permissions (
    id smallint NOT NULL,
    code character varying(100) NOT NULL,
    module character varying(50) NOT NULL,
    description character varying(300) NOT NULL
);


--
-- Name: TABLE permissions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.permissions IS 'Catalogo global de permisos atomicos. Ej: legal_matrix.article.evaluate';


--
-- Name: permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.permissions_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.permissions_id_seq OWNED BY public.permissions.id;


--
-- Name: processes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.processes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    department_id uuid,
    parent_process_id uuid,
    code character varying(50) NOT NULL,
    name character varying(180) NOT NULL,
    process_type character varying(24) NOT NULL,
    description text,
    responsible_user_id uuid,
    inputs jsonb DEFAULT '[]'::jsonb NOT NULL,
    outputs jsonb DEFAULT '[]'::jsonb NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT processes_process_type_check CHECK (((process_type)::text = ANY ((ARRAY['strategic'::character varying, 'operational'::character varying, 'support'::character varying])::text[])))
);

ALTER TABLE ONLY public.processes FORCE ROW LEVEL SECURITY;


--
-- Name: regulated_equipment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.regulated_equipment (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid NOT NULL,
    name character varying(180) NOT NULL,
    equipment_type character varying(80) NOT NULL,
    brand character varying(120),
    model character varying(120),
    registration_authority character varying(40),
    registration_number character varying(80),
    registration_expires_at date,
    status character varying(20) DEFAULT 'operational'::character varying NOT NULL,
    technical_specs jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT regulated_equipment_registration_authority_check CHECK (((registration_authority IS NULL) OR ((registration_authority)::text = ANY ((ARRAY['SEC'::character varying, 'SISS'::character varying, 'SEREMI_SALUD'::character varying, 'DGA'::character varying, 'SMA'::character varying, 'OTRO'::character varying])::text[])))),
    CONSTRAINT regulated_equipment_status_check CHECK (((status)::text = ANY ((ARRAY['operational'::character varying, 'stopped'::character varying, 'decommissioned'::character varying])::text[])))
);

ALTER TABLE ONLY public.regulated_equipment FORCE ROW LEVEL SECURITY;


--
-- Name: risks_opportunities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.risks_opportunities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid,
    environmental_aspect_id uuid,
    action_plan_id uuid,
    code character varying(40) NOT NULL,
    entry_type character varying(16) NOT NULL,
    description text NOT NULL,
    origin character varying(32) NOT NULL,
    risk_level character varying(16) DEFAULT 'medium'::character varying NOT NULL,
    treatment character varying(20),
    status character varying(20) DEFAULT 'identified'::character varying NOT NULL,
    owner_user_id uuid,
    review_date date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_risks_origen_aspecto CHECK ((((origin)::text <> 'environmental_aspect'::text) OR (environmental_aspect_id IS NOT NULL))),
    CONSTRAINT risks_opportunities_entry_type_check CHECK (((entry_type)::text = ANY ((ARRAY['risk'::character varying, 'opportunity'::character varying])::text[]))),
    CONSTRAINT risks_opportunities_origin_check CHECK (((origin)::text = ANY ((ARRAY['environmental_aspect'::character varying, 'context'::character varying, 'climate_change'::character varying, 'compliance'::character varying, 'other'::character varying])::text[]))),
    CONSTRAINT risks_opportunities_risk_level_check CHECK (((risk_level)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'critical'::character varying])::text[]))),
    CONSTRAINT risks_opportunities_status_check CHECK (((status)::text = ANY ((ARRAY['identified'::character varying, 'in_treatment'::character varying, 'controlled'::character varying, 'closed'::character varying])::text[]))),
    CONSTRAINT risks_opportunities_treatment_check CHECK (((treatment IS NULL) OR ((treatment)::text = ANY ((ARRAY['mitigate'::character varying, 'avoid'::character varying, 'transfer'::character varying, 'accept'::character varying, 'exploit'::character varying])::text[]))))
);

ALTER TABLE ONLY public.risks_opportunities FORCE ROW LEVEL SECURITY;


--
-- Name: CONSTRAINT ck_risks_origen_aspecto ON risks_opportunities; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON CONSTRAINT ck_risks_origen_aspecto ON public.risks_opportunities IS 'Si el origen declarado es un aspecto ambiental, el aspecto tiene que estar referenciado. ISO 14001 deriva §6.1.4 de §6.1.2 y esa trazabilidad es lo que pide un auditor.';


--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_permissions (
    role_id uuid NOT NULL,
    permission_id smallint NOT NULL,
    granted boolean DEFAULT true NOT NULL
);


--
-- Name: COLUMN role_permissions.granted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.role_permissions.granted IS 'false = denegacion explicita, gana sobre cualquier concesion.';


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code character varying(60) NOT NULL,
    name character varying(120) NOT NULL,
    is_system boolean DEFAULT false NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone
);

ALTER TABLE ONLY public.roles FORCE ROW LEVEL SECURITY;


--
-- Name: sectors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sectors (
    id smallint NOT NULL,
    country_id smallint,
    parent_id smallint,
    code character varying(40) NOT NULL,
    name character varying(180) NOT NULL,
    description text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: COLUMN sectors.code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.sectors.code IS 'Codigo estable; puede mapear CIIU u otra clasificacion.';


--
-- Name: sectors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sectors_id_seq
    AS smallint
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sectors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sectors_id_seq OWNED BY public.sectors.id;


--
-- Name: support_ticket_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.support_ticket_messages (
    id bigint NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_id uuid NOT NULL,
    author_user_id uuid,
    author_guest_email public.citext,
    message_type character varying(24) DEFAULT 'comment'::character varying NOT NULL,
    body text NOT NULL,
    is_internal boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT support_ticket_messages_message_type_check CHECK (((message_type)::text = ANY ((ARRAY['comment'::character varying, 'internal_note'::character varying, 'status_change'::character varying, 'attachment'::character varying])::text[])))
);

ALTER TABLE ONLY public.support_ticket_messages FORCE ROW LEVEL SECURITY;


--
-- Name: support_ticket_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.support_ticket_messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: support_ticket_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.support_ticket_messages_id_seq OWNED BY public.support_ticket_messages.id;


--
-- Name: support_tickets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.support_tickets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    ticket_number character varying(40) NOT NULL,
    created_by_user_id uuid,
    guest_name character varying(180),
    guest_email public.citext,
    category character varying(32) NOT NULL,
    subject character varying(240) NOT NULL,
    description text NOT NULL,
    priority character varying(16) DEFAULT 'medium'::character varying NOT NULL,
    status character varying(24) DEFAULT 'open'::character varying NOT NULL,
    assigned_to uuid,
    related_entity_type character varying(40),
    related_entity_id uuid,
    resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_support_tickets_autor CHECK (((created_by_user_id IS NOT NULL) OR (guest_email IS NOT NULL))),
    CONSTRAINT support_tickets_category_check CHECK (((category)::text = ANY ((ARRAY['technical'::character varying, 'access'::character varying, 'data'::character varying, 'legal'::character varying, 'billing'::character varying, 'other'::character varying])::text[]))),
    CONSTRAINT support_tickets_priority_check CHECK (((priority)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'critical'::character varying])::text[]))),
    CONSTRAINT support_tickets_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'assigned'::character varying, 'waiting_user'::character varying, 'in_progress'::character varying, 'resolved'::character varying, 'closed'::character varying])::text[])))
);

ALTER TABLE ONLY public.support_tickets FORCE ROW LEVEL SECURITY;


--
-- Name: CONSTRAINT ck_support_tickets_autor ON support_tickets; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON CONSTRAINT ck_support_tickets_autor ON public.support_tickets IS 'Un ticket lo abre un usuario registrado o un invitado con correo (RF-02).';


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    obligation_id uuid,
    parent_task_id uuid,
    task_type character varying(32) DEFAULT 'task'::character varying NOT NULL,
    title character varying(240) NOT NULL,
    description text,
    status character varying(24) DEFAULT 'todo'::character varying NOT NULL,
    priority character varying(16) DEFAULT 'medium'::character varying NOT NULL,
    start_at timestamp with time zone,
    due_at timestamp with time zone,
    completed_at timestamp with time zone,
    assignee_user_id uuid,
    department_id uuid,
    progress_percent numeric(5,2) DEFAULT 0 NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT tasks_priority_check CHECK (((priority)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'critical'::character varying])::text[]))),
    CONSTRAINT tasks_progress_percent_check CHECK (((progress_percent >= (0)::numeric) AND (progress_percent <= (100)::numeric))),
    CONSTRAINT tasks_status_check CHECK (((status)::text = ANY ((ARRAY['todo'::character varying, 'in_progress'::character varying, 'blocked'::character varying, 'review'::character varying, 'done'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT tasks_task_type_check CHECK (((task_type)::text = ANY ((ARRAY['task'::character varying, 'milestone'::character varying, 'approval'::character varying, 'evidence_request'::character varying, 'support_ticket'::character varying])::text[])))
);

ALTER TABLE ONLY public.tasks FORCE ROW LEVEL SECURITY;


--
-- Name: TABLE tasks; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.tasks IS 'Ticket unico de Calendario, Gantt y Obligaciones (RF-28). No se duplica.';


--
-- Name: tenant_legal_matrices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_legal_matrices (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(180) NOT NULL,
    period_year smallint NOT NULL,
    facility_id uuid,
    status character varying(24) DEFAULT 'draft'::character varying NOT NULL,
    version_no integer DEFAULT 1 NOT NULL,
    approved_at timestamp with time zone,
    approved_by uuid,
    scope_definition jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_matrices_aprobacion CHECK ((((status)::text = 'approved'::text) = (approved_at IS NOT NULL))),
    CONSTRAINT tenant_legal_matrices_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'in_review'::character varying, 'approved'::character varying, 'archived'::character varying])::text[])))
);

ALTER TABLE ONLY public.tenant_legal_matrices FORCE ROW LEVEL SECURITY;


--
-- Name: CONSTRAINT ck_matrices_aprobacion ON tenant_legal_matrices; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON CONSTRAINT ck_matrices_aprobacion ON public.tenant_legal_matrices IS 'Una matriz aprobada tiene fecha de aprobacion, y solo una aprobada la tiene.';


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    country_id smallint NOT NULL,
    parent_tenant_id uuid,
    tenant_type character varying(24) DEFAULT 'company'::character varying NOT NULL,
    rut_tax_id character varying(32) NOT NULL,
    legal_name character varying(240) NOT NULL,
    trade_name character varying(180),
    business_activity character varying(300),
    status character varying(24) DEFAULT 'trial'::character varying NOT NULL,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT tenants_status_check CHECK (((status)::text = ANY ((ARRAY['trial'::character varying, 'active'::character varying, 'suspended'::character varying, 'closed'::character varying])::text[]))),
    CONSTRAINT tenants_tenant_type_check CHECK (((tenant_type)::text = ANY ((ARRAY['company'::character varying, 'manager'::character varying, 'managed_client'::character varying, 'platform'::character varying])::text[])))
);


--
-- Name: COLUMN tenants.parent_tenant_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tenants.parent_tenant_id IS 'Gestor padre cuando opera como sub-tenant (RF-65).';


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    user_id uuid NOT NULL,
    role_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid,
    department_id uuid,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    CONSTRAINT ck_user_roles_vigencia CHECK (((valid_to IS NULL) OR (valid_to > valid_from)))
);

ALTER TABLE ONLY public.user_roles FORCE ROW LEVEL SECURITY;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    department_id uuid,
    rut_tax_id character varying(32),
    email public.citext NOT NULL,
    full_name character varying(180) NOT NULL,
    user_type character varying(32) NOT NULL,
    status character varying(24) DEFAULT 'invited'::character varying NOT NULL,
    password_hash character varying(255),
    preferences jsonb DEFAULT '{}'::jsonb NOT NULL,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid,
    deleted_at timestamp with time zone,
    CONSTRAINT users_status_check CHECK (((status)::text = ANY ((ARRAY['invited'::character varying, 'active'::character varying, 'blocked'::character varying, 'disabled'::character varying])::text[]))),
    CONSTRAINT users_user_type_check CHECK (((user_type)::text = ANY ((ARRAY['platform_admin'::character varying, 'tenant_admin'::character varying, 'internal'::character varying, 'guest'::character varying, 'manager'::character varying])::text[])))
);

ALTER TABLE ONLY public.users FORCE ROW LEVEL SECURITY;


--
-- Name: COLUMN users.password_hash; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.password_hash IS 'Argon2id o bcrypt. Nunca texto plano (RNF-05).';


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: chatbot_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatbot_messages ALTER COLUMN id SET DEFAULT nextval('public.chatbot_messages_id_seq'::regclass);


--
-- Name: countries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.countries ALTER COLUMN id SET DEFAULT nextval('public.countries_id_seq'::regclass);


--
-- Name: entity_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_documents ALTER COLUMN id SET DEFAULT nextval('public.entity_documents_id_seq'::regclass);


--
-- Name: entity_status_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_status_history ALTER COLUMN id SET DEFAULT nextval('public.entity_status_history_id_seq'::regclass);


--
-- Name: legal_relations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_relations ALTER COLUMN id SET DEFAULT nextval('public.legal_relations_id_seq'::regclass);


--
-- Name: legal_sources id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_sources ALTER COLUMN id SET DEFAULT nextval('public.legal_sources_id_seq'::regclass);


--
-- Name: norm_sync_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.norm_sync_runs ALTER COLUMN id SET DEFAULT nextval('public.norm_sync_runs_id_seq'::regclass);


--
-- Name: permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions ALTER COLUMN id SET DEFAULT nextval('public.permissions_id_seq'::regclass);


--
-- Name: sectors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors ALTER COLUMN id SET DEFAULT nextval('public.sectors_id_seq'::regclass);


--
-- Name: support_ticket_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_ticket_messages ALTER COLUMN id SET DEFAULT nextval('public.support_ticket_messages_id_seq'::regclass);


--
-- Data for Name: action_plans; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.action_plans (id, tenant_id, article_compliance_id, nonconformity_id, title, root_cause, objective, status, priority, owner_user_id, target_date, verified_at, verified_by, success_criteria, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000041-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	\N	a0000040-0000-0000-0000-000000000001	Actualizar registros de mantenimiento de filtros	Falta de supervisión del registro digital de mantenimiento preventivo	Completar los registros pendientes de abril a junio y digitalizar en sistema.	in_progress	high	d0000000-0000-0000-0000-000000000003	2026-08-15	\N	\N	{}	2026-08-03 21:51:48.403447+00	\N	2026-08-03 21:51:48.403447+00	\N	\N
a0000041-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	\N	a0000040-0000-0000-0000-000000000001	Capacitación en registro digital de mantenimiento	Personal de operaciones no capacitado en el módulo digital	Capacitar al equipo de operaciones en el uso del módulo de mantenimiento digital.	draft	medium	d0000000-0000-0000-0000-000000000002	2026-09-01	\N	\N	{}	2026-08-03 21:51:48.403447+00	\N	2026-08-03 21:51:48.403447+00	\N	\N
\.


--
-- Data for Name: article_compliance; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.article_compliance (id, tenant_id, matrix_norm_id, article_id, facility_id, department_id, compliance_status, compliance_method, assessment_reason, risk_level, responsible_user_id, assessed_at, assessed_by, approved_at, approved_by, attributes, row_version, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: audit_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_items (id, tenant_id, audit_id, article_compliance_id, sequence, question, result, notes, auditor_user_id, assessed_at, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000031-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	a0000030-0000-0000-0000-000000000001	\N	1	¿Se han identificado los aspectos ambientales significativos? (ISO 14001:2015 §6.1.2)	conform	Matriz de aspectos actualizada, registros de capacitación al día	\N	\N	2026-08-03 21:51:48.398678+00	\N	2026-08-03 21:51:48.398678+00	\N	\N
a0000031-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	a0000030-0000-0000-0000-000000000001	\N	2	¿Se mantienen los controles operacionales de emisiones? (ISO 14001:2015 §8.1)	nonconform	Registros de mantenimiento de filtros sin actualizar desde abril	\N	\N	2026-08-03 21:51:48.398678+00	\N	2026-08-03 21:51:48.398678+00	\N	\N
a0000031-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	a0000030-0000-0000-0000-000000000001	\N	3	¿El almacenamiento temporal de RESPEL cumple con DS 148 Art. 25?	observation	Señalética de bodega RESPEL parcialmente ilegible	\N	\N	2026-08-03 21:51:48.398678+00	\N	2026-08-03 21:51:48.398678+00	\N	\N
\.


--
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_log (id, tenant_id, occurred_at, actor_user_id, action, entity_type, entity_id, request_id, ip_address, reason, before_data, after_data, metadata) FROM stdin;
\.


--
-- Data for Name: audit_participants; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_participants (audit_id, user_id, tenant_id, external_name, external_email, participant_role, attendance_status, notes, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000030-0000-0000-0000-000000000001	d0000000-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	\N	\N	lead_auditor	invited	\N	2026-08-03 21:51:48.396218+00	\N	2026-08-03 21:51:48.396218+00	\N	\N
a0000030-0000-0000-0000-000000000001	d0000000-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	\N	\N	auditee	invited	\N	2026-08-03 21:51:48.396218+00	\N	2026-08-03 21:51:48.396218+00	\N	\N
a0000030-0000-0000-0000-000000000001	d0000000-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	\N	\N	auditee	invited	\N	2026-08-03 21:51:48.396218+00	\N	2026-08-03 21:51:48.396218+00	\N	\N
\.


--
-- Data for Name: audits; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audits (id, tenant_id, facility_id, code, title, audit_type, scope, lead_auditor_user_id, planned_start, planned_end, actual_start, actual_end, status, criteria, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000030-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	AUD-2026-001	Auditoría Interna SGA Q2 2026	internal	Revisión de cumplimiento del SGA ISO 14001 en Planta Calama	d0000000-0000-0000-0000-000000000002	2026-06-01 00:00:00+00	2026-06-05 00:00:00+00	\N	\N	closed	{}	2026-08-03 21:51:48.394278+00	\N	2026-08-03 21:51:48.394278+00	\N	\N
a0000030-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000002	AUD-2026-002	Fiscalización SMA - Faena Antofagasta	regulatory	Fiscalización programada de la SMA a la faena minera	\N	2026-09-15 00:00:00+00	2026-09-17 00:00:00+00	\N	\N	planned	{}	2026-08-03 21:51:48.394278+00	\N	2026-08-03 21:51:48.394278+00	\N	\N
\.


--
-- Data for Name: chatbot_conversations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.chatbot_conversations (id, tenant_id, user_id, title, scope, facility_id, status, context_snapshot, last_message_at, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: chatbot_messages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.chatbot_messages (id, tenant_id, conversation_id, role, content, cited_norm_ids, citations, model_name, token_usage, feedback, created_at) FROM stdin;
\.


--
-- Data for Name: contracts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.contracts (id, tenant_id, manager_tenant_id, client_tenant_id, contract_number, title, status, start_date, end_date, scope, terms_snapshot, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000080-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	ECOG-2026-001	Asesoría en cumplimiento ambiental Minera Andes	active	2026-01-01	2026-12-31	{"services": ["Matriz legal", "Auditoría interna", "Reportes RETC", "Capacitación"]}	{}	2026-08-03 21:51:48.420556+00	\N	2026-08-03 21:51:48.420556+00	\N	\N
\.


--
-- Data for Name: countries; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.countries (id, iso2, iso3, name, default_timezone, metadata) FROM stdin;
1	CL	CHL	Chile	America/Santiago	{}
2	PE	PER	Perú	America/Lima	{}
3	CO	COL	Colombia	America/Bogota	{}
\.


--
-- Data for Name: declaration_submissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.declaration_submissions (id, tenant_id, obligation_id, template_id, facility_id, period_label, version_no, status, prepared_by, reviewed_by, submitted_by, submitted_at, external_folio, submission_data, validation_result, receipt_document_id, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: declaration_templates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.declaration_templates (id, country_id, system_code, name, version, valid_from, valid_to, schema_definition, workbook_structure, source_document_id, active, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: departments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.departments (id, tenant_id, facility_id, parent_department_id, code, name, active, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
c0000000-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	\N	DEP-MED	Medio Ambiente	t	2026-08-03 21:51:48.355466+00	\N	2026-08-03 21:51:48.355466+00	\N	\N
c0000000-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	\N	DEP-OPS	Operaciones	t	2026-08-03 21:51:48.355466+00	\N	2026-08-03 21:51:48.355466+00	\N	\N
c0000000-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000003	\N	DEP-LEG	Legal y Cumplimiento	t	2026-08-03 21:51:48.355466+00	\N	2026-08-03 21:51:48.355466+00	\N	\N
c0000000-0000-0000-0000-000000000004	a0000000-0000-0000-0000-000000000002	b0000000-0000-0000-0000-000000000004	\N	DEP-CONS	Consultoría	t	2026-08-03 21:51:48.355466+00	\N	2026-08-03 21:51:48.355466+00	\N	\N
\.


--
-- Data for Name: document_versions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.document_versions (id, tenant_id, document_id, version_no, storage_provider, storage_key, file_name, mime_type, size_bytes, checksum_sha256, source, version_metadata, created_at, created_by) FROM stdin;
\.


--
-- Data for Name: documents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.documents (id, tenant_id, document_type, current_version_id, title, classification, status, tags, metadata, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: entity_documents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.entity_documents (id, tenant_id, document_id, entity_type, entity_id, purpose, is_required, valid_from, valid_to, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: entity_status_history; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.entity_status_history (id, tenant_id, entity_type, entity_id, from_status, to_status, changed_at, changed_by, reason, metadata) FROM stdin;
\.


--
-- Data for Name: environmental_aspects; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.environmental_aspects (id, tenant_id, facility_id, process_id, article_compliance_id, activity, aspect, impact_type, operating_condition, severity_score, frequency_score, legal_score, total_score, significance, responsible_user_id, controls, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000060-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	a0000050-0000-0000-0000-000000000001	\N	Chancado de mineral	Emisión de material particulado (MP10)	Contaminación atmosférica	normal	7	8	3	18	non_compliant	\N	[{"measure": "Filtros de manga"}, {"measure": "Supresión con agua"}, {"measure": "Monitoreo continuo"}]	2026-08-03 21:51:48.411031+00	\N	2026-08-03 21:51:48.411031+00	\N	\N
a0000060-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	a0000050-0000-0000-0000-000000000004	\N	Gestión de residuos	Generación de residuos peligrosos	Contaminación de suelo y agua	normal	8	6	6	20	partial	\N	[{"measure": "Bodega RESPEL certificada"}, {"measure": "Manifiestos SIDREP"}, {"measure": "Capacitación anual"}]	2026-08-03 21:51:48.411031+00	\N	2026-08-03 21:51:48.411031+00	\N	\N
a0000060-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	a0000050-0000-0000-0000-000000000002	\N	Flotación	Consumo de agua industrial	Agotamiento del recurso hídrico	normal	5	7	3	15	compliant	\N	[{"measure": "Recirculación de agua"}, {"measure": "Medidores de flujo"}]	2026-08-03 21:51:48.411031+00	\N	2026-08-03 21:51:48.411031+00	\N	\N
\.


--
-- Data for Name: equipment_operators; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.equipment_operators (equipment_id, user_id, tenant_id, certification_class, certification_number, certification_expires_at, is_primary, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000070-0000-0000-0000-000000000001	d0000000-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	Operador Clase B	CERT-2024-1234	2027-03-15	t	2026-08-03 21:51:48.418353+00	\N	2026-08-03 21:51:48.418353+00	\N	\N
a0000070-0000-0000-0000-000000000002	d0000000-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	Operador Clase C	CERT-2024-5678	2027-01-20	t	2026-08-03 21:51:48.418353+00	\N	2026-08-03 21:51:48.418353+00	\N	\N
\.


--
-- Data for Name: facilities; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.facilities (id, tenant_id, code, name, facility_type, address, region_code, commune_code, latitude, longitude, environmental_identifiers, active, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
b0000000-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	PLT-CALA	Planta Calama	planta_procesamiento	Ruta 24, Km 35, Calama	II	02101	-22.456789	-68.924561	{"rca": "RCA-045/2018", "seia_id": "2018050001"}	t	2026-08-03 21:51:48.352409+00	\N	2026-08-03 21:51:48.352409+00	\N	\N
b0000000-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	MIN-ANTO	Faena Antofagasta	faena_minera	Sector Sierra Gorda, Antofagasta	II	02101	-23.654321	-69.123456	{"rca": "RCA-112/2020", "seia_id": "2020030045"}	t	2026-08-03 21:51:48.352409+00	\N	2026-08-03 21:51:48.352409+00	\N	\N
b0000000-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	OFI-SCL	Oficina Santiago	oficina_administrativa	Av. Apoquindo 4500, Las Condes, Santiago	RM	13114	-33.417500	-70.605000	{}	t	2026-08-03 21:51:48.352409+00	\N	2026-08-03 21:51:48.352409+00	\N	\N
b0000000-0000-0000-0000-000000000004	a0000000-0000-0000-0000-000000000002	OFI-ECOG	Oficina Central EcoGestión	oficina_administrativa	Av. Providencia 1208, Providencia, Santiago	RM	13123	-33.425000	-70.610000	{}	t	2026-08-03 21:51:48.354257+00	\N	2026-08-03 21:51:48.354257+00	\N	\N
\.


--
-- Data for Name: facility_norm_assignments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.facility_norm_assignments (id, tenant_id, facility_id, norm_id, assigned_version_id, assignment_status, applicability_reason, assigned_by, assigned_at, source, metadata, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000012-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	f1000000-0000-0000-0000-000000000004	\N	assigned	\N	d0000000-0000-0000-0000-000000000002	2026-08-03 21:51:48.386674+00	manual	{}	2026-08-03 21:51:48.386674+00	\N	2026-08-03 21:51:48.386674+00	\N	\N
a0000012-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	f1000000-0000-0000-0000-000000000006	\N	assigned	\N	d0000000-0000-0000-0000-000000000002	2026-08-03 21:51:48.386674+00	manual	{}	2026-08-03 21:51:48.386674+00	\N	2026-08-03 21:51:48.386674+00	\N	\N
a0000012-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000002	f1000000-0000-0000-0000-000000000007	\N	assigned	\N	d0000000-0000-0000-0000-000000000002	2026-08-03 21:51:48.386674+00	manual	{}	2026-08-03 21:51:48.386674+00	\N	2026-08-03 21:51:48.386674+00	\N	\N
\.


--
-- Data for Name: facility_processes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.facility_processes (facility_id, process_id, tenant_id, is_primary, scope_notes, active_from, active_to, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
b0000000-0000-0000-0000-000000000001	a0000050-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	t	Línea principal de chancado	\N	\N	2026-08-03 21:51:48.40842+00	\N	2026-08-03 21:51:48.40842+00	\N	\N
b0000000-0000-0000-0000-000000000001	a0000050-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	t	Circuito de flotación Cu-Mo	\N	\N	2026-08-03 21:51:48.40842+00	\N	2026-08-03 21:51:48.40842+00	\N	\N
b0000000-0000-0000-0000-000000000001	a0000050-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	f	\N	\N	\N	2026-08-03 21:51:48.40842+00	\N	2026-08-03 21:51:48.40842+00	\N	\N
b0000000-0000-0000-0000-000000000001	a0000050-0000-0000-0000-000000000004	a0000000-0000-0000-0000-000000000001	f	\N	\N	\N	2026-08-03 21:51:48.40842+00	\N	2026-08-03 21:51:48.40842+00	\N	\N
\.


--
-- Data for Name: integration_accounts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.integration_accounts (id, tenant_id, provider, external_account_id, display_name, status, scopes, secret_reference, metadata, last_sync_at, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: legal_articles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.legal_articles (id, norm_version_id, parent_article_id, external_article_id, article_type, article_number, heading, content, display_order, effective_from, effective_to, structured_content, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
f3000000-0000-0000-0000-000000000001	f2000000-0000-0000-0000-000000000001	\N	\N	article	10	Proyectos que requieren EIA	Los proyectos o actividades susceptibles de causar impacto ambiental, en cualesquiera de sus fases, que deberán someterse al sistema de evaluación de impacto ambiental...	1	\N	\N	{}	2026-08-03 21:51:48.377267+00	\N	2026-08-03 21:51:48.377267+00	\N	\N
f3000000-0000-0000-0000-000000000002	f2000000-0000-0000-0000-000000000001	\N	\N	article	11	Circunstancias que requieren EIA	Los proyectos o actividades enumerados en el artículo precedente requerirán la elaboración de un Estudio de Impacto Ambiental...	2	\N	\N	{}	2026-08-03 21:51:48.377267+00	\N	2026-08-03 21:51:48.377267+00	\N	\N
f3000000-0000-0000-0000-000000000003	f2000000-0000-0000-0000-000000000002	\N	\N	article	5	Clasificación de residuos peligrosos	Se considerará residuo peligroso aquel que presente o pueda presentar riesgo para la salud pública y/o efectos adversos al medio ambiente...	1	\N	\N	{}	2026-08-03 21:51:48.377267+00	\N	2026-08-03 21:51:48.377267+00	\N	\N
f3000000-0000-0000-0000-000000000004	f2000000-0000-0000-0000-000000000002	\N	\N	article	25	Declaración de residuos peligrosos	Todo generador de residuos peligrosos deberá presentar una Declaración ante la Autoridad Sanitaria...	2	\N	\N	{}	2026-08-03 21:51:48.377267+00	\N	2026-08-03 21:51:48.377267+00	\N	\N
\.


--
-- Data for Name: legal_norm_versions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.legal_norm_versions (id, norm_id, external_version_id, version_label, valid_from, valid_to, is_current, content_hash, full_text, xml_payload, change_summary, source_retrieved_at, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
f2000000-0000-0000-0000-000000000001	f1000000-0000-0000-0000-000000000001	\N	Texto refundido 2023	2023-03-01	\N	t	sha256_placeholder_001                                          	\N	{}	Incorpora modificaciones de Ley 21.595	2026-08-03 21:51:48.375325+00	2026-08-03 21:51:48.375325+00	\N	2026-08-03 21:51:48.375325+00	\N	\N
f2000000-0000-0000-0000-000000000002	f1000000-0000-0000-0000-000000000004	\N	Texto original	2004-06-16	\N	t	sha256_placeholder_002                                          	\N	{}	Texto original del DS 148	2026-08-03 21:51:48.375325+00	2026-08-03 21:51:48.375325+00	\N	2026-08-03 21:51:48.375325+00	\N	\N
f2000000-0000-0000-0000-000000000003	f1000000-0000-0000-0000-000000000005	\N	Texto original	2016-06-01	\N	t	sha256_placeholder_003                                          	\N	{}	Texto original Ley REP	2026-08-03 21:51:48.375325+00	2026-08-03 21:51:48.375325+00	\N	2026-08-03 21:51:48.375325+00	\N	\N
\.


--
-- Data for Name: legal_norms; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.legal_norms (id, country_id, source_id, external_norm_id, norm_type, norm_number, title, issuing_body, publication_date, promulgation_date, effective_from, repeal_date, status, official_url, subjects, source_payload, last_source_sync_at, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
f1000000-0000-0000-0000-000000000001	1	1	\N	ley	19300	Ley sobre Bases Generales del Medio Ambiente	\N	1994-03-09	\N	\N	\N	vigente	\N	{"medio ambiente","protección ambiental",SEIA}	{}	\N	2026-08-03 21:51:48.372457+00	\N	2026-08-03 21:51:48.372457+00	\N	\N
f1000000-0000-0000-0000-000000000002	1	1	\N	decreto_supremo	40/2012	Reglamento del Sistema de Evaluación de Impacto Ambiental	\N	2013-12-30	\N	\N	\N	vigente	\N	{SEIA,"evaluación ambiental",EIA,DIA}	{}	\N	2026-08-03 21:51:48.372457+00	\N	2026-08-03 21:51:48.372457+00	\N	\N
f1000000-0000-0000-0000-000000000003	1	1	\N	decreto_supremo	13/2011	Norma de Emisión para Centrales Termoeléctricas	\N	2011-06-23	\N	\N	\N	vigente	\N	{"emisiones atmosféricas",termoeléctricas,"calidad del aire"}	{}	\N	2026-08-03 21:51:48.372457+00	\N	2026-08-03 21:51:48.372457+00	\N	\N
f1000000-0000-0000-0000-000000000004	1	1	\N	decreto_supremo	148/2003	Reglamento Sanitario sobre Manejo de Residuos Peligrosos	\N	2004-06-16	\N	\N	\N	vigente	\N	{"residuos peligrosos",RESPEL,SIDREP}	{}	\N	2026-08-03 21:51:48.372457+00	\N	2026-08-03 21:51:48.372457+00	\N	\N
f1000000-0000-0000-0000-000000000005	1	1	\N	ley	20920	Ley Marco para la Gestión de Residuos, la Responsabilidad Extendida del Productor y Fomento al Reciclaje (Ley REP)	\N	2016-06-01	\N	\N	\N	vigente	\N	{REP,reciclaje,residuos,"responsabilidad extendida"}	{}	\N	2026-08-03 21:51:48.372457+00	\N	2026-08-03 21:51:48.372457+00	\N	\N
f1000000-0000-0000-0000-000000000006	1	2	\N	decreto_supremo	90/2000	Norma de Emisión para la Regulación de Contaminantes Asociados a las Descargas de Residuos Líquidos	\N	2001-03-07	\N	\N	\N	vigente	\N	{RILes,"aguas superficiales","descargas líquidas"}	{}	\N	2026-08-03 21:51:48.372457+00	\N	2026-08-03 21:51:48.372457+00	\N	\N
f1000000-0000-0000-0000-000000000007	1	1	\N	decreto_supremo	38/2011	Norma de Emisión de Ruidos	\N	2011-11-12	\N	\N	\N	vigente	\N	{ruido,"emisión sonora","contaminación acústica"}	{}	\N	2026-08-03 21:51:48.372457+00	\N	2026-08-03 21:51:48.372457+00	\N	\N
f1000000-0000-0000-0000-000000000008	1	3	\N	resolucion	RE-574/2019	Resolución que establece obligaciones de reporte al RETC	\N	2019-08-15	\N	\N	\N	vigente	\N	{RETC,reporte,emisiones,transferencias}	{}	\N	2026-08-03 21:51:48.372457+00	\N	2026-08-03 21:51:48.372457+00	\N	\N
\.


--
-- Data for Name: legal_relations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.legal_relations (id, source_norm_id, source_article_id, target_norm_id, target_article_id, relation_type, effective_date, metadata) FROM stdin;
\.


--
-- Data for Name: legal_sources; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.legal_sources (id, country_id, code, name, base_url, connector_config, active) FROM stdin;
1	1	BCN	Biblioteca del Congreso Nacional	https://www.bcn.cl/leychile	{}	t
2	1	SMA	Superintendencia del Medio Ambiente	https://www.sma.gob.cl	{}	t
3	1	RETC	Registro de Emisiones y Transferencias de Contaminantes	https://www.retc.cl	{}	t
\.


--
-- Data for Name: matrix_norms; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.matrix_norms (id, tenant_id, matrix_id, norm_id, selected_version_id, sector_id, applicability, applicability_reason, owner_user_id, review_frequency, next_review_date, snapshot, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000011-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	a0000010-0000-0000-0000-000000000001	f1000000-0000-0000-0000-000000000001	f2000000-0000-0000-0000-000000000001	\N	applicable	Aplica a todas las operaciones de la minera	\N	annual	\N	{}	2026-08-03 21:52:13.586623+00	\N	2026-08-03 21:52:13.586623+00	\N	\N
a0000011-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	a0000010-0000-0000-0000-000000000001	f1000000-0000-0000-0000-000000000004	f2000000-0000-0000-0000-000000000002	\N	applicable	Generación de residuos peligrosos en planta Calama	\N	semiannual	\N	{}	2026-08-03 21:52:13.586623+00	\N	2026-08-03 21:52:13.586623+00	\N	\N
a0000011-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	a0000010-0000-0000-0000-000000000001	f1000000-0000-0000-0000-000000000005	f2000000-0000-0000-0000-000000000003	\N	applicable	Responsabilidad extendida sobre neumáticos y aceites usados	\N	annual	\N	{}	2026-08-03 21:52:13.586623+00	\N	2026-08-03 21:52:13.586623+00	\N	\N
a0000011-0000-0000-0000-000000000004	a0000000-0000-0000-0000-000000000001	a0000010-0000-0000-0000-000000000001	f1000000-0000-0000-0000-000000000006	f2000000-0000-0000-0000-000000000001	\N	applicable	Descargas de riles en planta de procesamiento	\N	quarterly	\N	{}	2026-08-03 21:52:13.586623+00	\N	2026-08-03 21:52:13.586623+00	\N	\N
a0000011-0000-0000-0000-000000000005	a0000000-0000-0000-0000-000000000001	a0000010-0000-0000-0000-000000000001	f1000000-0000-0000-0000-000000000008	f2000000-0000-0000-0000-000000000001	\N	applicable	Reporte anual al RETC	\N	annual	\N	{}	2026-08-03 21:52:13.586623+00	\N	2026-08-03 21:52:13.586623+00	\N	\N
\.


--
-- Data for Name: nonconformities; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.nonconformities (id, tenant_id, facility_id, audit_item_id, article_compliance_id, code, title, description, severity, status, record_type, detection_origin, root_cause_answers, improvement_stages, detected_at, detected_by, owner_user_id, due_date, closed_at, closure_notes, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000040-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	a0000031-0000-0000-0000-000000000002	\N	NC-2026-001	Registros de mantenimiento de filtros desactualizados	Los registros de mantenimiento preventivo de filtros de manga no se han actualizado desde abril 2026, incumpliendo el procedimiento PMA-OPS-012.	minor	action_plan	\N	\N	[]	{}	2026-06-03 00:00:00+00	\N	d0000000-0000-0000-0000-000000000003	\N	\N	\N	2026-08-03 21:51:48.401167+00	\N	2026-08-03 21:51:48.401167+00	\N	\N
\.


--
-- Data for Name: norm_sectors; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.norm_sectors (norm_id, sector_id, article_id, applicability_level, rationale, source, confidence) FROM stdin;
f1000000-0000-0000-0000-000000000001	5	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000002	5	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000003	3	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000004	5	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000005	5	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000006	1	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000006	2	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000007	5	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000008	1	\N	directa	\N	analyst	\N
f1000000-0000-0000-0000-000000000008	2	\N	directa	\N	analyst	\N
\.


--
-- Data for Name: norm_sync_runs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.norm_sync_runs (id, source_id, started_at, finished_at, status, request_parameters, response_metadata, norms_created, norms_updated, versions_created, error_detail) FROM stdin;
\.


--
-- Data for Name: notification_rules; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.notification_rules (id, tenant_id, event_type, channel, lead_minutes, recipient_rule, template_code, active, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: notification_templates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.notification_templates (id, tenant_id, code, name, event_type, channel, locale, subject_template, body_template, variables_schema, version_no, active, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000090-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	OBL_VENCIMIENTO	Obligación próxima a vencer	obligation_due	email	es-CL	Obligación {{obligation_code}} vence en {{days_remaining}} días	La obligación "{{obligation_title}}" asignada a {{facility_name}} vence el {{due_date}}. Por favor tome las acciones necesarias.	{}	1	t	2026-08-03 21:51:48.422451+00	\N	2026-08-03 21:51:48.422451+00	\N	\N
a0000090-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	AUDIT_PROGRAMADA	Auditoría programada	audit_scheduled	email	es-CL	Auditoría programada: {{audit_title}}	Se ha programado la auditoría "{{audit_title}}" para el período {{start_date}} - {{end_date}} en {{facility_name}}.	{}	1	t	2026-08-03 21:51:48.422451+00	\N	2026-08-03 21:51:48.422451+00	\N	\N
a0000090-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	NC_NUEVA	Nueva no conformidad	nc_created	in_app	es-CL	No conformidad detectada: {{nc_code}}	Se ha registrado la no conformidad "{{nc_title}}" con severidad {{severity}}. Responsable: {{responsible_name}}.	{}	1	t	2026-08-03 21:51:48.422451+00	\N	2026-08-03 21:51:48.422451+00	\N	\N
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.notifications (id, tenant_id, rule_id, recipient_user_id, channel, subject, body, status, scheduled_at, sent_at, read_at, provider_message_id, context, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000091-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	\N	d0000000-0000-0000-0000-000000000002	email	Obligación OBL-REP-NFU-2026 vencida	La obligación "Plan de gestión NFU (Ley REP)" asignada a Planta Calama venció el 30/09/2026. Requiere acción inmediata.	sent	2026-08-03 21:51:48.424339+00	\N	\N	\N	{}	2026-08-03 21:51:48.424339+00	\N	2026-08-03 21:51:48.424339+00	\N	\N
a0000091-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	\N	d0000000-0000-0000-0000-000000000001	in_app	Fiscalización SMA programada para septiembre	Se ha programado la fiscalización de la SMA en Faena Antofagasta del 15 al 17 de septiembre 2026.	delivered	2026-08-03 21:51:48.424339+00	\N	\N	\N	{}	2026-08-03 21:51:48.424339+00	\N	2026-08-03 21:51:48.424339+00	\N	\N
a0000091-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	\N	d0000000-0000-0000-0000-000000000003	in_app	No conformidad NC-2026-001 detectada	Registros de mantenimiento de filtros desactualizados. Severidad: menor. Por favor revise y tome acción.	read	2026-08-03 21:51:48.424339+00	\N	\N	\N	{}	2026-08-03 21:51:48.424339+00	\N	2026-08-03 21:51:48.424339+00	\N	\N
\.


--
-- Data for Name: obligation_templates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.obligation_templates (id, country_id, code, name, authority, frequency_rule, default_lead_days, template_config, active, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000020-0000-0000-0000-000000000001	1	RETC-ANUAL	Declaración anual RETC	Ministerio del Medio Ambiente	{"type": "annual", "month": 3, "day": 31}	60	{}	t	2026-08-03 21:52:13.591019+00	\N	2026-08-03 21:52:13.591019+00	\N	\N
a0000020-0000-0000-0000-000000000002	1	SIDREP-SEM	Declaración semestral SIDREP (residuos peligrosos)	Ministerio de Salud / SEREMI	{"type": "semiannual", "months": [1, 7], "day": 15}	30	{}	t	2026-08-03 21:52:13.591019+00	\N	2026-08-03 21:52:13.591019+00	\N	\N
a0000020-0000-0000-0000-000000000003	1	DS90-TRIM	Monitoreo trimestral de RILes (DS 90)	Superintendencia de Servicios Sanitarios	{"type": "quarterly", "day": 15}	15	{}	t	2026-08-03 21:52:13.591019+00	\N	2026-08-03 21:52:13.591019+00	\N	\N
\.


--
-- Data for Name: obligations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.obligations (id, tenant_id, template_id, matrix_norm_id, article_compliance_id, facility_id, code, title, period_start, period_end, due_at, status, owner_user_id, submitted_at, external_receipt, data, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000021-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	a0000020-0000-0000-0000-000000000001	a0000011-0000-0000-0000-000000000005	\N	b0000000-0000-0000-0000-000000000001	OBL-RETC-2026	Declaración RETC 2026	2026-01-01	2026-12-31	2027-04-01 02:59:00+00	in_progress	d0000000-0000-0000-0000-000000000002	\N	\N	{}	2026-08-03 21:52:13.593054+00	\N	2026-08-03 21:52:13.593054+00	\N	\N
a0000021-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	a0000020-0000-0000-0000-000000000002	a0000011-0000-0000-0000-000000000002	\N	b0000000-0000-0000-0000-000000000001	OBL-SIDREP-2026S1	Declaración SIDREP 1er Semestre 2026	2026-01-01	2026-06-30	2026-07-16 02:59:00+00	submitted	d0000000-0000-0000-0000-000000000002	\N	\N	{}	2026-08-03 21:52:13.593054+00	\N	2026-08-03 21:52:13.593054+00	\N	\N
a0000021-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	a0000020-0000-0000-0000-000000000002	a0000011-0000-0000-0000-000000000002	\N	b0000000-0000-0000-0000-000000000001	OBL-SIDREP-2026S2	Declaración SIDREP 2do Semestre 2026	2026-07-01	2026-12-31	2027-01-16 02:59:00+00	draft	d0000000-0000-0000-0000-000000000002	\N	\N	{}	2026-08-03 21:52:13.593054+00	\N	2026-08-03 21:52:13.593054+00	\N	\N
a0000021-0000-0000-0000-000000000004	a0000000-0000-0000-0000-000000000001	a0000020-0000-0000-0000-000000000003	a0000011-0000-0000-0000-000000000004	\N	b0000000-0000-0000-0000-000000000001	OBL-DS90-2026Q3	Monitoreo RILes Q3 2026	2026-07-01	2026-09-30	2026-10-16 02:59:00+00	open	d0000000-0000-0000-0000-000000000003	\N	\N	{}	2026-08-03 21:52:13.593054+00	\N	2026-08-03 21:52:13.593054+00	\N	\N
a0000021-0000-0000-0000-000000000005	a0000000-0000-0000-0000-000000000001	\N	a0000011-0000-0000-0000-000000000003	\N	b0000000-0000-0000-0000-000000000001	OBL-REP-NFU-2026	Plan de gestión NFU (Ley REP)	2026-01-01	2026-12-31	2026-10-01 02:59:00+00	overdue	d0000000-0000-0000-0000-000000000002	\N	\N	{}	2026-08-03 21:52:13.593054+00	\N	2026-08-03 21:52:13.593054+00	\N	\N
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.permissions (id, code, module, description) FROM stdin;
1	dashboard.view	dashboard	Ver dashboard principal
2	matrix.view	compliance	Ver matriz legal
3	matrix.edit	compliance	Editar matriz legal
4	obligations.view	obligations	Ver obligaciones
5	obligations.edit	obligations	Crear y editar obligaciones
6	obligations.submit	obligations	Enviar declaraciones
7	audits.view	audits	Ver auditorías
8	audits.edit	audits	Crear y editar auditorías
9	users.view	admin	Ver usuarios
10	users.edit	admin	Gestionar usuarios
11	settings.edit	admin	Editar configuración de empresa
12	reports.view	reports	Ver reportes
13	reports.export	reports	Exportar reportes
14	catalog.view	catalog	Ver catálogo normativo
15	catalog.edit	catalog	Editar catálogo normativo (admin global)
16	tenants.manage	admin	Gestionar tenants (admin global)
17	support.view	support	Ver tickets de soporte
18	support.edit	support	Gestionar tickets de soporte
19	documents.view	documents	Ver documentos
20	documents.edit	documents	Subir y editar documentos
\.


--
-- Data for Name: processes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.processes (id, tenant_id, department_id, parent_process_id, code, name, process_type, description, responsible_user_id, inputs, outputs, display_order, active, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000050-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	c0000000-0000-0000-0000-000000000002	\N	PROC-CHANC	Chancado y Molienda	operational	Reducción de tamaño del mineral mediante chancadores y molinos	d0000000-0000-0000-0000-000000000003	[]	[]	1	t	2026-08-03 21:51:48.40573+00	\N	2026-08-03 21:51:48.40573+00	\N	\N
a0000050-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	c0000000-0000-0000-0000-000000000002	\N	PROC-FLOT	Flotación	operational	Separación de minerales por flotación en celdas	d0000000-0000-0000-0000-000000000003	[]	[]	2	t	2026-08-03 21:51:48.40573+00	\N	2026-08-03 21:51:48.40573+00	\N	\N
a0000050-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	c0000000-0000-0000-0000-000000000001	\N	PROC-MONIT	Monitoreo Ambiental	support	Monitoreo de calidad de aire, agua y suelo	d0000000-0000-0000-0000-000000000002	[]	[]	3	t	2026-08-03 21:51:48.40573+00	\N	2026-08-03 21:51:48.40573+00	\N	\N
a0000050-0000-0000-0000-000000000004	a0000000-0000-0000-0000-000000000001	c0000000-0000-0000-0000-000000000001	\N	PROC-RESPEL	Gestión de Residuos Peligrosos	support	Manejo, almacenamiento temporal y disposición de RESPEL	d0000000-0000-0000-0000-000000000002	[]	[]	4	t	2026-08-03 21:51:48.40573+00	\N	2026-08-03 21:51:48.40573+00	\N	\N
\.


--
-- Data for Name: regulated_equipment; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.regulated_equipment (id, tenant_id, facility_id, name, equipment_type, brand, model, registration_authority, registration_number, registration_expires_at, status, technical_specs, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000070-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	Caldera de vapor principal	caldera	Babcock & Wilcox	FW-15	SEC	SEC-II-2024-0451	2026-09-15	operational	{"fuel": "gas_natural", "norm": "DS 48/1984", "capacity": "15 ton/hr"}	2026-08-03 21:51:48.416398+00	\N	2026-08-03 21:51:48.416398+00	\N	\N
a0000070-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	b0000000-0000-0000-0000-000000000001	Estanque de petróleo diésel	estanque_combustible	Isisan	TK-50000	SEC	SEC-II-2024-0892	2027-01-20	operational	{"norm": "DS 160/2008", "type": "superficial", "capacity_liters": 50000}	2026-08-03 21:51:48.416398+00	\N	2026-08-03 21:51:48.416398+00	\N	\N
\.


--
-- Data for Name: risks_opportunities; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.risks_opportunities (id, tenant_id, facility_id, environmental_aspect_id, action_plan_id, code, entry_type, description, origin, risk_level, treatment, status, owner_user_id, review_date, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000061-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	\N	\N	\N	R-2026-001	risk	Riesgo de sanción SMA por no cumplir condiciones de la RCA-045/2018 en planta Calama	compliance	critical	mitigate	in_treatment	d0000000-0000-0000-0000-000000000002	\N	2026-08-03 21:51:48.413799+00	\N	2026-08-03 21:51:48.413799+00	\N	\N
a0000061-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	\N	\N	\N	O-2026-001	opportunity	Obtener certificación ISO 14001 mejora imagen corporativa y acceso a mercados internacionales	context	high	exploit	identified	d0000000-0000-0000-0000-000000000001	\N	2026-08-03 21:51:48.413799+00	\N	2026-08-03 21:51:48.413799+00	\N	\N
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.role_permissions (role_id, permission_id, granted) FROM stdin;
e0000000-0000-0000-0000-000000000001	1	t
e0000000-0000-0000-0000-000000000001	2	t
e0000000-0000-0000-0000-000000000001	3	t
e0000000-0000-0000-0000-000000000001	4	t
e0000000-0000-0000-0000-000000000001	5	t
e0000000-0000-0000-0000-000000000001	6	t
e0000000-0000-0000-0000-000000000001	7	t
e0000000-0000-0000-0000-000000000001	8	t
e0000000-0000-0000-0000-000000000001	9	t
e0000000-0000-0000-0000-000000000001	10	t
e0000000-0000-0000-0000-000000000001	11	t
e0000000-0000-0000-0000-000000000001	12	t
e0000000-0000-0000-0000-000000000001	13	t
e0000000-0000-0000-0000-000000000001	14	t
e0000000-0000-0000-0000-000000000001	17	t
e0000000-0000-0000-0000-000000000001	19	t
e0000000-0000-0000-0000-000000000001	20	t
e0000000-0000-0000-0000-000000000002	1	t
e0000000-0000-0000-0000-000000000002	2	t
e0000000-0000-0000-0000-000000000002	3	t
e0000000-0000-0000-0000-000000000002	4	t
e0000000-0000-0000-0000-000000000002	5	t
e0000000-0000-0000-0000-000000000002	6	t
e0000000-0000-0000-0000-000000000002	7	t
e0000000-0000-0000-0000-000000000002	12	t
e0000000-0000-0000-0000-000000000002	14	t
e0000000-0000-0000-0000-000000000002	19	t
e0000000-0000-0000-0000-000000000002	20	t
e0000000-0000-0000-0000-000000000003	1	t
e0000000-0000-0000-0000-000000000003	2	t
e0000000-0000-0000-0000-000000000003	4	t
e0000000-0000-0000-0000-000000000003	7	t
e0000000-0000-0000-0000-000000000003	19	t
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.roles (id, tenant_id, code, name, is_system, description, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
e0000000-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	admin_empresa	Administrador de Empresa	t	Acceso total a la gestión de la empresa	2026-08-03 21:51:48.362608+00	\N	2026-08-03 21:51:48.362608+00	\N	\N
e0000000-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	encargado_ambiental	Encargado Ambiental	t	Gestión de cumplimiento y obligaciones	2026-08-03 21:51:48.362608+00	\N	2026-08-03 21:51:48.362608+00	\N	\N
e0000000-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	operador	Operador	t	Acceso de solo lectura y ejecución de tareas asignadas	2026-08-03 21:51:48.362608+00	\N	2026-08-03 21:51:48.362608+00	\N	\N
\.


--
-- Data for Name: sectors; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sectors (id, country_id, parent_id, code, name, description, metadata) FROM stdin;
1	\N	\N	MIN	Minería	\N	{}
2	\N	\N	IND	Industria manufacturera	\N	{}
3	\N	\N	ENE	Energía	\N	{}
4	\N	\N	AGR	Agricultura y ganadería	\N	{}
5	\N	\N	GEN	Aplicación general	\N	{}
\.


--
-- Data for Name: support_ticket_messages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.support_ticket_messages (id, tenant_id, ticket_id, author_user_id, author_guest_email, message_type, body, is_internal, created_at) FROM stdin;
\.


--
-- Data for Name: support_tickets; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.support_tickets (id, tenant_id, ticket_number, created_by_user_id, guest_name, guest_email, category, subject, description, priority, status, assigned_to, related_entity_type, related_entity_id, resolved_at, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
\.


--
-- Data for Name: tasks; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tasks (id, tenant_id, obligation_id, parent_task_id, task_type, title, description, status, priority, start_at, due_at, completed_at, assignee_user_id, department_id, progress_percent, metadata, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000022-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	a0000021-0000-0000-0000-000000000001	\N	task	Recopilar datos de emisiones atmosféricas	Consolidar mediciones de MP10, MP2.5, SO2, NOx de todas las fuentes	in_progress	high	\N	2026-09-01 02:59:00+00	\N	d0000000-0000-0000-0000-000000000003	c0000000-0000-0000-0000-000000000002	0.00	{}	2026-08-03 21:52:13.597356+00	\N	2026-08-03 21:52:13.597356+00	\N	\N
a0000022-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	a0000021-0000-0000-0000-000000000001	\N	task	Recopilar datos de residuos generados	Consolidar manifiestos de residuos peligrosos y no peligrosos	todo	medium	\N	2026-10-01 02:59:00+00	\N	d0000000-0000-0000-0000-000000000003	c0000000-0000-0000-0000-000000000002	0.00	{}	2026-08-03 21:52:13.597356+00	\N	2026-08-03 21:52:13.597356+00	\N	\N
a0000022-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	a0000021-0000-0000-0000-000000000001	\N	approval	Revisión final declaración RETC	Validar datos consolidados antes de envío	todo	high	\N	2027-03-16 02:59:00+00	\N	d0000000-0000-0000-0000-000000000002	c0000000-0000-0000-0000-000000000001	0.00	{}	2026-08-03 21:52:13.597356+00	\N	2026-08-03 21:52:13.597356+00	\N	\N
a0000022-0000-0000-0000-000000000004	a0000000-0000-0000-0000-000000000001	a0000021-0000-0000-0000-000000000004	\N	task	Toma de muestras RILes Q3	Realizar muestreo compuesto en punto de descarga	todo	high	\N	2026-09-21 02:59:00+00	\N	d0000000-0000-0000-0000-000000000003	c0000000-0000-0000-0000-000000000002	0.00	{}	2026-08-03 21:52:13.597356+00	\N	2026-08-03 21:52:13.597356+00	\N	\N
\.


--
-- Data for Name: tenant_legal_matrices; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tenant_legal_matrices (id, tenant_id, name, period_year, facility_id, status, version_no, approved_at, approved_by, scope_definition, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000010-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	Matriz Legal Ambiental 2026	2026	\N	approved	1	2026-02-15 13:00:00+00	d0000000-0000-0000-0000-000000000001	{}	2026-08-03 21:52:13.583755+00	\N	2026-08-03 21:52:13.583755+00	\N	\N
\.


--
-- Data for Name: tenants; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tenants (id, country_id, parent_tenant_id, tenant_type, rut_tax_id, legal_name, trade_name, business_activity, status, settings, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
a0000000-0000-0000-0000-000000000001	1	\N	company	76.123.456-7	Minera Andes SpA	Minera Andes	Extracción de minerales metálicos no ferrosos	active	{"plan": "enterprise", "max_users": 50, "max_facilities": 10}	2026-08-03 21:51:48.349817+00	\N	2026-08-03 21:51:48.349817+00	\N	\N
a0000000-0000-0000-0000-000000000002	1	\N	manager	76.987.654-3	EcoGestión Consultoría Ambiental Ltda	EcoGestión	Consultoría en gestión ambiental y cumplimiento normativo	active	{"plan": "professional", "max_users": 20, "max_facilities": 5}	2026-08-03 21:51:48.349817+00	\N	2026-08-03 21:51:48.349817+00	\N	\N
\.


--
-- Data for Name: user_roles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.user_roles (user_id, role_id, tenant_id, facility_id, department_id, valid_from, valid_to) FROM stdin;
d0000000-0000-0000-0000-000000000001	e0000000-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	\N	\N	2026-08-03 21:51:48.367229+00	\N
d0000000-0000-0000-0000-000000000002	e0000000-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	\N	\N	2026-08-03 21:51:48.367229+00	\N
d0000000-0000-0000-0000-000000000003	e0000000-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	\N	\N	2026-08-03 21:51:48.367229+00	\N
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, tenant_id, department_id, rut_tax_id, email, full_name, user_type, status, password_hash, preferences, last_login_at, created_at, created_by, updated_at, updated_by, deleted_at) FROM stdin;
d0000000-0000-0000-0000-000000000001	a0000000-0000-0000-0000-000000000001	c0000000-0000-0000-0000-000000000003	12.345.678-9	carlos.mendoza@mineraandes.cl	Carlos Mendoza Reyes	tenant_admin	active	$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q	{"language": "es", "timezone": "America/Santiago", "notifications": {"push": true, "email": true}}	\N	2026-08-03 21:51:48.357991+00	\N	2026-08-03 21:51:48.357991+00	\N	\N
d0000000-0000-0000-0000-000000000002	a0000000-0000-0000-0000-000000000001	c0000000-0000-0000-0000-000000000001	13.456.789-0	maria.silva@mineraandes.cl	María Silva Contreras	internal	active	$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q	{"language": "es", "timezone": "America/Santiago"}	\N	2026-08-03 21:51:48.357991+00	\N	2026-08-03 21:51:48.357991+00	\N	\N
d0000000-0000-0000-0000-000000000003	a0000000-0000-0000-0000-000000000001	c0000000-0000-0000-0000-000000000002	14.567.890-1	pedro.gonzalez@mineraandes.cl	Pedro González Muñoz	internal	active	$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q	{"language": "es", "timezone": "America/Santiago"}	\N	2026-08-03 21:51:48.357991+00	\N	2026-08-03 21:51:48.357991+00	\N	\N
d0000000-0000-0000-0000-000000000004	a0000000-0000-0000-0000-000000000002	c0000000-0000-0000-0000-000000000004	15.678.901-2	ana.rojas@ecogestion.cl	Ana Rojas Figueroa	tenant_admin	active	$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q	{"language": "es", "timezone": "America/Santiago"}	\N	2026-08-03 21:51:48.357991+00	\N	2026-08-03 21:51:48.357991+00	\N	\N
d0000000-0000-0000-0000-000000000005	a0000000-0000-0000-0000-000000000002	c0000000-0000-0000-0000-000000000004	16.789.012-3	jorge.martinez@ecogestion.cl	Jorge Martínez Soto	internal	active	$2b$12$LJ3m5ZQnJPfDLkGjzEKMXeJHvBqMKczKz5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q	{"language": "es", "timezone": "America/Santiago"}	\N	2026-08-03 21:51:48.357991+00	\N	2026-08-03 21:51:48.357991+00	\N	\N
\.


--
-- Name: audit_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.audit_log_id_seq', 1, false);


--
-- Name: chatbot_messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.chatbot_messages_id_seq', 1, false);


--
-- Name: countries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.countries_id_seq', 5, true);


--
-- Name: entity_documents_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.entity_documents_id_seq', 1, false);


--
-- Name: entity_status_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.entity_status_history_id_seq', 1, false);


--
-- Name: legal_relations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.legal_relations_id_seq', 1, false);


--
-- Name: legal_sources_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.legal_sources_id_seq', 4, true);


--
-- Name: norm_sync_runs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.norm_sync_runs_id_seq', 1, false);


--
-- Name: permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.permissions_id_seq', 39, true);


--
-- Name: sectors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.sectors_id_seq', 8, true);


--
-- Name: support_ticket_messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.support_ticket_messages_id_seq', 1, false);


--
-- Name: action_plans action_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_plans
    ADD CONSTRAINT action_plans_pkey PRIMARY KEY (id);


--
-- Name: article_compliance article_compliance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT article_compliance_pkey PRIMARY KEY (id);


--
-- Name: audit_items audit_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_items
    ADD CONSTRAINT audit_items_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: audit_participants audit_participants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_participants
    ADD CONSTRAINT audit_participants_pkey PRIMARY KEY (audit_id, user_id);


--
-- Name: audits audits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audits
    ADD CONSTRAINT audits_pkey PRIMARY KEY (id);


--
-- Name: chatbot_conversations chatbot_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatbot_conversations
    ADD CONSTRAINT chatbot_conversations_pkey PRIMARY KEY (id);


--
-- Name: chatbot_messages chatbot_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatbot_messages
    ADD CONSTRAINT chatbot_messages_pkey PRIMARY KEY (id);


--
-- Name: contracts contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_pkey PRIMARY KEY (id);


--
-- Name: countries countries_iso2_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.countries
    ADD CONSTRAINT countries_iso2_key UNIQUE (iso2);


--
-- Name: countries countries_iso3_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.countries
    ADD CONSTRAINT countries_iso3_key UNIQUE (iso3);


--
-- Name: countries countries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.countries
    ADD CONSTRAINT countries_pkey PRIMARY KEY (id);


--
-- Name: declaration_submissions declaration_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT declaration_submissions_pkey PRIMARY KEY (id);


--
-- Name: declaration_templates declaration_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_templates
    ADD CONSTRAINT declaration_templates_pkey PRIMARY KEY (id);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: document_versions document_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT document_versions_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: entity_documents entity_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_documents
    ADD CONSTRAINT entity_documents_pkey PRIMARY KEY (id);


--
-- Name: entity_status_history entity_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_status_history
    ADD CONSTRAINT entity_status_history_pkey PRIMARY KEY (id);


--
-- Name: environmental_aspects environmental_aspects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environmental_aspects
    ADD CONSTRAINT environmental_aspects_pkey PRIMARY KEY (id);


--
-- Name: equipment_operators equipment_operators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment_operators
    ADD CONSTRAINT equipment_operators_pkey PRIMARY KEY (equipment_id, user_id);


--
-- Name: facilities facilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facilities
    ADD CONSTRAINT facilities_pkey PRIMARY KEY (id);


--
-- Name: facility_norm_assignments facility_norm_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_norm_assignments
    ADD CONSTRAINT facility_norm_assignments_pkey PRIMARY KEY (id);


--
-- Name: facility_processes facility_processes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_processes
    ADD CONSTRAINT facility_processes_pkey PRIMARY KEY (facility_id, process_id);


--
-- Name: integration_accounts integration_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_accounts
    ADD CONSTRAINT integration_accounts_pkey PRIMARY KEY (id);


--
-- Name: legal_articles legal_articles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_articles
    ADD CONSTRAINT legal_articles_pkey PRIMARY KEY (id);


--
-- Name: legal_norm_versions legal_norm_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_norm_versions
    ADD CONSTRAINT legal_norm_versions_pkey PRIMARY KEY (id);


--
-- Name: legal_norms legal_norms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_norms
    ADD CONSTRAINT legal_norms_pkey PRIMARY KEY (id);


--
-- Name: legal_relations legal_relations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_relations
    ADD CONSTRAINT legal_relations_pkey PRIMARY KEY (id);


--
-- Name: legal_sources legal_sources_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_sources
    ADD CONSTRAINT legal_sources_code_key UNIQUE (code);


--
-- Name: legal_sources legal_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_sources
    ADD CONSTRAINT legal_sources_pkey PRIMARY KEY (id);


--
-- Name: matrix_norms matrix_norms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matrix_norms
    ADD CONSTRAINT matrix_norms_pkey PRIMARY KEY (id);


--
-- Name: nonconformities nonconformities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nonconformities
    ADD CONSTRAINT nonconformities_pkey PRIMARY KEY (id);


--
-- Name: norm_sectors norm_sectors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.norm_sectors
    ADD CONSTRAINT norm_sectors_pkey PRIMARY KEY (norm_id, sector_id);


--
-- Name: norm_sync_runs norm_sync_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.norm_sync_runs
    ADD CONSTRAINT norm_sync_runs_pkey PRIMARY KEY (id);


--
-- Name: notification_rules notification_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_rules
    ADD CONSTRAINT notification_rules_pkey PRIMARY KEY (id);


--
-- Name: notification_templates notification_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT notification_templates_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: obligation_templates obligation_templates_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligation_templates
    ADD CONSTRAINT obligation_templates_code_key UNIQUE (code);


--
-- Name: obligation_templates obligation_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligation_templates
    ADD CONSTRAINT obligation_templates_pkey PRIMARY KEY (id);


--
-- Name: obligations obligations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligations
    ADD CONSTRAINT obligations_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_code_key UNIQUE (code);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: processes processes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processes
    ADD CONSTRAINT processes_pkey PRIMARY KEY (id);


--
-- Name: regulated_equipment regulated_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regulated_equipment
    ADD CONSTRAINT regulated_equipment_pkey PRIMARY KEY (id);


--
-- Name: risks_opportunities risks_opportunities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risks_opportunities
    ADD CONSTRAINT risks_opportunities_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: sectors sectors_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT sectors_code_key UNIQUE (code);


--
-- Name: sectors sectors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT sectors_pkey PRIMARY KEY (id);


--
-- Name: support_ticket_messages support_ticket_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_ticket_messages
    ADD CONSTRAINT support_ticket_messages_pkey PRIMARY KEY (id);


--
-- Name: support_tickets support_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_pkey PRIMARY KEY (id);


--
-- Name: support_tickets support_tickets_ticket_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_ticket_number_key UNIQUE (ticket_number);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: tenant_legal_matrices tenant_legal_matrices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_legal_matrices
    ADD CONSTRAINT tenant_legal_matrices_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: article_compliance uq_article_compliance; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT uq_article_compliance UNIQUE (matrix_norm_id, article_id, facility_id);


--
-- Name: audit_items uq_audit_items_seq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_items
    ADD CONSTRAINT uq_audit_items_seq UNIQUE (audit_id, sequence);


--
-- Name: audits uq_audits_tenant_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audits
    ADD CONSTRAINT uq_audits_tenant_code UNIQUE (tenant_id, code);


--
-- Name: contracts uq_contracts_manager_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT uq_contracts_manager_number UNIQUE (manager_tenant_id, contract_number);


--
-- Name: declaration_templates uq_declaration_templates; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_templates
    ADD CONSTRAINT uq_declaration_templates UNIQUE (system_code, version);


--
-- Name: departments uq_departments_tenant_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT uq_departments_tenant_code UNIQUE (tenant_id, code);


--
-- Name: document_versions uq_document_versions; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT uq_document_versions UNIQUE (document_id, version_no);


--
-- Name: facilities uq_facilities_tenant_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facilities
    ADD CONSTRAINT uq_facilities_tenant_code UNIQUE (tenant_id, code);


--
-- Name: legal_articles uq_legal_articles_external; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_articles
    ADD CONSTRAINT uq_legal_articles_external UNIQUE (norm_version_id, external_article_id);


--
-- Name: legal_norms uq_legal_norms_source_external; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_norms
    ADD CONSTRAINT uq_legal_norms_source_external UNIQUE (source_id, external_norm_id);


--
-- Name: matrix_norms uq_matrix_norms; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matrix_norms
    ADD CONSTRAINT uq_matrix_norms UNIQUE (matrix_id, norm_id);


--
-- Name: nonconformities uq_nonconformities_tenant_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nonconformities
    ADD CONSTRAINT uq_nonconformities_tenant_code UNIQUE (tenant_id, code);


--
-- Name: legal_norm_versions uq_norm_versions_hash; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_norm_versions
    ADD CONSTRAINT uq_norm_versions_hash UNIQUE (norm_id, content_hash);


--
-- Name: notification_templates uq_notification_templates; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT uq_notification_templates UNIQUE (tenant_id, code);


--
-- Name: obligations uq_obligations_tenant_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligations
    ADD CONSTRAINT uq_obligations_tenant_code UNIQUE (tenant_id, code);


--
-- Name: processes uq_processes_tenant_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processes
    ADD CONSTRAINT uq_processes_tenant_code UNIQUE (tenant_id, code);


--
-- Name: risks_opportunities uq_risks_opportunities_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risks_opportunities
    ADD CONSTRAINT uq_risks_opportunities_code UNIQUE (tenant_id, code);


--
-- Name: roles uq_roles_tenant_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT uq_roles_tenant_code UNIQUE (tenant_id, code);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_ac_attributes; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ac_attributes ON public.article_compliance USING gin (attributes);


--
-- Name: ix_ac_matrixnorm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ac_matrixnorm ON public.article_compliance USING btree (matrix_norm_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_ac_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ac_tenant_status ON public.article_compliance USING btree (tenant_id, compliance_status) WHERE (deleted_at IS NULL);


--
-- Name: ix_ap_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ap_tenant_status ON public.action_plans USING btree (tenant_id, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_articles_fts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_articles_fts ON public.legal_articles USING gin (to_tsvector('spanish'::regconfig, content));


--
-- Name: ix_articles_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_articles_version ON public.legal_articles USING btree (norm_version_id, display_order);


--
-- Name: ix_auditems_audit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditems_audit ON public.audit_items USING btree (audit_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_auditlog_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditlog_actor ON public.audit_log USING btree (actor_user_id, occurred_at DESC);


--
-- Name: ix_auditlog_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditlog_entity ON public.audit_log USING btree (entity_type, entity_id);


--
-- Name: ix_auditlog_occurred; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditlog_occurred ON public.audit_log USING brin (occurred_at);


--
-- Name: ix_audits_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audits_tenant_status ON public.audits USING btree (tenant_id, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_contracts_client; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_client ON public.contracts USING btree (client_tenant_id);


--
-- Name: ix_contracts_manager; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_manager ON public.contracts USING btree (manager_tenant_id);


--
-- Name: ix_conv_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conv_user ON public.chatbot_conversations USING btree (user_id, last_message_at DESC) WHERE (deleted_at IS NULL);


--
-- Name: ix_departments_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_departments_tenant ON public.departments USING btree (tenant_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_documents_tags; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_tags ON public.documents USING gin (tags);


--
-- Name: ix_documents_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_tenant ON public.documents USING btree (tenant_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_docversions_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_docversions_document ON public.document_versions USING btree (document_id);


--
-- Name: ix_ds_folio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ds_folio ON public.declaration_submissions USING btree (external_folio) WHERE (external_folio IS NOT NULL);


--
-- Name: ix_ds_obligation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ds_obligation ON public.declaration_submissions USING btree (obligation_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_ea_significance; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ea_significance ON public.environmental_aspects USING btree (tenant_id, significance) WHERE (deleted_at IS NULL);


--
-- Name: ix_ea_tenant_facility; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ea_tenant_facility ON public.environmental_aspects USING btree (tenant_id, facility_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_entdocs_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entdocs_entity ON public.entity_documents USING btree (entity_type, entity_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_entdocs_vencimiento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entdocs_vencimiento ON public.entity_documents USING btree (valid_to) WHERE ((valid_to IS NOT NULL) AND (deleted_at IS NULL));


--
-- Name: ix_eo_cert_vencimiento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_eo_cert_vencimiento ON public.equipment_operators USING btree (certification_expires_at) WHERE (deleted_at IS NULL);


--
-- Name: ix_eo_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_eo_user ON public.equipment_operators USING btree (user_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_esh_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_esh_entity ON public.entity_status_history USING btree (entity_type, entity_id, changed_at DESC);


--
-- Name: ix_facilities_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_facilities_tenant ON public.facilities USING btree (tenant_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_legal_norms_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_legal_norms_status ON public.legal_norms USING btree (status) WHERE (deleted_at IS NULL);


--
-- Name: ix_legal_norms_subjects; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_legal_norms_subjects ON public.legal_norms USING gin (subjects);


--
-- Name: ix_legal_norms_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_legal_norms_type ON public.legal_norms USING btree (norm_type);


--
-- Name: ix_matrices_tenant_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_matrices_tenant_year ON public.tenant_legal_matrices USING btree (tenant_id, period_year) WHERE (deleted_at IS NULL);


--
-- Name: ix_matrixnorms_matrix; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_matrixnorms_matrix ON public.matrix_norms USING btree (matrix_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_matrixnorms_review; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_matrixnorms_review ON public.matrix_norms USING btree (next_review_date) WHERE (deleted_at IS NULL);


--
-- Name: ix_msg_citednorms; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_msg_citednorms ON public.chatbot_messages USING gin (cited_norm_ids);


--
-- Name: ix_msg_conversation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_msg_conversation ON public.chatbot_messages USING btree (conversation_id, created_at);


--
-- Name: ix_nc_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_nc_due ON public.nonconformities USING btree (due_date) WHERE (deleted_at IS NULL);


--
-- Name: ix_nc_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_nc_tenant_status ON public.nonconformities USING btree (tenant_id, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_norm_versions_current; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_norm_versions_current ON public.legal_norm_versions USING btree (norm_id) WHERE is_current;


--
-- Name: ix_norm_versions_fts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_norm_versions_fts ON public.legal_norm_versions USING gin (to_tsvector('spanish'::regconfig, COALESCE(full_text, ''::text)));


--
-- Name: ix_norm_versions_norm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_norm_versions_norm ON public.legal_norm_versions USING btree (norm_id);


--
-- Name: ix_notifications_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_pending ON public.notifications USING btree (scheduled_at) WHERE ((status)::text = 'queued'::text);


--
-- Name: ix_notifications_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user ON public.notifications USING btree (recipient_user_id, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_obligations_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_obligations_status ON public.obligations USING btree (tenant_id, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_obligations_tenant_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_obligations_tenant_due ON public.obligations USING btree (tenant_id, due_at) WHERE (deleted_at IS NULL);


--
-- Name: ix_processes_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processes_tenant ON public.processes USING btree (tenant_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_re_tenant_facility; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_re_tenant_facility ON public.regulated_equipment USING btree (tenant_id, facility_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_re_vencimiento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_re_vencimiento ON public.regulated_equipment USING btree (registration_expires_at) WHERE (deleted_at IS NULL);


--
-- Name: ix_relations_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_relations_source ON public.legal_relations USING btree (source_norm_id);


--
-- Name: ix_relations_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_relations_target ON public.legal_relations USING btree (target_norm_id);


--
-- Name: ix_ro_aspect; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ro_aspect ON public.risks_opportunities USING btree (environmental_aspect_id) WHERE (environmental_aspect_id IS NOT NULL);


--
-- Name: ix_ro_tenant_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ro_tenant_type ON public.risks_opportunities USING btree (tenant_id, entry_type, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_roles_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_roles_tenant ON public.roles USING btree (tenant_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_tasks_assignee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_assignee ON public.tasks USING btree (assignee_user_id, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_tasks_obligation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_obligation ON public.tasks USING btree (obligation_id) WHERE (deleted_at IS NULL);


--
-- Name: ix_tasks_tenant_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_tenant_due ON public.tasks USING btree (tenant_id, due_at) WHERE (deleted_at IS NULL);


--
-- Name: ix_tenants_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenants_parent ON public.tenants USING btree (parent_tenant_id) WHERE (parent_tenant_id IS NOT NULL);


--
-- Name: ix_tickets_tenant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tickets_tenant_status ON public.support_tickets USING btree (tenant_id, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_tktmsg_ticket; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tktmsg_ticket ON public.support_ticket_messages USING btree (ticket_id, created_at);


--
-- Name: ix_users_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_status ON public.users USING btree (tenant_id, status) WHERE (deleted_at IS NULL);


--
-- Name: ix_users_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_tenant ON public.users USING btree (tenant_id) WHERE (deleted_at IS NULL);


--
-- Name: action_plans trg_action_plans_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_action_plans_updated_at BEFORE UPDATE ON public.action_plans FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: article_compliance trg_article_compliance_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_article_compliance_updated_at BEFORE UPDATE ON public.article_compliance FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: audit_items trg_audit_items_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_items_updated_at BEFORE UPDATE ON public.audit_items FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: audit_participants trg_audit_participants_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_participants_updated_at BEFORE UPDATE ON public.audit_participants FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: audits trg_audits_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audits_updated_at BEFORE UPDATE ON public.audits FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: chatbot_conversations trg_chatbot_conversations_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_chatbot_conversations_updated_at BEFORE UPDATE ON public.chatbot_conversations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: contracts trg_contracts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_contracts_updated_at BEFORE UPDATE ON public.contracts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: declaration_submissions trg_declaration_submissions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_declaration_submissions_updated_at BEFORE UPDATE ON public.declaration_submissions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: declaration_templates trg_declaration_templates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_declaration_templates_updated_at BEFORE UPDATE ON public.declaration_templates FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: departments trg_departments_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_departments_updated_at BEFORE UPDATE ON public.departments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: documents trg_documents_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_documents_updated_at BEFORE UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: entity_documents trg_entity_documents_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_entity_documents_updated_at BEFORE UPDATE ON public.entity_documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: environmental_aspects trg_environmental_aspects_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_environmental_aspects_updated_at BEFORE UPDATE ON public.environmental_aspects FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: equipment_operators trg_equipment_operators_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_equipment_operators_updated_at BEFORE UPDATE ON public.equipment_operators FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: facilities trg_facilities_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_facilities_updated_at BEFORE UPDATE ON public.facilities FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: facility_norm_assignments trg_facility_norm_assignments_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_facility_norm_assignments_updated_at BEFORE UPDATE ON public.facility_norm_assignments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: facility_processes trg_facility_processes_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_facility_processes_updated_at BEFORE UPDATE ON public.facility_processes FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: integration_accounts trg_integration_accounts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_integration_accounts_updated_at BEFORE UPDATE ON public.integration_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: legal_articles trg_legal_articles_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_legal_articles_updated_at BEFORE UPDATE ON public.legal_articles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: legal_norm_versions trg_legal_norm_versions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_legal_norm_versions_updated_at BEFORE UPDATE ON public.legal_norm_versions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: legal_norms trg_legal_norms_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_legal_norms_updated_at BEFORE UPDATE ON public.legal_norms FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: matrix_norms trg_matrix_norms_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_matrix_norms_updated_at BEFORE UPDATE ON public.matrix_norms FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: nonconformities trg_nonconformities_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_nonconformities_updated_at BEFORE UPDATE ON public.nonconformities FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: notification_rules trg_notification_rules_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_notification_rules_updated_at BEFORE UPDATE ON public.notification_rules FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: notification_templates trg_notification_templates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_notification_templates_updated_at BEFORE UPDATE ON public.notification_templates FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: notifications trg_notifications_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_notifications_updated_at BEFORE UPDATE ON public.notifications FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: obligation_templates trg_obligation_templates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_obligation_templates_updated_at BEFORE UPDATE ON public.obligation_templates FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: obligations trg_obligations_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_obligations_updated_at BEFORE UPDATE ON public.obligations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: processes trg_processes_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_processes_updated_at BEFORE UPDATE ON public.processes FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: regulated_equipment trg_regulated_equipment_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_regulated_equipment_updated_at BEFORE UPDATE ON public.regulated_equipment FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: risks_opportunities trg_risks_opportunities_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_risks_opportunities_updated_at BEFORE UPDATE ON public.risks_opportunities FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: roles trg_roles_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_roles_updated_at BEFORE UPDATE ON public.roles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: support_tickets trg_support_tickets_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_support_tickets_updated_at BEFORE UPDATE ON public.support_tickets FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: tasks trg_tasks_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tasks_updated_at BEFORE UPDATE ON public.tasks FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: tenant_legal_matrices trg_tenant_legal_matrices_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tenant_legal_matrices_updated_at BEFORE UPDATE ON public.tenant_legal_matrices FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: tenants trg_tenants_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tenants_updated_at BEFORE UPDATE ON public.tenants FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: users trg_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: article_compliance fk_ac_approvedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT fk_ac_approvedby FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: article_compliance fk_ac_article; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT fk_ac_article FOREIGN KEY (article_id) REFERENCES public.legal_articles(id);


--
-- Name: article_compliance fk_ac_assessedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT fk_ac_assessedby FOREIGN KEY (assessed_by) REFERENCES public.users(id);


--
-- Name: article_compliance fk_ac_department; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT fk_ac_department FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: article_compliance fk_ac_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT fk_ac_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: article_compliance fk_ac_matrixnorm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT fk_ac_matrixnorm FOREIGN KEY (matrix_norm_id) REFERENCES public.matrix_norms(id) ON DELETE CASCADE;


--
-- Name: article_compliance fk_ac_responsible; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT fk_ac_responsible FOREIGN KEY (responsible_user_id) REFERENCES public.users(id);


--
-- Name: article_compliance fk_ac_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.article_compliance
    ADD CONSTRAINT fk_ac_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: action_plans fk_ap_ac; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_plans
    ADD CONSTRAINT fk_ap_ac FOREIGN KEY (article_compliance_id) REFERENCES public.article_compliance(id);


--
-- Name: action_plans fk_ap_nc; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_plans
    ADD CONSTRAINT fk_ap_nc FOREIGN KEY (nonconformity_id) REFERENCES public.nonconformities(id) ON DELETE CASCADE;


--
-- Name: action_plans fk_ap_owner; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_plans
    ADD CONSTRAINT fk_ap_owner FOREIGN KEY (owner_user_id) REFERENCES public.users(id);


--
-- Name: action_plans fk_ap_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_plans
    ADD CONSTRAINT fk_ap_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: action_plans fk_ap_verifiedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_plans
    ADD CONSTRAINT fk_ap_verifiedby FOREIGN KEY (verified_by) REFERENCES public.users(id);


--
-- Name: legal_articles fk_articles_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_articles
    ADD CONSTRAINT fk_articles_parent FOREIGN KEY (parent_article_id) REFERENCES public.legal_articles(id);


--
-- Name: legal_articles fk_articles_version; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_articles
    ADD CONSTRAINT fk_articles_version FOREIGN KEY (norm_version_id) REFERENCES public.legal_norm_versions(id) ON DELETE CASCADE;


--
-- Name: audit_items fk_auditems_ac; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_items
    ADD CONSTRAINT fk_auditems_ac FOREIGN KEY (article_compliance_id) REFERENCES public.article_compliance(id);


--
-- Name: audit_items fk_auditems_audit; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_items
    ADD CONSTRAINT fk_auditems_audit FOREIGN KEY (audit_id) REFERENCES public.audits(id) ON DELETE CASCADE;


--
-- Name: audit_items fk_auditems_auditor; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_items
    ADD CONSTRAINT fk_auditems_auditor FOREIGN KEY (auditor_user_id) REFERENCES public.users(id);


--
-- Name: audit_items fk_auditems_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_items
    ADD CONSTRAINT fk_auditems_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: audit_log fk_auditlog_actor; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT fk_auditlog_actor FOREIGN KEY (actor_user_id) REFERENCES public.users(id);


--
-- Name: audit_log fk_auditlog_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT fk_auditlog_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: audit_participants fk_auditpart_audit; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_participants
    ADD CONSTRAINT fk_auditpart_audit FOREIGN KEY (audit_id) REFERENCES public.audits(id) ON DELETE CASCADE;


--
-- Name: audit_participants fk_auditpart_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_participants
    ADD CONSTRAINT fk_auditpart_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: audit_participants fk_auditpart_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_participants
    ADD CONSTRAINT fk_auditpart_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: audits fk_audits_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audits
    ADD CONSTRAINT fk_audits_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: audits fk_audits_lead; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audits
    ADD CONSTRAINT fk_audits_lead FOREIGN KEY (lead_auditor_user_id) REFERENCES public.users(id);


--
-- Name: audits fk_audits_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audits
    ADD CONSTRAINT fk_audits_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: contracts fk_contracts_client; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT fk_contracts_client FOREIGN KEY (client_tenant_id) REFERENCES public.tenants(id);


--
-- Name: contracts fk_contracts_manager; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT fk_contracts_manager FOREIGN KEY (manager_tenant_id) REFERENCES public.tenants(id);


--
-- Name: contracts fk_contracts_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT fk_contracts_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: chatbot_conversations fk_conv_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatbot_conversations
    ADD CONSTRAINT fk_conv_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: chatbot_conversations fk_conv_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatbot_conversations
    ADD CONSTRAINT fk_conv_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: chatbot_conversations fk_conv_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatbot_conversations
    ADD CONSTRAINT fk_conv_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: declaration_templates fk_dectmpl_country; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_templates
    ADD CONSTRAINT fk_dectmpl_country FOREIGN KEY (country_id) REFERENCES public.countries(id);


--
-- Name: declaration_templates fk_dectmpl_document; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_templates
    ADD CONSTRAINT fk_dectmpl_document FOREIGN KEY (source_document_id) REFERENCES public.documents(id);


--
-- Name: departments fk_departments_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT fk_departments_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: departments fk_departments_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT fk_departments_parent FOREIGN KEY (parent_department_id) REFERENCES public.departments(id);


--
-- Name: departments fk_departments_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT fk_departments_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: documents fk_documents_curversion; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_curversion FOREIGN KEY (current_version_id) REFERENCES public.document_versions(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: documents fk_documents_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: document_versions fk_docversions_createdby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT fk_docversions_createdby FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: document_versions fk_docversions_document; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT fk_docversions_document FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: document_versions fk_docversions_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT fk_docversions_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: declaration_submissions fk_ds_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT fk_ds_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: declaration_submissions fk_ds_obligation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT fk_ds_obligation FOREIGN KEY (obligation_id) REFERENCES public.obligations(id) ON DELETE CASCADE;


--
-- Name: declaration_submissions fk_ds_preparedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT fk_ds_preparedby FOREIGN KEY (prepared_by) REFERENCES public.users(id);


--
-- Name: declaration_submissions fk_ds_receipt; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT fk_ds_receipt FOREIGN KEY (receipt_document_id) REFERENCES public.documents(id);


--
-- Name: declaration_submissions fk_ds_reviewedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT fk_ds_reviewedby FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: declaration_submissions fk_ds_submittedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT fk_ds_submittedby FOREIGN KEY (submitted_by) REFERENCES public.users(id);


--
-- Name: declaration_submissions fk_ds_template; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT fk_ds_template FOREIGN KEY (template_id) REFERENCES public.declaration_templates(id);


--
-- Name: declaration_submissions fk_ds_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.declaration_submissions
    ADD CONSTRAINT fk_ds_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: environmental_aspects fk_ea_ac; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environmental_aspects
    ADD CONSTRAINT fk_ea_ac FOREIGN KEY (article_compliance_id) REFERENCES public.article_compliance(id);


--
-- Name: environmental_aspects fk_ea_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environmental_aspects
    ADD CONSTRAINT fk_ea_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id) ON DELETE CASCADE;


--
-- Name: environmental_aspects fk_ea_process; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environmental_aspects
    ADD CONSTRAINT fk_ea_process FOREIGN KEY (process_id) REFERENCES public.processes(id);


--
-- Name: environmental_aspects fk_ea_responsible; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environmental_aspects
    ADD CONSTRAINT fk_ea_responsible FOREIGN KEY (responsible_user_id) REFERENCES public.users(id);


--
-- Name: environmental_aspects fk_ea_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environmental_aspects
    ADD CONSTRAINT fk_ea_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: entity_documents fk_entdocs_document; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_documents
    ADD CONSTRAINT fk_entdocs_document FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: entity_documents fk_entdocs_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_documents
    ADD CONSTRAINT fk_entdocs_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: equipment_operators fk_eo_equipment; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment_operators
    ADD CONSTRAINT fk_eo_equipment FOREIGN KEY (equipment_id) REFERENCES public.regulated_equipment(id) ON DELETE CASCADE;


--
-- Name: equipment_operators fk_eo_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment_operators
    ADD CONSTRAINT fk_eo_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: equipment_operators fk_eo_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment_operators
    ADD CONSTRAINT fk_eo_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: entity_status_history fk_esh_changedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_status_history
    ADD CONSTRAINT fk_esh_changedby FOREIGN KEY (changed_by) REFERENCES public.users(id);


--
-- Name: entity_status_history fk_esh_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_status_history
    ADD CONSTRAINT fk_esh_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: facilities fk_facilities_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facilities
    ADD CONSTRAINT fk_facilities_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: facility_processes fk_facproc_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_processes
    ADD CONSTRAINT fk_facproc_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id) ON DELETE CASCADE;


--
-- Name: facility_processes fk_facproc_process; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_processes
    ADD CONSTRAINT fk_facproc_process FOREIGN KEY (process_id) REFERENCES public.processes(id) ON DELETE CASCADE;


--
-- Name: facility_processes fk_facproc_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_processes
    ADD CONSTRAINT fk_facproc_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: facility_norm_assignments fk_fna_assignedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_norm_assignments
    ADD CONSTRAINT fk_fna_assignedby FOREIGN KEY (assigned_by) REFERENCES public.users(id);


--
-- Name: facility_norm_assignments fk_fna_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_norm_assignments
    ADD CONSTRAINT fk_fna_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id) ON DELETE CASCADE;


--
-- Name: facility_norm_assignments fk_fna_norm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_norm_assignments
    ADD CONSTRAINT fk_fna_norm FOREIGN KEY (norm_id) REFERENCES public.legal_norms(id);


--
-- Name: facility_norm_assignments fk_fna_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_norm_assignments
    ADD CONSTRAINT fk_fna_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: facility_norm_assignments fk_fna_version; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility_norm_assignments
    ADD CONSTRAINT fk_fna_version FOREIGN KEY (assigned_version_id) REFERENCES public.legal_norm_versions(id);


--
-- Name: integration_accounts fk_intacc_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_accounts
    ADD CONSTRAINT fk_intacc_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: legal_norms fk_legalnorms_country; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_norms
    ADD CONSTRAINT fk_legalnorms_country FOREIGN KEY (country_id) REFERENCES public.countries(id);


--
-- Name: legal_norms fk_legalnorms_source; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_norms
    ADD CONSTRAINT fk_legalnorms_source FOREIGN KEY (source_id) REFERENCES public.legal_sources(id);


--
-- Name: legal_sources fk_legalsources_country; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_sources
    ADD CONSTRAINT fk_legalsources_country FOREIGN KEY (country_id) REFERENCES public.countries(id);


--
-- Name: tenant_legal_matrices fk_matrices_approver; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_legal_matrices
    ADD CONSTRAINT fk_matrices_approver FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: tenant_legal_matrices fk_matrices_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_legal_matrices
    ADD CONSTRAINT fk_matrices_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: tenant_legal_matrices fk_matrices_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_legal_matrices
    ADD CONSTRAINT fk_matrices_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: matrix_norms fk_matrixnorms_matrix; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matrix_norms
    ADD CONSTRAINT fk_matrixnorms_matrix FOREIGN KEY (matrix_id) REFERENCES public.tenant_legal_matrices(id) ON DELETE CASCADE;


--
-- Name: matrix_norms fk_matrixnorms_norm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matrix_norms
    ADD CONSTRAINT fk_matrixnorms_norm FOREIGN KEY (norm_id) REFERENCES public.legal_norms(id);


--
-- Name: matrix_norms fk_matrixnorms_owner; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matrix_norms
    ADD CONSTRAINT fk_matrixnorms_owner FOREIGN KEY (owner_user_id) REFERENCES public.users(id);


--
-- Name: matrix_norms fk_matrixnorms_sector; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matrix_norms
    ADD CONSTRAINT fk_matrixnorms_sector FOREIGN KEY (sector_id) REFERENCES public.sectors(id);


--
-- Name: matrix_norms fk_matrixnorms_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matrix_norms
    ADD CONSTRAINT fk_matrixnorms_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: matrix_norms fk_matrixnorms_version; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matrix_norms
    ADD CONSTRAINT fk_matrixnorms_version FOREIGN KEY (selected_version_id) REFERENCES public.legal_norm_versions(id);


--
-- Name: chatbot_messages fk_msg_conversation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatbot_messages
    ADD CONSTRAINT fk_msg_conversation FOREIGN KEY (conversation_id) REFERENCES public.chatbot_conversations(id) ON DELETE CASCADE;


--
-- Name: chatbot_messages fk_msg_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chatbot_messages
    ADD CONSTRAINT fk_msg_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: nonconformities fk_nc_ac; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nonconformities
    ADD CONSTRAINT fk_nc_ac FOREIGN KEY (article_compliance_id) REFERENCES public.article_compliance(id);


--
-- Name: nonconformities fk_nc_audititem; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nonconformities
    ADD CONSTRAINT fk_nc_audititem FOREIGN KEY (audit_item_id) REFERENCES public.audit_items(id);


--
-- Name: nonconformities fk_nc_detectedby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nonconformities
    ADD CONSTRAINT fk_nc_detectedby FOREIGN KEY (detected_by) REFERENCES public.users(id);


--
-- Name: nonconformities fk_nc_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nonconformities
    ADD CONSTRAINT fk_nc_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: nonconformities fk_nc_owner; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nonconformities
    ADD CONSTRAINT fk_nc_owner FOREIGN KEY (owner_user_id) REFERENCES public.users(id);


--
-- Name: nonconformities fk_nc_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nonconformities
    ADD CONSTRAINT fk_nc_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: norm_sectors fk_normsectors_article; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.norm_sectors
    ADD CONSTRAINT fk_normsectors_article FOREIGN KEY (article_id) REFERENCES public.legal_articles(id);


--
-- Name: norm_sectors fk_normsectors_norm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.norm_sectors
    ADD CONSTRAINT fk_normsectors_norm FOREIGN KEY (norm_id) REFERENCES public.legal_norms(id) ON DELETE CASCADE;


--
-- Name: norm_sectors fk_normsectors_sector; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.norm_sectors
    ADD CONSTRAINT fk_normsectors_sector FOREIGN KEY (sector_id) REFERENCES public.sectors(id);


--
-- Name: legal_norm_versions fk_normversions_norm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_norm_versions
    ADD CONSTRAINT fk_normversions_norm FOREIGN KEY (norm_id) REFERENCES public.legal_norms(id) ON DELETE CASCADE;


--
-- Name: notifications fk_notif_recipient; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT fk_notif_recipient FOREIGN KEY (recipient_user_id) REFERENCES public.users(id);


--
-- Name: notifications fk_notif_rule; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT fk_notif_rule FOREIGN KEY (rule_id) REFERENCES public.notification_rules(id);


--
-- Name: notifications fk_notif_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT fk_notif_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: notification_rules fk_nr_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_rules
    ADD CONSTRAINT fk_nr_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: notification_templates fk_nt_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT fk_nt_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: obligations fk_obligations_ac; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligations
    ADD CONSTRAINT fk_obligations_ac FOREIGN KEY (article_compliance_id) REFERENCES public.article_compliance(id);


--
-- Name: obligations fk_obligations_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligations
    ADD CONSTRAINT fk_obligations_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: obligations fk_obligations_matrixnorm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligations
    ADD CONSTRAINT fk_obligations_matrixnorm FOREIGN KEY (matrix_norm_id) REFERENCES public.matrix_norms(id);


--
-- Name: obligations fk_obligations_owner; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligations
    ADD CONSTRAINT fk_obligations_owner FOREIGN KEY (owner_user_id) REFERENCES public.users(id);


--
-- Name: obligations fk_obligations_template; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligations
    ADD CONSTRAINT fk_obligations_template FOREIGN KEY (template_id) REFERENCES public.obligation_templates(id);


--
-- Name: obligations fk_obligations_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligations
    ADD CONSTRAINT fk_obligations_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: obligation_templates fk_obltmpl_country; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligation_templates
    ADD CONSTRAINT fk_obltmpl_country FOREIGN KEY (country_id) REFERENCES public.countries(id);


--
-- Name: processes fk_processes_department; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processes
    ADD CONSTRAINT fk_processes_department FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: processes fk_processes_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processes
    ADD CONSTRAINT fk_processes_parent FOREIGN KEY (parent_process_id) REFERENCES public.processes(id);


--
-- Name: processes fk_processes_responsible; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processes
    ADD CONSTRAINT fk_processes_responsible FOREIGN KEY (responsible_user_id) REFERENCES public.users(id);


--
-- Name: processes fk_processes_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processes
    ADD CONSTRAINT fk_processes_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: regulated_equipment fk_re_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regulated_equipment
    ADD CONSTRAINT fk_re_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id) ON DELETE CASCADE;


--
-- Name: regulated_equipment fk_re_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regulated_equipment
    ADD CONSTRAINT fk_re_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: legal_relations fk_relations_srcart; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_relations
    ADD CONSTRAINT fk_relations_srcart FOREIGN KEY (source_article_id) REFERENCES public.legal_articles(id);


--
-- Name: legal_relations fk_relations_srcnorm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_relations
    ADD CONSTRAINT fk_relations_srcnorm FOREIGN KEY (source_norm_id) REFERENCES public.legal_norms(id) ON DELETE CASCADE;


--
-- Name: legal_relations fk_relations_tgtart; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_relations
    ADD CONSTRAINT fk_relations_tgtart FOREIGN KEY (target_article_id) REFERENCES public.legal_articles(id);


--
-- Name: legal_relations fk_relations_tgtnorm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_relations
    ADD CONSTRAINT fk_relations_tgtnorm FOREIGN KEY (target_norm_id) REFERENCES public.legal_norms(id) ON DELETE CASCADE;


--
-- Name: risks_opportunities fk_ro_actionplan; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risks_opportunities
    ADD CONSTRAINT fk_ro_actionplan FOREIGN KEY (action_plan_id) REFERENCES public.action_plans(id);


--
-- Name: risks_opportunities fk_ro_aspect; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risks_opportunities
    ADD CONSTRAINT fk_ro_aspect FOREIGN KEY (environmental_aspect_id) REFERENCES public.environmental_aspects(id);


--
-- Name: risks_opportunities fk_ro_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risks_opportunities
    ADD CONSTRAINT fk_ro_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: risks_opportunities fk_ro_owner; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risks_opportunities
    ADD CONSTRAINT fk_ro_owner FOREIGN KEY (owner_user_id) REFERENCES public.users(id);


--
-- Name: risks_opportunities fk_ro_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risks_opportunities
    ADD CONSTRAINT fk_ro_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: role_permissions fk_roleperm_permission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT fk_roleperm_permission FOREIGN KEY (permission_id) REFERENCES public.permissions(id);


--
-- Name: role_permissions fk_roleperm_role; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT fk_roleperm_role FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: roles fk_roles_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT fk_roles_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: sectors fk_sectors_country; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT fk_sectors_country FOREIGN KEY (country_id) REFERENCES public.countries(id);


--
-- Name: sectors fk_sectors_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT fk_sectors_parent FOREIGN KEY (parent_id) REFERENCES public.sectors(id);


--
-- Name: norm_sync_runs fk_syncruns_source; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.norm_sync_runs
    ADD CONSTRAINT fk_syncruns_source FOREIGN KEY (source_id) REFERENCES public.legal_sources(id);


--
-- Name: tasks fk_tasks_assignee; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_tasks_assignee FOREIGN KEY (assignee_user_id) REFERENCES public.users(id);


--
-- Name: tasks fk_tasks_department; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_tasks_department FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: tasks fk_tasks_obligation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_tasks_obligation FOREIGN KEY (obligation_id) REFERENCES public.obligations(id) ON DELETE CASCADE;


--
-- Name: tasks fk_tasks_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_tasks_parent FOREIGN KEY (parent_task_id) REFERENCES public.tasks(id);


--
-- Name: tasks fk_tasks_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_tasks_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenants fk_tenants_country; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT fk_tenants_country FOREIGN KEY (country_id) REFERENCES public.countries(id);


--
-- Name: tenants fk_tenants_created_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT fk_tenants_created_by FOREIGN KEY (created_by) REFERENCES public.users(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: tenants fk_tenants_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT fk_tenants_parent FOREIGN KEY (parent_tenant_id) REFERENCES public.tenants(id);


--
-- Name: tenants fk_tenants_updated_by; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT fk_tenants_updated_by FOREIGN KEY (updated_by) REFERENCES public.users(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: support_tickets fk_tickets_assignedto; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT fk_tickets_assignedto FOREIGN KEY (assigned_to) REFERENCES public.users(id);


--
-- Name: support_tickets fk_tickets_createdby; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT fk_tickets_createdby FOREIGN KEY (created_by_user_id) REFERENCES public.users(id);


--
-- Name: support_tickets fk_tickets_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT fk_tickets_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: support_ticket_messages fk_tktmsg_author; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_ticket_messages
    ADD CONSTRAINT fk_tktmsg_author FOREIGN KEY (author_user_id) REFERENCES public.users(id);


--
-- Name: support_ticket_messages fk_tktmsg_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_ticket_messages
    ADD CONSTRAINT fk_tktmsg_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: support_ticket_messages fk_tktmsg_ticket; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_ticket_messages
    ADD CONSTRAINT fk_tktmsg_ticket FOREIGN KEY (ticket_id) REFERENCES public.support_tickets(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_userroles_department; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_userroles_department FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: user_roles fk_userroles_facility; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_userroles_facility FOREIGN KEY (facility_id) REFERENCES public.facilities(id);


--
-- Name: user_roles fk_userroles_role; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_userroles_role FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_userroles_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_userroles_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: user_roles fk_userroles_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT fk_userroles_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users fk_users_department; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_department FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: users fk_users_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_tenant FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: action_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.action_plans ENABLE ROW LEVEL SECURITY;

--
-- Name: article_compliance; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.article_compliance ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_items; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_items ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_participants; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_participants ENABLE ROW LEVEL SECURITY;

--
-- Name: audits; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audits ENABLE ROW LEVEL SECURITY;

--
-- Name: chatbot_conversations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chatbot_conversations ENABLE ROW LEVEL SECURITY;

--
-- Name: chatbot_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.chatbot_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: contracts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.contracts ENABLE ROW LEVEL SECURITY;

--
-- Name: declaration_submissions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.declaration_submissions ENABLE ROW LEVEL SECURITY;

--
-- Name: departments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;

--
-- Name: document_versions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_versions ENABLE ROW LEVEL SECURITY;

--
-- Name: documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

--
-- Name: entity_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.entity_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: entity_status_history; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.entity_status_history ENABLE ROW LEVEL SECURITY;

--
-- Name: environmental_aspects; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.environmental_aspects ENABLE ROW LEVEL SECURITY;

--
-- Name: equipment_operators; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.equipment_operators ENABLE ROW LEVEL SECURITY;

--
-- Name: facilities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.facilities ENABLE ROW LEVEL SECURITY;

--
-- Name: facility_norm_assignments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.facility_norm_assignments ENABLE ROW LEVEL SECURITY;

--
-- Name: facility_processes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.facility_processes ENABLE ROW LEVEL SECURITY;

--
-- Name: integration_accounts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.integration_accounts ENABLE ROW LEVEL SECURITY;

--
-- Name: matrix_norms; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.matrix_norms ENABLE ROW LEVEL SECURITY;

--
-- Name: nonconformities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.nonconformities ENABLE ROW LEVEL SECURITY;

--
-- Name: notification_rules; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.notification_rules ENABLE ROW LEVEL SECURITY;

--
-- Name: notification_templates; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.notification_templates ENABLE ROW LEVEL SECURITY;

--
-- Name: notifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

--
-- Name: obligations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.obligations ENABLE ROW LEVEL SECURITY;

--
-- Name: processes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.processes ENABLE ROW LEVEL SECURITY;

--
-- Name: regulated_equipment; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.regulated_equipment ENABLE ROW LEVEL SECURITY;

--
-- Name: risks_opportunities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.risks_opportunities ENABLE ROW LEVEL SECURITY;

--
-- Name: roles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;

--
-- Name: support_ticket_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.support_ticket_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: support_tickets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY;

--
-- Name: tasks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

--
-- Name: action_plans tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.action_plans USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: article_compliance tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.article_compliance USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: audit_items tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.audit_items USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: audit_log tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.audit_log USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: audit_participants tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.audit_participants USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: audits tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.audits USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: chatbot_conversations tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.chatbot_conversations USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: chatbot_messages tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.chatbot_messages USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: contracts tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.contracts USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: declaration_submissions tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.declaration_submissions USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: departments tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.departments USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: document_versions tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.document_versions USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: documents tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.documents USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: entity_documents tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.entity_documents USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: entity_status_history tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.entity_status_history USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: environmental_aspects tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.environmental_aspects USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: equipment_operators tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.equipment_operators USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: facilities tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.facilities USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: facility_norm_assignments tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.facility_norm_assignments USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: facility_processes tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.facility_processes USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: integration_accounts tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.integration_accounts USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: matrix_norms tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.matrix_norms USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: nonconformities tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.nonconformities USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: notification_rules tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.notification_rules USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: notification_templates tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.notification_templates USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: notifications tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.notifications USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: obligations tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.obligations USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: processes tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.processes USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: regulated_equipment tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.regulated_equipment USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: risks_opportunities tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.risks_opportunities USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: roles tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.roles USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: support_ticket_messages tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.support_ticket_messages USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: support_tickets tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.support_tickets USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: tasks tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.tasks USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: tenant_legal_matrices tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.tenant_legal_matrices USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: user_roles tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.user_roles USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: users tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.users USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: tenant_legal_matrices; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tenant_legal_matrices ENABLE ROW LEVEL SECURITY;

--
-- Name: user_roles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict TVBkszhBvDI9XErzstYsbif3MFqaTtSbs0xpPskOd1aoF0qq9SWI1tWcXFWg8du

