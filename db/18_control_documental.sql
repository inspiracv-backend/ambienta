-- ─────────────────────────────────────────────────────────────────────────
-- 18. Control de informacion documentada (RF-102 a RF-106, epica #31)
-- ─────────────────────────────────────────────────────────────────────────
--
-- La capa de evidencias existe desde `01_schema.sql`: `documents`,
-- `document_versions` y `entity_documents`, con almacenamiento abstraido
-- (`storage_provider` + `storage_key`) y vinculo polimorfico. **Lo que no
-- existe es el control documental** que pide ISO 9001 §7.5 y que el cliente
-- nombro directo: "la informacion se maneja por correo y se pierde".
--
-- Medido antes de escribir esto: las tres tablas tienen **cero filas**.
--
-- ## Que falta, requisito por requisito
--
-- **RF-102 — los tipos.** `document_type` admite `evidence`,
-- `declaration_template`, `receipt`, `contract`, `audit`, `email_attachment` y
-- `other`. Son los tipos de *nuestra* operacion, no los del sistema de gestion
-- del cliente: no hay politica, procedimiento, instructivo, formato ni
-- registro.
--
-- **RF-103 — la identificacion.** No hay codigo. Un documento sin codigo no se
-- puede citar en una auditoria, que es justamente para lo que sirve.
--
-- **RF-104 — el ciclo de vida.** `documents.status` es
-- `draft/active/archived/deleted`. Eso describe una fila en una base, no un
-- documento controlado: falta `en_revision`, falta `aprobado`, y `archived` no
-- distingue "lo retiramos" de "lo reemplazo una version nueva".
--
-- **RF-105 — la aprobacion.** No se registra quien aprobo ni cuando, asi que
-- **nada impide usar un borrador como evidencia**. Ese es el agujero que mas
-- importa: una evidencia sin aprobar no sostiene nada ante un fiscalizador, y
-- el sistema hoy la acepta sin decir palabra.
--
-- **RF-106 — los obsoletos.** No hay como marcarlos, y `status` incluye
-- `deleted`, que invita justo a lo contrario de lo que el requisito pide.
--
-- ## La decision de diseno: el ciclo de vida vive en la VERSION
--
-- Un documento controlado tiene un codigo estable y **revisiones que se
-- aprueban de a una**. El "Procedimiento de Manejo de Residuos PR-07" es el
-- mismo documento en su revision 1 y en su revision 4; lo que se aprueba, lo
-- que entra en vigencia y lo que queda obsoleto son las revisiones.
--
-- Por eso:
--
-- - `document_versions` gana su propio estado, su aprobacion y su vigencia
-- - `documents.status` describe al documento entero: vigente mientras tenga una
--   revision aprobada en curso, obsoleto cuando se retira
-- - `documents.current_version_id` apunta a la revision vigente, que ya existia
--
-- Poner el ciclo de vida en el documento obligaria a que aprobar una revision
-- nueva "desaprobara" la anterior, y se perderia el rastro de que la revision 3
-- estuvo vigente entre tales fechas — que es exactamente lo que una auditoria
-- pregunta.
--
-- No hace falta politica RLS ni GRANT nuevos: las tres tablas ya los tienen.
--
-- Idempotente.


-- ── RF-102 · Los tipos del sistema de gestion ────────────────────────────
--
-- Se **agregan** a los que ya habia en vez de reemplazarlos: los existentes
-- son los de nuestra operacion (comprobantes, plantillas, adjuntos de correo)
-- y siguen haciendo falta. Un documento controlado y un comprobante del RETC
-- conviven en la misma tabla porque los dos son archivos con versiones, pero
-- solo el primero lleva ciclo de vida.

ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_document_type_check;

ALTER TABLE documents ADD CONSTRAINT documents_document_type_check
    CHECK (document_type IN (
        -- Los de siempre.
        'evidence', 'declaration_template', 'receipt', 'contract', 'audit',
        'email_attachment', 'other',
        -- Los del sistema de gestion (RF-102).
        'politica', 'procedimiento', 'instructivo', 'formato', 'registro',
        'externo'
    ));

COMMENT ON COLUMN documents.document_type IS
  'Los seis ultimos son documentacion controlada del sistema de gestion '
  '(ISO 9001 §7.5, RF-102). Los otros son archivos de la operacion: un '
  'comprobante no se aprueba ni se revisa, solo se guarda.';


-- ── RF-103 · Codigo, y la fecha de vigencia ──────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'code'
    ) THEN
        ALTER TABLE documents ADD COLUMN code varchar(60);

        COMMENT ON COLUMN documents.code IS
          'Identificacion del documento controlado (RF-103): PR-07, IT-12, '
          'PO-01. Lo elige la empresa segun su propia nomenclatura — imponer '
          'un formato obligaria a renumerar lo que ya tienen. NULL en los '
          'archivos de operacion, que no se citan por codigo.';

        RAISE NOTICE 'documents.code agregada.';
    END IF;
END $$;

