-- 28_comentarios.sql
--
-- RF-111 (comentarios con hilo sobre cualquier registro) y RF-112 (menciones
-- con notificacion), issue #74.
--
-- ## Que problema resuelve
--
-- La epica #31 lo dice con las palabras del cliente: *"la informacion se maneja
-- por correo y se pierde, sobre todo la de normativas, RCAs e ISO"*. Lo que se
-- pierde no es el dato: es **la conversacion sobre el dato** — por que se
-- evaluo asi un articulo, quien dijo que la evidencia servia, que se acordo
-- cuando el plazo se corrio. Eso vive hoy en la bandeja de alguien.
--
-- ## Lo que NO se reuso, y por que
--
-- `support_ticket_messages` es lo mas parecido que hay y **es otra cosa**: son
-- los mensajes de un ticket de soporte, con `author_guest_email` para quien
-- escribe sin cuenta y `is_internal` para lo que el cliente no ve.
-- Generalizarla mezclaria una bandeja de atencion con las notas internas sobre
-- un registro de cumplimiento — dos cosas con reglas de visibilidad opuestas.
--
-- ## RLS y GRANT propios
--
-- El bucle de politicas y el `GRANT ON ALL TABLES` de `01_schema.sql` corren
-- **una sola vez**, al crear el volumen. Una tabla nacida en una migracion no
-- los hereda: sin estas lineas las dos quedan visibles entre empresas, que en
-- un sistema donde RLS es la unica barrera no es un descuido, es una fuga.
--
-- Idempotente.

BEGIN;

-- ── Comentarios ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS comments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Polimorfico, igual que `entity_documents`, y **comprobado por el mismo
    -- mapa**: `services/vinculos_de_documentos.py::ANCLAJES`. Sin clave
    -- foranea, porque apunta a trece tablas segun el tipo.
    --
    -- Deliberadamente NO se repite la lista de tipos aca: el CHECK vive en
    -- `entity_documents` y una prueba lo compara contra el mapa. Dos listas
    -- serian dos cosas que mantener iguales, y este archivo ya sabe como
    -- termina eso.
    entity_type VARCHAR(40) NOT NULL,
    entity_id   UUID        NOT NULL,

    -- **El autor es obligatorio.** Un comentario sin autor en un registro que
    -- se exporta a un auditor no sirve, y atribuirselo al primer administrador
    -- de la empresa —la salida comoda— dejaria escrito que esa persona dijo
    -- algo que no dijo. Por eso el endpoint responde 409 sin sesion
    -- identificada, igual que aprobar una revision documental.
    author_user_id UUID NOT NULL REFERENCES users(id),

    body        TEXT NOT NULL CHECK (length(btrim(body)) > 0),

    -- El hilo es de **un solo nivel**: una respuesta cuelga de un comentario
    -- raiz y no de otra respuesta. Postgres no puede exigirlo en un CHECK
    -- —no mira la fila del padre— asi que lo exige `services/comentarios.py`,
    -- y hay una prueba que lo rompe a proposito.
    parent_id   UUID REFERENCES comments(id),

    -- **Se expone.** Un comentario editado despues de que alguien lo respondio
    -- cambia lo que quedo escrito, y quien lo lea tiene que poder saberlo.
    edited_at   TIMESTAMPTZ,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  UUID,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  UUID,
    deleted_at  TIMESTAMPTZ,

    -- Un comentario no puede ser su propia respuesta.
    CONSTRAINT ck_comments_no_es_su_padre CHECK (parent_id IS NULL OR parent_id <> id)
);

COMMENT ON TABLE comments IS
    'Conversacion sobre un registro (RF-111). Polimorfica como entity_documents '
    'y comprobada por el mismo mapa ANCLAJES. Hilo de un solo nivel, exigido en '
    'el servicio porque un CHECK no puede mirar la fila del padre.';

CREATE INDEX IF NOT EXISTS ix_comments_entidad
    ON comments (entity_type, entity_id, created_at)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_comments_hilo
    ON comments (parent_id) WHERE parent_id IS NOT NULL;

-- ── Menciones ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS comment_mentions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- **Lleva `tenant_id` aunque se derive del comentario.** Sin la columna no
    -- hay politica de RLS que escribir sobre esta tabla, y una tabla sin
    -- politica donde RLS es la unica barrera no es una optimizacion: es un
    -- agujero.
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    comment_id  UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id),

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Mencionar dos veces a la misma persona en un comentario es una sola
    -- mencion. Sin esto, "@juan, avisale a @juan" le manda dos avisos.
    CONSTRAINT uq_comment_mentions UNIQUE (comment_id, user_id)
);

COMMENT ON TABLE comment_mentions IS
    'A quien se menciono en un comentario (RF-112). Es una fila y no un `@` '
    'dentro del texto: buscarlo en la cadena falla con nombres compuestos y '
    'con dos personas del mismo nombre, y falla en silencio — la notificacion '
    'simplemente no sale.';

CREATE INDEX IF NOT EXISTS ix_comment_mentions_usuario
    ON comment_mentions (user_id, created_at);

-- ── RLS y permisos ──────────────────────────────────────────────────────────

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['comments', 'comment_mentions'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        -- `FORCE`: sin el, el dueno de la tabla se salta su propia politica.
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

COMMIT;
