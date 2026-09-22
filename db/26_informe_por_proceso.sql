-- 26_informe_por_proceso.sql
--
-- El informe de auditoria con matriz por proceso y tasa de cierre (#42,
-- RF-101; design.md §6 del cambio `hallazgos-auditoria-no-conformidades`).
--
-- ## Que faltaba, y no era el endpoint
--
-- **`audit_items` no tiene proceso.** El design dice que las tres primeras
-- columnas de la matriz "son derivables", y no lo son: no hay de donde. Una
-- auditoria sabe que preguntas hizo y que hallazgos salieron, y **no sabe a que
-- proceso pertenece cada pregunta**, asi que no puede decir como quedo ninguno.
--
-- Eso importa mas de lo que parece: el dueno de un proceso no lee la lista de
-- hallazgos de toda la planta, lee la fila de su proceso. Sin la columna, el
-- informe es una lista plana y cada dueno tiene que adivinar cual le toca.
--
-- ## Y por que hacen falta DOS cosas
--
-- La matriz tiene columnas de dos naturalezas distintas, y mezclarlas seria el
-- error:
--
--   derivadas   clausulas auditadas, evidencia revisada, hallazgos
--               -> salen de los items y de los registros de mejora
--   escritas    clasificacion y conclusion del proceso
--               -> las escribe el auditor, no se calculan
--
-- Las derivadas **no se guardan**. Guardar un conteo escrito a mano es la forma
-- mas rapida de que el informe y el sistema digan cosas distintas, y el que
-- miente es siempre el guardado. Las escritas necesitan donde vivir, y esa es
-- `audit_process_results`.
--
-- ## Las tablas nacidas en una migracion no heredan nada
--
-- El bucle de politicas y el `GRANT ON ALL TABLES` de `01_schema.sql` corren una
-- sola vez, al crear el volumen. Esta declara su propia RLS y sus GRANT o queda
-- visible entre empresas.

BEGIN;

-- ── A que proceso pertenece cada pregunta del checklist ─────────────────────
--
-- Nulable a proposito. Una auditoria tiene preguntas que no son de ningun
-- proceso —requisitos generales del sistema de gestion— y forzarlas a uno
-- inventaria una pertenencia. El informe las cuenta aparte, igual que
-- `items_sin_articulo` en la cobertura: lo que no encaja se muestra, no se
-- esconde en una fila cualquiera.
--
-- **La clave foranea no pasa por RLS.** Solo exige que la fila exista, no que
-- sea de esta empresa: quien acepte este id desde el cuerpo tiene que llamar a
-- `routers/_comun.py::validar_visible`.

ALTER TABLE audit_items
    ADD COLUMN IF NOT EXISTS process_id UUID REFERENCES processes(id);

CREATE INDEX IF NOT EXISTS ix_audit_items_process
    ON audit_items (tenant_id, audit_id, process_id) WHERE deleted_at IS NULL;

COMMENT ON COLUMN audit_items.process_id IS
    'Proceso auditado por esta pregunta. NULL = requisito general del sistema '
    'de gestion, que el informe cuenta aparte en vez de asignarlo a la fuerza.';

-- ── El veredicto del auditor sobre cada proceso ─────────────────────────────

CREATE TABLE IF NOT EXISTS audit_process_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    audit_id        UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    process_id      UUID NOT NULL REFERENCES processes(id),

    -- Como quedo el proceso. Lista cerrada porque es lo que se lee de un
    -- vistazo en la matriz, y tres auditores escribiendo la misma idea con tres
    -- redacciones distintas hacen la tabla ilegible justo donde tiene que
    -- resumir. El matiz va en `conclusion`, que es texto libre.
    classification  VARCHAR(40) NOT NULL,
    -- El parrafo del auditor sobre este proceso. Es lo que el dueno del proceso
    -- lee de verdad.
    conclusion      TEXT,
    -- Que se miro. Va escrito y no derivado porque "el registro de calibracion
    -- de marzo" no esta en ninguna tabla: es lo que el auditor tuvo a la vista.
    evidence_reviewed TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by      UUID REFERENCES users(id),
    deleted_at      TIMESTAMPTZ,

    CONSTRAINT ck_apr_classification CHECK (
        classification IN (
            'conforme',
            'conforme_con_observaciones',
            'no_conforme',
            'no_auditado'
        )
    )
);

-- Un proceso tiene una fila por auditoria y no mas: dos veredictos sobre el
-- mismo proceso en la misma auditoria es una matriz que se contradice a si
-- misma, y el informe elegiria uno de los dos sin decirlo.
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_process_results
    ON audit_process_results (audit_id, process_id) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_audit_process_results_audit
    ON audit_process_results (tenant_id, audit_id) WHERE deleted_at IS NULL;

COMMENT ON TABLE audit_process_results IS
    'La parte de la matriz por proceso que el auditor escribe (RF-101). Los '
    'conteos y los hallazgos NO se guardan aca: se derivan, para que el informe '
    'no pueda discrepar del sistema.';

-- ── RLS y permisos ──────────────────────────────────────────────────────────

ALTER TABLE audit_process_results ENABLE ROW LEVEL SECURITY;
-- `FORCE`: sin el, el dueno de la tabla se salta su propia politica, y las
-- tareas que corren como dueno verian todas las empresas.
ALTER TABLE audit_process_results FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON audit_process_results;
CREATE POLICY tenant_isolation ON audit_process_results
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON audit_process_results TO ambienta_app;

COMMIT;