-- Unico por empresa **solo cuando hay codigo**: dos documentos controlados no
-- pueden compartir identificacion, y los archivos de operacion no llevan.
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_code
    ON documents (tenant_id, code)
    WHERE deleted_at IS NULL AND code IS NOT NULL;


-- ── RF-104 y RF-105 · Ciclo de vida y aprobacion, en la revision ─────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'document_versions' AND column_name = 'lifecycle_status'
    ) THEN
        ALTER TABLE document_versions
            ADD COLUMN lifecycle_status varchar(20) NOT NULL DEFAULT 'borrador',
            ADD COLUMN approved_at timestamptz,
            ADD COLUMN approved_by uuid,
            ADD COLUMN valid_from date,
            ADD COLUMN valid_to date,
            ADD COLUMN obsoleted_at timestamptz,
            ADD COLUMN obsoleted_reason text;

        ALTER TABLE document_versions
            ADD CONSTRAINT ck_document_versions_lifecycle
            CHECK (lifecycle_status IN (
                'borrador', 'en_revision', 'aprobado', 'vigente', 'obsoleto'
            ));

        -- **Aprobado sin quien ni cuando es una aprobacion que no existe.**
        -- Es la restriccion que sostiene RF-105: sin ella se podria marcar
        -- `aprobado` a mano y la evidencia pasaria la comprobacion sin que
        -- nadie hubiera aprobado nada.
        ALTER TABLE document_versions
            ADD CONSTRAINT ck_document_versions_aprobacion
            CHECK (
                lifecycle_status NOT IN ('aprobado', 'vigente', 'obsoleto')
                OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)
            );

        ALTER TABLE document_versions
            ADD CONSTRAINT fk_dv_approved_by
            FOREIGN KEY (approved_by) REFERENCES users(id);

        RAISE NOTICE 'document_versions: ciclo de vida agregado.';
    ELSE
        RAISE NOTICE 'document_versions.lifecycle_status ya existia; no se toca.';
    END IF;
END $$;

COMMENT ON COLUMN document_versions.lifecycle_status IS
  'RF-104. La revision se aprueba, entra en vigencia y despues queda obsoleta. '
  'El ciclo vive aca y no en `documents` para no perder el rastro de que la '
  'revision 3 estuvo vigente entre tales fechas, que es lo que pregunta una '
  'auditoria.';

COMMENT ON COLUMN document_versions.obsoleted_reason IS
  'RF-106. Por que dejo de regir: la reemplazo la revision N, cambio la norma, '
  'se retiro el proceso. Un obsoleto sin motivo obliga a adivinar si todavia '
  'sirve para algo.';

-- Una sola revision vigente por documento. Sin esto, dos revisiones aprobadas
-- a la vez dejan a la empresa sin saber cual rige — y el `current_version_id`
-- de `documents` apuntaria a una de las dos sin criterio.
--
-- **Sin `deleted_at` en la condicion, y no por olvido:** `document_versions`
-- no tiene esa columna. La tabla es de solo agregar — no hay `deleted_at` ni
-- `updated_at`— y eso ya es lo que RF-106 pide: una revision no se borra ni se
-- reescribe, se marca obsoleta y queda.
CREATE UNIQUE INDEX IF NOT EXISTS uq_document_versions_vigente
    ON document_versions (document_id)
    WHERE lifecycle_status = 'vigente';


-- ── RF-106 · Los obsoletos se conservan ──────────────────────────────────
--
-- `documents.status` admitia `deleted`, que invita justo a lo contrario de lo
-- que el requisito pide. Se reemplaza el CHECK: un documento se retira
-- marcandolo `obsoleto`, y el borrado logico (`deleted_at`) queda para lo que
-- de verdad se dio de baja por error.
--
-- Los valores existentes se mapean antes de cambiar la restriccion, o la
-- migracion falla en cualquier base con datos. Hoy son cero filas, pero la
-- migracion tiene que servir tambien en la del cliente.

UPDATE documents SET status = 'vigente'  WHERE status = 'active';
UPDATE documents SET status = 'borrador' WHERE status = 'draft';
UPDATE documents SET status = 'obsoleto' WHERE status IN ('archived', 'deleted');

ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_status_check;

ALTER TABLE documents ADD CONSTRAINT documents_status_check
    CHECK (status IN ('borrador', 'en_revision', 'vigente', 'obsoleto'));

ALTER TABLE documents ALTER COLUMN status SET DEFAULT 'borrador';

COMMENT ON COLUMN documents.status IS
  'RF-104/RF-106. **No hay `deleted`**: un documento controlado se retira '
  'marcandolo `obsoleto` y se conserva, porque las evaluaciones que lo citan '
  'siguen necesitando saber contra que se evaluaron. El borrado logico queda '
  'para lo dado de baja por error.';

-- La consulta que abre la pantalla: los documentos vigentes de la empresa.
CREATE INDEX IF NOT EXISTS ix_documents_vigentes
    ON documents (tenant_id, document_type)
    WHERE deleted_at IS NULL AND status = 'vigente';
