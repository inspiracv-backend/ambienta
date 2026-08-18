-- ============================================================================
-- 08 — Perfil normativo de la empresa
-- ============================================================================
-- Spec: openspec/changes/normativa-aplicable-por-empresa/specs/normativa-aplicable/spec.md
--
-- El eslabon que faltaba entre el catalogo y la matriz: con que datos de la
-- empresa se decide que normas le tocan.
--
-- NO crea tablas, asi que no hace falta declarar politicas RLS ni GRANT: las
-- columnas heredan los de su tabla. `sectors` ya existe en 01_schema y esta
-- sembrada con las 8 secciones CIIU, incluida `C · Industria manufacturera`.
--
-- ## Lo que este archivo NO agrega, y por que
--
-- La primera version de esta migracion agregaba cuatro columnas a
-- `matrix_norms`. Tres ya existian y se sacaron:
--
--   * `evaluated_version_id` -> ya esta `selected_version_id`, con el
--     comentario "Version congelada usada para evaluar. Sin esto no se puede
--     reconstruir una evaluacion pasada". Es exactamente lo mismo.
--   * `included_by` -> ya esta `created_by`, que es quien creo la fila.
--   * `no_longer_applicable_at` -> ya esta `applicability`, que admite
--     `not_applicable`, con `applicability_reason` para el motivo.
--
-- Tambien estaba ya `matrix_norms.sector_id`: que sector hizo entrar a la
-- norma. Duplicarlas habria dejado dos fuentes de verdad para el mismo dato,
-- que es peor que no tenerlo: la segunda se desactualiza en silencio.
--
-- Idempotente: se puede correr sobre una base nueva y sobre una vieja, las
-- veces que haga falta.
-- ============================================================================

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
--  1. Perfil normativo de la empresa
-- ───────────────────────────────────────────────────────────────────────────
--
-- NULLABLE a proposito. Las empresas que ya existen no tienen perfil, y eso no
-- es un dato faltante que haya que rellenar: es el estado correcto hasta que
-- alguien lo declare. Con NOT NULL y un valor por defecto le inventariamos un
-- sector a cada empresa cargada, y el filtro devolveria normas equivocadas con
-- toda confianza.

ALTER TABLE tenants ADD COLUMN IF NOT EXISTS sector_id smallint;
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS size_bracket varchar(16);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_tenants_sector') THEN
        ALTER TABLE tenants ADD CONSTRAINT fk_tenants_sector
            FOREIGN KEY (sector_id) REFERENCES sectors(id);
    END IF;

    -- El tramo, no el numero de trabajadores. La ley se escribe por tramo
    -- ("mas de 50 trabajadores"), asi que guardar el numero exacto obligaria a
    -- que cada regla reimplemente el umbral. Y el numero cambia cada mes:
    -- nadie lo actualiza, y el filtro daria resultados falsos sin que se note.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_tenants_size_bracket') THEN
        ALTER TABLE tenants ADD CONSTRAINT ck_tenants_size_bracket
            CHECK (size_bracket IS NULL OR size_bracket IN
                  ('micro','pequena','mediana','grande'));
    END IF;
END $$;

COMMENT ON COLUMN tenants.sector_id IS
  'Sector economico (CIIU) con el que se cruza la normativa. NULL = sin perfil '
  'normativo: la empresa existe y no se le calcula normativa aplicable.';
COMMENT ON COLUMN tenants.size_bracket IS
  'Tramo de tamano, no el numero de trabajadores: la normativa se escribe por '
  'tramo y el numero exacto queda viejo apenas se carga.';
COMMENT ON COLUMN tenants.business_activity IS
  'Giro declarado, en texto libre. NO reemplaza a sector_id: el giro ante el '
  'SII no siempre coincide con el sector regulatorio, y este campo se conserva '
  'porque es lo que escribio la persona.';

-- Las consultas del calculo parten del sector.
CREATE INDEX IF NOT EXISTS ix_tenants_sector ON tenants (sector_id)
    WHERE deleted_at IS NULL;

-- ───────────────────────────────────────────────────────────────────────────
--  2. Como entro cada norma a la matriz
-- ───────────────────────────────────────────────────────────────────────────
--
-- Lo unico que faltaba de verdad en `matrix_norms`. Importa porque un
-- recalculo **no puede quitar** lo que alguien agrego a mano: que el calculo
-- no la encuentre no significa que no aplique — puede venir de un contrato o
-- de la RCA de la empresa.

ALTER TABLE matrix_norms ADD COLUMN IF NOT EXISTS inclusion_source varchar(16);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_matrix_norms_inclusion') THEN
        ALTER TABLE matrix_norms ADD CONSTRAINT ck_matrix_norms_inclusion
            CHECK (inclusion_source IS NULL OR inclusion_source IN ('automatic','manual'));
    END IF;
END $$;

COMMENT ON COLUMN matrix_norms.inclusion_source IS
  'automatic = la incluyo el calculo por sector; manual = la agrego una '
  'persona, y `created_by` dice quien. Un recalculo nunca quita las manuales. '
  'NULL = fila anterior a esta migracion, origen desconocido.';

-- ───────────────────────────────────────────────────────────────────────────
--  3. Limpieza de la primera version de esta migracion
-- ───────────────────────────────────────────────────────────────────────────
--
-- Si alguien alcanzo a correr la version que duplicaba columnas, se quitan.
-- Van con IF EXISTS para que sea seguro en una base que nunca las tuvo.

ALTER TABLE matrix_norms DROP COLUMN IF EXISTS evaluated_version_id;
ALTER TABLE matrix_norms DROP COLUMN IF EXISTS included_by;
ALTER TABLE matrix_norms DROP COLUMN IF EXISTS no_longer_applicable_at;
DROP INDEX IF EXISTS ix_matrix_norms_vigentes;

COMMIT;
