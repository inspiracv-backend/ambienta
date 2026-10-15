-- Esquema de la base de conocimiento (SPEC-03).
--
-- Datos derivados del backend: se pueden borrar y reconstruir con la sincronización. Los ids
-- son los UUID del backend; acá no se inventa ninguno.
--
-- :dimension la reemplaza migrar.py con DIMENSION_EMBEDDINGS. Cambiarla es reindexar.

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Versiones indexadas
-- ---------------------------------------------------------------------------

CREATE TABLE version_norma (
    id               uuid PRIMARY KEY,            -- norm_version_id del backend
    norm_id          uuid NOT NULL,
    tenant_id        uuid,                        -- null = catálogo público (D-05)
    norm_type        text NOT NULL,
    norm_number      text,
    clave_norma      text,                        -- "ley/19300", "ds/40": para la búsqueda exacta
    titulo           text NOT NULL,
    valid_from       date,
    valid_to         date,                        -- null = todavía rige
    is_current       boolean NOT NULL,
    content_hash     text NOT NULL,
    official_url     text,
    sincronizado_en  timestamptz NOT NULL DEFAULT now()
);

-- Una sola versión indexada por norma: la vigente (decisión D del plan).
CREATE UNIQUE INDEX uq_version_por_norma ON version_norma (norm_id);
CREATE INDEX ix_version_clave ON version_norma (clave_norma);


-- ---------------------------------------------------------------------------
-- Fragmentos
-- ---------------------------------------------------------------------------

CREATE TABLE fragmento (
    id                bigserial PRIMARY KEY,
    article_id        uuid NOT NULL,              -- id del artículo en el backend
    version_id        uuid NOT NULL REFERENCES version_norma(id) ON DELETE CASCADE,
    norm_id           uuid NOT NULL,
    tenant_id         uuid,
    article_type      text NOT NULL,
    article_number    text,
    numero_normal     text,                       -- "10 bis", "1 transitorio": para comparar
    parte             int  NOT NULL DEFAULT 1,
    total_partes      int  NOT NULL DEFAULT 1,
    ruta              text NOT NULL,              -- D-02
    texto             text NOT NULL,
    embedding         vector(:dimension) NOT NULL,
    modelo_embedding  text NOT NULL,
    busqueda          tsvector GENERATED ALWAYS AS (
                          to_tsvector('spanish', coalesce(ruta, '') || ' ' || texto)
                      ) STORED,
    UNIQUE (article_id, parte)
);

CREATE INDEX ix_fragmento_embedding ON fragmento USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_fragmento_busqueda  ON fragmento USING gin (busqueda);
CREATE INDEX ix_fragmento_cita      ON fragmento (norm_id, numero_normal);
CREATE INDEX ix_fragmento_tenant    ON fragmento (tenant_id) WHERE tenant_id IS NOT NULL;


-- ---------------------------------------------------------------------------
-- Estado de la sincronización
-- ---------------------------------------------------------------------------

CREATE TABLE sincronizacion (
    fuente             text PRIMARY KEY,
    updated_at_maximo  timestamptz,               -- el máximo visto, no la hora de la corrida
    ultima_corrida     timestamptz,
    resultado          jsonb
);


-- ---------------------------------------------------------------------------
-- Aislamiento (D-04). RLS es la barrera, no el WHERE del código.
-- ---------------------------------------------------------------------------

ALTER TABLE version_norma ENABLE ROW LEVEL SECURITY;
ALTER TABLE fragmento     ENABLE ROW LEVEL SECURITY;

-- Lectura: lo público y lo de la empresa fijada en la transacción. Sin empresa fijada,
-- current_setting devuelve '' y nullif lo vuelve NULL: no ve nada privado.
CREATE POLICY lectura_version ON version_norma FOR SELECT TO ia_consulta
    USING (tenant_id IS NULL OR tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY lectura_fragmento ON fragmento FOR SELECT TO ia_consulta
    USING (tenant_id IS NULL OR tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

-- El sincronizador solo toca el catálogo público.
CREATE POLICY sincroniza_version ON version_norma FOR ALL TO ia_sincronizador
    USING (tenant_id IS NULL) WITH CHECK (tenant_id IS NULL);
CREATE POLICY sincroniza_fragmento ON fragmento FOR ALL TO ia_sincronizador
    USING (tenant_id IS NULL) WITH CHECK (tenant_id IS NULL);

GRANT SELECT ON version_norma, fragmento, sincronizacion TO ia_consulta;
GRANT SELECT, INSERT, UPDATE, DELETE ON version_norma, fragmento, sincronizacion TO ia_sincronizador;
GRANT USAGE ON SEQUENCE fragmento_id_seq TO ia_sincronizador;
