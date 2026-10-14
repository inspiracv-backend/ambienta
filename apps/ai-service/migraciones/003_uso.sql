-- Uso del asistente, agregado (SPEC-12): lo que ve el chatbot del Superadmin.
--
-- Una fila por consulta, SIN el texto de la pregunta ni de la respuesta: el equipo de
-- plataforma ve cuánto se usa, cuánto se abstiene y cuánto cuesta, no qué preguntó cada empresa
-- (RF-60: "sin acceso a datos de un tenant salvo permiso explícito").

CREATE TABLE uso_consulta (
    id              bigserial PRIMARY KEY,
    creado_en       timestamptz NOT NULL DEFAULT now(),
    tenant_id       uuid,
    perfil          text NOT NULL,                 -- empresa | plataforma
    modo_busqueda   text,
    herramientas    text[] NOT NULL DEFAULT '{}',
    se_abstuvo      boolean,
    motivo          text,
    tokens_entrada  integer NOT NULL DEFAULT 0,
    tokens_salida   integer NOT NULL DEFAULT 0,
    latencia_ms     integer,
    error           boolean NOT NULL DEFAULT false
);
CREATE INDEX ix_uso_fecha ON uso_consulta (creado_en DESC);

-- El servicio que atiende consultas puede anotar su uso y leerlo, y nada más.
GRANT SELECT, INSERT ON uso_consulta TO ia_consulta;
GRANT USAGE ON SEQUENCE uso_consulta_id_seq TO ia_consulta;
GRANT SELECT ON uso_consulta TO ia_sincronizador;
