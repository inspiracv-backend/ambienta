-- ============================================================================
--  30 · Las cinco etapas del registro de mejora, tipadas (RF-97, #38, #43)
-- ============================================================================
--
--  ## Que reemplaza, y por que
--
--  `nonconformities.improvement_stages` es un JSONB provisorio desde el
--  principio, y su propio comentario en `01_schema.sql` lo dice: se puso "para
--  no perder lo que el cliente ya tiene" mientras se decidia el modelo
--  definitivo. Esa decision es #57 y se tomo el 10-sep-2026: **tabla tipada**.
--
--  El motivo no es purismo. Con JSONB el responsable de cada etapa es un texto
--  sin clave foranea —nada impide que apunte a alguien de otra empresa o a
--  nadie— y el generador de avisos tendria que leer dentro del JSON para saber
--  a quien escribirle. Este repositorio ya se quemo con eso: el generador de
--  vencimientos **se saltaba en silencio las obligaciones sin responsable**, 3
--  de 8 en el seed, y nadie se entero porque no fallaba.
--
--  ## Que se migra: nada, y se midio
--
--  Medido el 10-sep contra la base: **cero filas con etapas escritas**. Las 293
--  no conformidades tienen `improvement_stages = '{}'`, y 292 de ellas estan
--  borradas logicamente (residuo de pruebas). O sea que esto **no es una
--  migracion de datos**: es una tabla nueva.
--
--  La columna JSONB **se conserva** y no se borra. Dos motivos: una base de
--  algun entorno podria tener datos que aca no se ven, y quitarla es un paso
--  aparte que se hace cuando se compruebe que nadie la lee. Mientras tanto no
--  estorba — `01_schema.sql` la sigue creando para bases nuevas.
--
--  ## Una fila por etapa y por registro, no un historial
--
--  `UNIQUE (nonconformity_id, kind)`. El bucle de reapertura del diseno
--  —`seguimiento → accion_correctiva` cuando la accion no fue eficaz— vuelve a
--  la misma etapa y la corrige, y **ese ida y vuelta queda en `audit_log`**,
--  que es donde el diseno dice que tiene que quedar. Guardar aca cada pasada
--  seria un segundo historial que se puede contradecir con el primero.
--
--  ## Lo tipado y lo que sigue en JSONB
--
--  Son columnas reales las que alguien **consulta o recorre**:
--
--  | columna | para que |
--  |---|---|
--  | `responsable_user_id` | el aviso por etapa (RF-99), con FK de verdad |
--  | `due_date` | la ventana del cron de avisos |
--  | los cinco tri-estado | el cierre exige `eficaz = true`, no truthy |
--  | `metodologia_id` | el catalogo por empresa de `db/25` |
--
--  Lo especifico de cada etapa —la correccion inmediata, la causa raiz, los
--  cinco porques, la espina de pescado, la descripcion de la accion— va en
--  `datos`, porque **nadie filtra por eso**: se lee entero con la etapa. Poner
--  veinte columnas nulas para que diecisiete esten siempre vacias no tipa nada,
--  solo hace mas ancha la tabla.
--
--  ## Tri-estado y no booleano, y el CHECK lo exige
--
--  Los cinco desplegables del sistema del cliente son `Seleccione… / SI / NO`.
--  Modelarlos como booleano convierte "todavia no lo verifique" en "No", que en
--  tres de las cuatro preguntas es la respuesta **favorable**: el defecto
--  silencioso cerraria la verificacion a favor. Por eso son `boolean` nulables
--  y el cierre compara contra `true`.
--
--  Y solo tienen sentido en `seguimiento`: `ck_etapa_triestado_solo_seguimiento`
--  impide que una correccion inmediata quede diciendo que fue eficaz.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS improvement_stage_entries (
    id                uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid         NOT NULL,
    nonconformity_id  uuid         NOT NULL,

    -- Las cinco de la maquina de estados del diseno, en orden.
    kind              varchar(24)  NOT NULL,

    -- **Quien la ejecuto**, que no es lo mismo que a quien se le asigno.
    -- `nonconformities.responsables` es la asignacion; esto es el hecho. Cuando
    -- no coinciden, esa diferencia misma es informacion.
    --
    -- Nulable: una etapa existe antes de que alguien la ejecute, y esa es
    -- justamente la que hay que avisar.
    responsable_user_id uuid,

    -- Del catalogo por empresa (`db/25`). Solo en el analisis de causa.
    metodologia_id    uuid,

    fecha_ejecucion   date,
    -- Calculada de `improvement_severities.days_to_close` cuando la empresa lo
    -- declara. Mientras ese catalogo tenga los plazos en NULL —hoy los tiene,
    -- a proposito— se sigue pidiendo a mano.
    due_date          date,

    completada_en     timestamptz,

    -- Los cinco tri-estado del seguimiento. Ver la nota de arriba.
    eficaz                      boolean,
    causa_se_repitio            boolean,
    cumplio_proposito           boolean,
    requiere_actualizar_riesgos boolean,
    requiere_cambios_sgc        boolean,

    observaciones     text,
    evidencia_urls    text[]       NOT NULL DEFAULT '{}',
    datos             jsonb        NOT NULL DEFAULT '{}'::jsonb,

    created_at        timestamptz  NOT NULL DEFAULT now(),
    created_by        uuid,
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    updated_by        uuid,
    deleted_at        timestamptz,

    CONSTRAINT ck_etapa_kind CHECK (kind IN (
        'registro', 'correccion', 'analisis_causa', 'accion_correctiva', 'seguimiento'
    )),

    -- Una correccion inmediata no puede quedar diciendo que fue eficaz.
    CONSTRAINT ck_etapa_triestado_solo_seguimiento CHECK (
        kind = 'seguimiento' OR (
            eficaz IS NULL AND causa_se_repitio IS NULL
            AND cumplio_proposito IS NULL
            AND requiere_actualizar_riesgos IS NULL
            AND requiere_cambios_sgc IS NULL
        )
    ),

    -- La metodologia es del analisis de causa y de ninguna otra.
    CONSTRAINT ck_etapa_metodologia_solo_analisis CHECK (
        kind = 'analisis_causa' OR metodologia_id IS NULL
    ),

    -- Completada exige saber cuando se ejecuto: una etapa cerrada sin fecha no
    -- se puede ubicar en el tiempo, y el informe de auditoria ordena por eso.
    CONSTRAINT ck_etapa_completada_con_fecha CHECK (
        completada_en IS NULL OR fecha_ejecucion IS NOT NULL
    )
);

-- Una fila por etapa y por registro. Ver la nota del encabezado.
CREATE UNIQUE INDEX IF NOT EXISTS uq_etapa_por_registro
    ON improvement_stage_entries (nonconformity_id, kind)
    WHERE deleted_at IS NULL;

-- Lo que recorre el cron de avisos: las etapas con plazo y sin completar.
CREATE INDEX IF NOT EXISTS ix_etapas_por_vencer
    ON improvement_stage_entries (due_date)
    WHERE deleted_at IS NULL AND completada_en IS NULL AND due_date IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_etapas_por_responsable
    ON improvement_stage_entries (responsable_user_id)
    WHERE deleted_at IS NULL;

-- ── Claves foraneas ─────────────────────────────────────────────────────────
--
-- **Las FK no pasan por RLS** (CLAUDE.md §4): solo exigen que la fila exista,
-- no que sea de esta empresa. Por eso ademas de estas, el endpoint que reciba
-- un id del cuerpo tiene que llamar a `validar_visible`.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_etapa_tenant') THEN
        ALTER TABLE improvement_stage_entries
            ADD CONSTRAINT fk_etapa_tenant FOREIGN KEY (tenant_id)
            REFERENCES tenants(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_etapa_registro') THEN
        ALTER TABLE improvement_stage_entries
            ADD CONSTRAINT fk_etapa_registro FOREIGN KEY (nonconformity_id)
            REFERENCES nonconformities(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_etapa_responsable') THEN
        ALTER TABLE improvement_stage_entries
            ADD CONSTRAINT fk_etapa_responsable FOREIGN KEY (responsable_user_id)
            REFERENCES users(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_etapa_metodologia') THEN
        ALTER TABLE improvement_stage_entries
            ADD CONSTRAINT fk_etapa_metodologia FOREIGN KEY (metodologia_id)
            REFERENCES improvement_methodologies(id);
    END IF;
END $$;

-- ── RLS y permisos, declarados aca ──────────────────────────────────────────
--
-- **Una tabla nacida en una migracion no hereda nada.** El bucle de politicas y
-- el `GRANT ON ALL TABLES` de `01_schema.sql` corren una sola vez, al crear la
-- base: sin estas cuatro lineas la tabla queda **visible entre empresas** y
-- `ambienta_app` no puede tocarla. Es la trampa que CLAUDE.md documenta primero.

ALTER TABLE improvement_stage_entries ENABLE ROW LEVEL SECURITY;
-- `FORCE`: sin el, el dueno de la tabla se salta su propia politica.
ALTER TABLE improvement_stage_entries FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON improvement_stage_entries;
CREATE POLICY tenant_isolation ON improvement_stage_entries
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());
GRANT SELECT, INSERT, UPDATE, DELETE ON improvement_stage_entries TO ambienta_app;

COMMENT ON TABLE improvement_stage_entries IS
  'Las cinco etapas del tratamiento de un registro de mejora (RF-97). Reemplaza '
  'a nonconformities.improvement_stages, que era JSONB provisorio.';
COMMENT ON COLUMN improvement_stage_entries.responsable_user_id IS
  'Quien EJECUTO la etapa. `nonconformities.responsables` es a quien se le '
  'asigno: cuando no coinciden, esa diferencia es informacion.';
COMMENT ON COLUMN improvement_stage_entries.eficaz IS
  'Tri-estado. NULL = sin verificar, que NO es "no fue eficaz": el cierre exige '
  'true explicito.';
COMMENT ON COLUMN improvement_stage_entries.datos IS
  'Lo especifico de cada etapa, que nadie filtra: correccion inmediata, causa '
  'raiz, cinco porques, espina de pescado, descripcion de la accion.';

COMMIT;
