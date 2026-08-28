-- 22 · CRM simplificado: empresas, contactos, pipeline y actividades (epica #32)
--
-- ## Que hueco llena, y por que no bastaba lo que habia
--
-- `contracts` une **dos tenants**: `manager_tenant_id` y `client_tenant_id`.
-- O sea que solo se puede registrar una relacion con alguien que **ya es
-- cliente de la plataforma**. Una empresa a la que todavia se le esta
-- vendiendo no cabe en ninguna tabla, asi que el seguimiento comercial vivia
-- fuera del sistema — que es justo lo que esta epica existe para evitar.
--
-- `crm_companies` es esa empresa. Cuando el trato se gana y la empresa entra a
-- la plataforma, `client_tenant_id` la enlaza con su tenant y el trato se
-- promueve a `contracts` (#82). El CRM no reemplaza a `contracts`: lo alimenta.
--
-- ## Las decisiones que conviene conocer
--
-- **Las etapas son una tabla y no un enum.** #78 las pide configurables por
-- empresa: una consultora ambiental y un gestor de residuos no venden igual.
-- Con un CHECK, "configurable" significaria una migracion por cliente.
--
-- **`kind` distingue la etapa de su significado.** Una etapa se puede llamar
-- "Cerrado feliz" o "Firmado"; lo que el sistema necesita saber es si eso
-- cuenta como ganado. Sin esa columna, calcular la tasa de cierre obligaria a
-- comparar nombres escritos por cada empresa.
--
-- **Una actividad cuelga de UNA cosa, con clave foranea de verdad.**
-- `entity_documents` usa `(entity_type, entity_id)` polimorfico, y aca se hace
-- distinto a proposito: son tres padres posibles y conocidos, asi que tres
-- columnas nulables con un CHECK de "exactamente una" dan **integridad
-- referencial real**. Con el par polimorfico, borrar una empresa deja
-- actividades apuntando al vacio y nada lo impide.
--
-- **Perder exige motivo.** Igual que `document_versions.obsoleted_reason`: un
-- trato perdido sin explicacion no ensena nada, y la razon de tener un pipeline
-- es aprender por que se pierde.
--
-- ## RLS y permisos, declarados aca
--
-- `db/01_schema.sql` no es una migracion: su bucle de politicas y su
-- `GRANT ON ALL TABLES` corren **una sola vez**, al crear el volumen. Una tabla
-- que nace aca no los hereda, asi que cada una declara su propia politica y sus
-- GRANT o queda visible entre empresas.
--
-- Idempotente: se puede correr dos veces.

BEGIN;

-- ── Etapas del pipeline ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crm_stages (
    id          uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        varchar(40)   NOT NULL,
    name        varchar(120)  NOT NULL,
    -- El orden en el kanban. `smallint` y no `serial`: reordenar es habitual y
    -- una secuencia no se reordena.
    position    smallint      NOT NULL DEFAULT 0,
    -- Que significa la etapa para el sistema, independiente de como la llame la
    -- empresa. Sin esto, "¿cuantos tratos ganamos?" habria que contestarlo
    -- comparando nombres escritos a mano.
    kind        varchar(8)    NOT NULL DEFAULT 'open'
                CHECK (kind IN ('open', 'won', 'lost')),
    active      boolean       NOT NULL DEFAULT true,
    created_at  timestamptz   NOT NULL DEFAULT now(),
    created_by  uuid,
    updated_at  timestamptz   NOT NULL DEFAULT now(),
    updated_by  uuid,
    deleted_at  timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_crm_stages_code
    ON crm_stages (tenant_id, code) WHERE deleted_at IS NULL;

-- ── Empresas ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crm_companies (
    id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name             varchar(240)  NOT NULL,
    -- Sin `NOT NULL` ni unicidad: a un prospecto se le sigue la pista antes de
    -- tener su RUT, y exigirlo obligaria a inventarlo para poder anotarlo.
    rut              varchar(20),
    industry         varchar(120),
    website          varchar(240),
    -- **El puente hacia `contracts`.** Nulo mientras la empresa no sea cliente
    -- de la plataforma; cuando lo es, esto la enlaza con su tenant y permite
    -- promover el trato ganado a contrato (#82) sin escribir el nombre otra vez.
    client_tenant_id uuid          REFERENCES tenants(id),
    status           varchar(16)   NOT NULL DEFAULT 'prospect'
                     CHECK (status IN ('prospect', 'client', 'inactive')),
    owner_user_id    uuid          REFERENCES users(id),
    notes            text,
    created_at       timestamptz   NOT NULL DEFAULT now(),
    created_by       uuid,
    updated_at       timestamptz   NOT NULL DEFAULT now(),
    updated_by       uuid,
    deleted_at       timestamptz
);

CREATE INDEX IF NOT EXISTS ix_crm_companies_tenant
    ON crm_companies (tenant_id, status) WHERE deleted_at IS NULL;

-- ── Contactos ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crm_contacts (
    id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    crm_company_id  uuid          NOT NULL REFERENCES crm_companies(id) ON DELETE CASCADE,
    full_name       varchar(180)  NOT NULL,
    email           varchar(240),
    phone           varchar(40),
    role_title      varchar(120),
    -- A quien se le escribe por defecto. Sin esto, mandar un correo obliga a
    -- elegir entre cinco personas cada vez.
    is_primary      boolean       NOT NULL DEFAULT false,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    created_by      uuid,
    updated_at      timestamptz   NOT NULL DEFAULT now(),
    updated_by      uuid,
    deleted_at      timestamptz
);

CREATE INDEX IF NOT EXISTS ix_crm_contacts_company
    ON crm_contacts (crm_company_id) WHERE deleted_at IS NULL;

-- Un solo contacto principal por empresa. Dos "principales" no es un dato: es
-- la ausencia de una decision, y la pantalla tendria que elegir uno igual.
CREATE UNIQUE INDEX IF NOT EXISTS uq_crm_contacts_principal
    ON crm_contacts (crm_company_id)
    WHERE is_primary AND deleted_at IS NULL;

-- ── Oportunidades ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crm_deals (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    crm_company_id      uuid          NOT NULL REFERENCES crm_companies(id) ON DELETE CASCADE,
    -- Opcional: hay tratos que arrancan con la empresa y sin persona todavia.
    crm_contact_id      uuid          REFERENCES crm_contacts(id) ON DELETE SET NULL,
    stage_id            uuid          NOT NULL REFERENCES crm_stages(id),
    title               varchar(240)  NOT NULL,
    -- `numeric` y no `float`: el dinero con coma flotante acumula centavos
    -- fantasma, y un pipeline que no cuadra con la propuesta firmada no sirve.
    amount              numeric(14,2),
    currency            varchar(3)    NOT NULL DEFAULT 'CLP',
    owner_user_id       uuid          REFERENCES users(id),
    expected_close_date date,
    closed_at           timestamptz,
    -- Obligatorio al perder, por el CHECK de mas abajo. Mismo criterio que
    -- `document_versions.obsoleted_reason`: la razon de tener un pipeline es
    -- aprender por que se pierde, y un perdido sin motivo no ensena nada.
    lost_reason         text,
    -- El contrato en que termino, cuando se gano y el cliente entro (#82).
    contract_id         uuid          REFERENCES contracts(id),
    created_at          timestamptz   NOT NULL DEFAULT now(),
    created_by          uuid,
    updated_at          timestamptz   NOT NULL DEFAULT now(),
    updated_by          uuid,
    deleted_at          timestamptz
);

CREATE INDEX IF NOT EXISTS ix_crm_deals_stage
    ON crm_deals (tenant_id, stage_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_crm_deals_company
    ON crm_deals (crm_company_id) WHERE deleted_at IS NULL;

-- ── Actividades ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crm_activities (
    id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    kind            varchar(16)   NOT NULL
                    CHECK (kind IN ('call', 'email', 'meeting', 'note', 'task')),
    subject         varchar(240)  NOT NULL,
    body            text,
    occurred_at     timestamptz   NOT NULL DEFAULT now(),
    author_user_id  uuid          REFERENCES users(id),

    -- **Tres columnas y no un par polimorfico.** `entity_documents` usa
    -- `(entity_type, entity_id)`, y aca se hace distinto a proposito: los
    -- padres posibles son tres y conocidos, asi que tres claves foraneas dan
    -- integridad de verdad. Con el par polimorfico, borrar una empresa deja
    -- actividades apuntando al vacio y nada lo impide.
    crm_company_id  uuid          REFERENCES crm_companies(id) ON DELETE CASCADE,
    crm_contact_id  uuid          REFERENCES crm_contacts(id) ON DELETE CASCADE,
    crm_deal_id     uuid          REFERENCES crm_deals(id) ON DELETE CASCADE,

    created_at      timestamptz   NOT NULL DEFAULT now(),
    created_by      uuid,
    updated_at      timestamptz   NOT NULL DEFAULT now(),
    updated_by      uuid,
    deleted_at      timestamptz,

    -- Exactamente uno. Ninguno seria una actividad huerfana que no aparece en
    -- ninguna ficha; dos seria la misma llamada contada dos veces en la linea
    -- de tiempo.
    CONSTRAINT ck_crm_activities_un_solo_padre CHECK (
        (crm_company_id IS NOT NULL)::int
      + (crm_contact_id IS NOT NULL)::int
      + (crm_deal_id    IS NOT NULL)::int = 1
    )
);

CREATE INDEX IF NOT EXISTS ix_crm_activities_deal
    ON crm_activities (crm_deal_id, occurred_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_crm_activities_company
    ON crm_activities (crm_company_id, occurred_at DESC) WHERE deleted_at IS NULL;

-- ── Ganado y perdido: lo que la base exige ──────────────────────────────────
--
-- Se pone como restriccion y no como un `if` del servicio porque un `UPDATE` a
-- mano tambien tiene que respetarlo: un trato marcado perdido sin motivo, por
-- la via que sea, es un dato que no ensena nada.

ALTER TABLE crm_deals DROP CONSTRAINT IF EXISTS ck_crm_deals_perdido_con_motivo;
ALTER TABLE crm_deals ADD  CONSTRAINT ck_crm_deals_perdido_con_motivo
    CHECK (lost_reason IS NULL OR btrim(lost_reason) <> '');

-- ── RLS y permisos ──────────────────────────────────────────────────────────

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'crm_stages', 'crm_companies', 'crm_contacts', 'crm_deals', 'crm_activities'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        -- `FORCE`: sin el, el dueno de la tabla se salta su propia politica, y
        -- las tareas que corren como dueno verian todas las empresas.
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (tenant_id = current_tenant_id()) '
            'WITH CHECK (tenant_id = current_tenant_id())', t);
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO ambienta_app', t);
    END LOOP;
END $$;

-- ── Etapas por defecto, en todas las empresas ───────────────────────────────
--
-- Mismo criterio que `09_roles_por_codigo.sql`: lo que toda empresa necesita
-- para que la pantalla funcione se crea en todas, no solo en la de
-- demostracion. Un pipeline sin etapas no se puede dibujar.
--
-- Son un punto de partida editable, no una verdad: cada empresa las renombra,
-- reordena y agrega las suyas.

INSERT INTO crm_stages (tenant_id, code, name, position, kind)
SELECT t.id, e.code, e.name, e.position, e.kind
  FROM tenants t
 CROSS JOIN (VALUES
        ('prospecto',  'Prospecto',            0, 'open'),
        ('contactado', 'Contactado',           1, 'open'),
        ('propuesta',  'Propuesta enviada',    2, 'open'),
        ('negociacion','En negociación',       3, 'open'),
        ('ganado',     'Ganado',               4, 'won'),
        ('perdido',    'Perdido',              5, 'lost')
    ) AS e(code, name, position, kind)
 WHERE t.deleted_at IS NULL
   AND NOT EXISTS (
       SELECT 1 FROM crm_stages s
        WHERE s.tenant_id = t.id AND s.code = e.code AND s.deleted_at IS NULL
   );

COMMIT;
