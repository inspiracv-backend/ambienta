-- 25_catalogos_de_mejora.sql
--
-- Los catalogos del registro de mejora son **convencion de cada empresa**, no
-- normativa (#41, RF-100; design.md §4 del cambio
-- `hallazgos-auditoria-no-conformidades`, decision S-14).
--
-- Hoy la escala de severidad es un CHECK con `minor | major | critical`, o sea
-- que es la misma para todos y solo existe en ingles. La entrevista con el
-- cliente mostro que ellos dicen `Alta` y `Mayor`, y que otra empresa usa otra
-- escala. Sin esta tabla, el segundo cliente obliga a un cambio de esquema.
--
-- ## Que NO hace esta migracion, y por que
--
-- **No toca `nonconformities.severity` ni su CHECK.** Cambiar la columna por
-- una clave foranea al catalogo es un paso aparte y mas riesgoso: hay filas
-- escritas, el frontend traduce `minor|major|critical` en
-- `CRITICIDAD_POR_SEVERITY`, y la escala definitiva es una de las tres
-- decisiones abiertas (#57). El catalogo se monta **encima** del CHECK: la
-- empresa renombra y ordena sus niveles, y la API exige que el valor escrito
-- este activo en su catalogo. Son dos barreras, no una en reemplazo de otra.
--
-- **No trae los plazos por etapa.** `plazosPorDefectoDias` del design es por
-- etapa del tratamiento, y las etapas tipadas todavia no existen —
-- `improvement_stages` sigue siendo JSONB provisorio, y su modelo definitivo
-- depende de #57. Una tabla de configuracion para algo que nadie lee todavia
-- es el patron que este repositorio ya conoce: codigo escrito, probado y sin
-- un solo llamador. Entra cuando entren las etapas.
--
-- Lo que si trae es el plazo **por nivel de severidad**, que tiene consumidor
-- hoy: `nonconformities.due_date` existe desde el principio y **nadie la
-- calcula** — se acepta del cuerpo o se deja vacia. O sea que "una critica se
-- cierra en 15 dias" es una regla que la empresa tiene en la cabeza y el
-- sistema no aplica.
--
-- ## Y por que los plazos nacen en NULL
--
-- Sembrar 60/30/15 dias seria inventar el compromiso de la empresa. Un plazo
-- equivocado en un sistema de cumplimiento no es un dato feo: produce una fecha
-- limite falsa, y la empresa cree que va a tiempo. Es el mismo criterio que la
-- `periodicidad` vacia de `retc_systems` y que el repositorio de plantillas.
--
-- Con `days_to_close` en NULL, `due_date` se sigue pidiendo a mano, igual que
-- hoy. En cuanto la empresa declara sus plazos, el sistema los calcula.
--
-- ## Las tablas nacidas en una migracion no heredan nada
--
-- El bucle de politicas y el `GRANT ON ALL TABLES` de `01_schema.sql` corren
-- una sola vez, al crear el volumen. Cada tabla de aca declara su propia RLS y
-- sus propios GRANT o queda visible entre empresas.

BEGIN;

-- ── Escala de severidad por empresa ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS improvement_severities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- El valor que se escribe en `nonconformities.severity`. Mientras el CHECK
    -- de esa columna siga vigente, los codigos utiles son los suyos.
    code            VARCHAR(40) NOT NULL,
    -- Lo que ve la persona. Es la mitad del sentido de esta tabla: la empresa
    -- que dice "Mayor" deja de leer "major".
    label           VARCHAR(80) NOT NULL,
    -- De mas leve a mas grave. No lleva restriccion de unicidad, igual que
    -- `crm_stages.position`: reordenar con una unica exige pasos intermedios.
    rank            SMALLINT NOT NULL DEFAULT 0,
    -- Dias para cerrar un hallazgo de este nivel. **NULL = la empresa no lo
    -- declaro**, y entonces nadie calcula la fecha limite. Ver el encabezado.
    days_to_close   SMALLINT,
    active          BOOLEAN NOT NULL DEFAULT TRUE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by      UUID REFERENCES users(id),
    deleted_at      TIMESTAMPTZ,

    CONSTRAINT ck_severity_label_no_vacia CHECK (btrim(label) <> ''),
    CONSTRAINT ck_severity_code_no_vacio  CHECK (btrim(code) <> ''),
    -- Cero dias no es "sin plazo", es un plazo imposible. "Sin plazo" es NULL.
    CONSTRAINT ck_severity_plazo_positivo
        CHECK (days_to_close IS NULL OR days_to_close > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_improvement_severities_code
    ON improvement_severities (tenant_id, code) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_improvement_severities_tenant
    ON improvement_severities (tenant_id, rank) WHERE deleted_at IS NULL;

COMMENT ON TABLE improvement_severities IS
    'Escala de severidad de cada empresa (RF-100). Se monta encima del CHECK de '
    'nonconformities.severity, no lo reemplaza.';
COMMENT ON COLUMN improvement_severities.days_to_close IS
    'Dias para cerrar. NULL significa que la empresa no declaro plazo: nadie '
    'calcula due_date. Sembrar un numero seria inventarle el compromiso.';

-- ── Metodologias de analisis de causa ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS improvement_methodologies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    code            VARCHAR(40) NOT NULL,
    name            VARCHAR(120) NOT NULL,
    -- **La forma decide que datos exige el analisis**, y por eso es una lista
    -- cerrada y no texto: con `cinco_porques` hacen falta las respuestas
    -- encadenadas, con `espina_pescado` las categorias. Una empresa puede
    -- llamar a su metodologia como quiera; lo que no puede inventar es una
    -- forma que el sistema no sabe pedir ni mostrar.
    shape           VARCHAR(30) NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT TRUE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by      UUID REFERENCES users(id),
    deleted_at      TIMESTAMPTZ,

    CONSTRAINT ck_methodology_name_no_vacio CHECK (btrim(name) <> ''),
    CONSTRAINT ck_methodology_code_no_vacio CHECK (btrim(code) <> ''),
    CONSTRAINT ck_methodology_shape CHECK (
        shape IN ('cinco_porques', 'espina_pescado', 'texto_libre')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_improvement_methodologies_code
    ON improvement_methodologies (tenant_id, code) WHERE deleted_at IS NULL;

COMMENT ON TABLE improvement_methodologies IS
    'Metodologias de analisis de causa de cada empresa (RF-100, RF-35).';

-- ── Con que metodologia se analizo cada hallazgo ────────────────────────────
--
-- Sin esta columna el catalogo de metodologias no tendria consumidor: seria una
-- tabla que se puede llenar y que nada lee. `root_cause_answers` ya guarda las
-- respuestas, pero no con que metodo se llegaron a ellas — y las respuestas de
-- un Ishikawa no se leen igual que las de un 5 porques.
--
-- Va por `id` y no por codigo: una clave foranea compuesta a `(tenant_id, code)`
-- necesitaria un unico **no parcial**, y el que hay excluye las filas borradas
-- logicamente. Con el id, borrar una metodologia usada falla, que es lo que
-- corresponde.
--
-- Ojo: **la clave foranea no pasa por RLS**. Solo exige que la fila exista, no
-- que sea de esta empresa. Quien acepte este id desde el cuerpo tiene que
-- llamar a `routers/_comun.py::validar_visible`, como el resto.

ALTER TABLE nonconformities
    ADD COLUMN IF NOT EXISTS root_cause_methodology_id UUID
        REFERENCES improvement_methodologies(id);

COMMENT ON COLUMN nonconformities.root_cause_methodology_id IS
    'Con que metodologia del catalogo de la empresa se analizo la causa raiz.';

-- ── RLS y permisos ──────────────────────────────────────────────────────────

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'improvement_severities', 'improvement_methodologies'
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

-- ── Catalogos por defecto, en todas las empresas ────────────────────────────
--
-- Mismo criterio que `22_crm.sql` y `09_roles_por_codigo.sql`: lo que toda
-- empresa necesita para que la pantalla funcione se crea en todas.
--
-- **Y con la leccion de `22_crm.sql` aprendida:** ese `CROSS JOIN tenants` corre
-- al aplicar la migracion, asi que sembro a las empresas que existian ese dia y
-- **ninguna empresa creada despues quedo con etapas**. Aca pasa lo mismo, y por
-- eso `POST /tenants/` tambien siembra estos catalogos, en la misma transaccion
-- del alta. Una prueba lee este archivo y exige que las dos listas coincidan.
--
-- Los codigos de severidad son los tres del CHECK vigente. Las etiquetas van en
-- espanol, que es la mitad del punto. Los plazos van vacios: ver el encabezado.

INSERT INTO improvement_severities (tenant_id, code, label, rank)
SELECT t.id, s.code, s.label, s.rank
  FROM tenants t
 CROSS JOIN (VALUES
        ('minor',    'Menor',   1),
        ('major',    'Mayor',   2),
        ('critical', 'Crítica', 3)
    ) AS s(code, label, rank)
 WHERE t.deleted_at IS NULL
   AND NOT EXISTS (
       SELECT 1 FROM improvement_severities x
        WHERE x.tenant_id = t.id AND x.code = s.code AND x.deleted_at IS NULL
   );

-- Las tres formas que el sistema sabe pedir. No son invencion: los 5 porques y
-- el Ishikawa son las dos herramientas que la norma y la entrevista nombran, y
-- la tercera existe para el analisis que no sigue ninguna de las dos.

INSERT INTO improvement_methodologies (tenant_id, code, name, shape)
SELECT t.id, m.code, m.name, m.shape
  FROM tenants t
 CROSS JOIN (VALUES
        ('cinco_porques', '5 ¿Por qué?',                        'cinco_porques'),
        ('ishikawa',      'Diagrama de Ishikawa (causa-efecto)', 'espina_pescado'),
        ('descriptivo',   'Análisis descriptivo',                'texto_libre')
    ) AS m(code, name, shape)
 WHERE t.deleted_at IS NULL
   AND NOT EXISTS (
       SELECT 1 FROM improvement_methodologies x
        WHERE x.tenant_id = t.id AND x.code = m.code AND x.deleted_at IS NULL
   );

COMMIT;
