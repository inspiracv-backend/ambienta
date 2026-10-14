-- Índice de documentos privados y estado durable de los procesos AI.
-- Se instala en la base ambienta existente; los fragmentos públicos y privados
-- viven en el mismo PostgreSQL/pgvector.

CREATE TABLE IF NOT EXISTS documento_fragmento (
    id              bigserial PRIMARY KEY,
    tenant_id       uuid NOT NULL,
    document_id     uuid NOT NULL,
    version_id      uuid NOT NULL,
    chunk_no        integer NOT NULL,
    titulo          text NOT NULL,
    contenido       text NOT NULL,
    checksum_sha256 text NOT NULL,
    embedding       vector(:dimension) NOT NULL,
    creado_en       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, document_id, version_id, chunk_no)
);
CREATE INDEX IF NOT EXISTS ix_documento_fragmento_tenant
    ON documento_fragmento (tenant_id, document_id, version_id);
CREATE INDEX IF NOT EXISTS ix_documento_fragmento_embedding
    ON documento_fragmento USING hnsw (embedding vector_cosine_ops);

ALTER TABLE documento_fragmento ENABLE ROW LEVEL SECURITY;
ALTER TABLE documento_fragmento FORCE ROW LEVEL SECURITY;
CREATE POLICY documento_fragmento_lectura ON documento_fragmento FOR SELECT TO ia_consulta
    USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY documento_fragmento_escritura ON documento_fragmento FOR ALL TO ia_sincronizador
    USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
GRANT SELECT ON documento_fragmento TO ia_consulta;
GRANT SELECT, INSERT, UPDATE, DELETE ON documento_fragmento TO ia_sincronizador;
GRANT USAGE, SELECT ON SEQUENCE documento_fragmento_id_seq TO ia_sincronizador;

CREATE TABLE IF NOT EXISTS ai_job_estado (
    nombre          text PRIMARY KEY,
    estado          text NOT NULL CHECK (estado IN ('ejecutando', 'ok', 'error')),
    iniciado_en     timestamptz,
    finalizado_en   timestamptz,
    elementos       integer NOT NULL DEFAULT 0,
    detalle         text,
    actualizado_en  timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON ai_job_estado TO ia_consulta;
GRANT SELECT, INSERT, UPDATE ON ai_job_estado TO ia_sincronizador;
