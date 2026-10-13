-- ============================================================================
--  34 · Las salidas que deja la verificacion, comprometidas (ISO 9001 10.2.1)
-- ============================================================================
--
--  ## Que hueco llena
--
--  El seguimiento de un registro de mejora tiene dos preguntas tri-estado que
--  son **salidas reglamentarias**: si hay que actualizar los riesgos y
--  oportunidades (10.2.1 e) y si hay que hacer cambios al sistema de gestion
--  (10.2.1 f). Hasta el 4-oct-2026 eran dos casillas y nada mas: alguien
--  marcaba "Si", cerraba el registro, y **el sistema no volvia a mencionarlo
--  nunca**. Es exactamente el hallazgo que levanta un auditor cuando revisa la
--  eficacia del propio sistema de gestion.
--
--  El spec de `gestion-mejoras` lo pedia desde su primera version: "las salidas
--  que la verificacion deja abiertas quedan como compromisos con responsable y
--  plazo, y descartarlas exige justificacion".
--
--  ## Por que una tabla y no el JSONB que la pantalla ya tenia
--
--  `packages/shared` modela la salida y el panel la guardaba dentro de
--  `improvement_stage_entries.datos.salidas`. Es el mismo JSONB del que ya se
--  salio con las etapas (#57): el responsable queda como texto sin clave
--  foranea, y **no hay forma de listar lo que el sistema de gestion debe** —que
--  es justamente la pregunta que esto responde—. Medido el 4-oct: cero filas
--  con salidas escritas ahi, asi que no hay datos que migrar.
--
--  Los tres tipos son los que la pantalla ya nombraba: la matriz de riesgos y
--  oportunidades (10.2.1 e), la matriz FODA (ISO 9001 4.1, que la revision
--  anual actualiza) y un documento del sistema de gestion (10.2.1 f).
--
--  ## Tres decisiones que conviene no invertir
--
--  1. **Una fila por salida y por registro** (`uq_compromiso_por_registro`). Si
--     el seguimiento se repite —porque la accion no fue eficaz y el registro
--     volvio a tratamiento— se reusa el compromiso que ya existe en vez de
--     acumular duplicados de la misma promesa.
--  2. **Descartar exige justificacion, y lo exige la base.** Sin el CHECK, la
--     salida se podria "cerrar" con un clic y el registro de por que se
--     descarto quedaria en la memoria de alguien.
--  3. **El compromiso sobrevive al cierre del registro.** No bloquea cerrar:
--     bloquear obligaria a dejar el registro abierto por una tarea que es de
--     otro plazo. Lo que no puede pasar es que desaparezca de la vista, y para
--     eso esta el indice de pendientes.
--
--  Responsable y fecha nacen vacios porque al marcar la casilla todavia no se
--  saben, y inventarlos es lo que este repositorio ya aprendio a no hacer con
--  los plazos del catalogo de severidades. Lo que si exige el cierre del
--  registro es que cada compromiso pendiente tenga los dos: un compromiso sin
--  responsable ni fecha no se le avisa a nadie, que es el defecto original con
--  otro nombre.
--
--  Tabla nueva: trae **su propia politica RLS y sus GRANT**. El bucle de
--  politicas y el `GRANT ON ALL TABLES` de `01_schema.sql` corren una sola vez.
--
--  Idempotente.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS improvement_commitments (
    id                   uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid         NOT NULL REFERENCES tenants (id),
    nonconformity_id     uuid         NOT NULL REFERENCES nonconformities (id) ON DELETE CASCADE,
    -- De que verificacion salio. Nulable: si la etapa se retira, el compromiso
    -- sigue valiendo — lo que se prometio no depende de la fila que lo origino.
    stage_entry_id       uuid         REFERENCES improvement_stage_entries (id) ON DELETE SET NULL,

    kind                 varchar(32)  NOT NULL,
    descripcion          text,
    status               varchar(16)  NOT NULL DEFAULT 'pendiente',
    responsable_user_id  uuid         REFERENCES users (id),
    due_date             date,
    justificacion        text,
    completada_en        timestamptz,

    created_at           timestamptz  NOT NULL DEFAULT now(),
    created_by           uuid,
    updated_at           timestamptz  NOT NULL DEFAULT now(),
    updated_by           uuid,
    deleted_at           timestamptz,

    CONSTRAINT ck_compromiso_kind CHECK (kind IN (
        'matriz_riesgos', 'matriz_foda', 'documento_sgc'
    )),
    CONSTRAINT ck_compromiso_status CHECK (status IN ('pendiente', 'ejecutada', 'descartada')),

    -- Descartar una salida reglamentaria exige decir por que.
    CONSTRAINT ck_compromiso_descartado_con_motivo CHECK (
        status <> 'descartada'
        OR (justificacion IS NOT NULL AND length(btrim(justificacion)) > 0)
    ),

    -- Ejecutada o descartada tiene fecha de cierre; pendiente no.
    CONSTRAINT ck_compromiso_cerrado_con_fecha CHECK (
        (status = 'pendiente' AND completada_en IS NULL)
        OR (status <> 'pendiente' AND completada_en IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_compromiso_por_registro
    ON improvement_commitments (nonconformity_id, kind)
    WHERE deleted_at IS NULL;

-- Las salidas que el sistema de gestion todavia debe: lo que la pantalla lista
-- y lo que un auditor pregunta.
CREATE INDEX IF NOT EXISTS ix_compromisos_pendientes
    ON improvement_commitments (tenant_id, due_date)
    WHERE deleted_at IS NULL AND status = 'pendiente';

ALTER TABLE improvement_commitments ENABLE ROW LEVEL SECURITY;
-- `FORCE`: sin el, el dueno de la tabla se salta su propia politica.
ALTER TABLE improvement_commitments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON improvement_commitments;
CREATE POLICY tenant_isolation ON improvement_commitments
    USING (tenant_id = current_setting('ambienta.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('ambienta.tenant_id', true)::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON improvement_commitments TO ambienta_app;

COMMENT ON TABLE improvement_commitments IS
  'ISO 9001 10.2.1 e y f: lo que la verificacion de eficacia deja comprometido, con responsable y plazo.';

COMMENT ON COLUMN improvement_commitments.kind IS
  'matriz_riesgos (10.2.1 e), matriz_foda (4.1) o documento_sgc (10.2.1 f).';

COMMIT;
