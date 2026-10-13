-- =============================================================================
-- 37 · La evaluacion de un articulo es evidencia: no se borra
-- =============================================================================
-- **Decision D del plan de cierre, tomada el 13-oct-2026.**
--
-- `uq_article_compliance` era un `CONSTRAINT UNIQUE`, y un constraint en
-- Postgres **no admite `WHERE`**: cubria tambien las filas con `deleted_at`. La
-- consecuencia, medida: una evaluacion borrada deja su articulo con **409 para
-- siempre**, porque la fila retirada sigue ocupando la combinacion. En esta base
-- habia **9 filas borradas** bloqueando sus articulos.
--
-- ## Lo que se decidio, que son dos cosas
--
-- 1. **La API deja de permitir el borrado** (403 `evaluacion_es_evidencia`). Una
--    evaluacion dice que se reviso un articulo, con que resultado y cuando: es
--    la respuesta de la empresa ante una fiscalizacion del periodo en que se
--    hizo. Lo que hace falta no es borrar, es **reevaluar** —`/evaluate`, que
--    deja el rastro— o **marcar el articulo como no aplicable**, y las dos cosas
--    ya existen. Misma logica por la que `audit_log` no se puede corregir.
-- 2. **El indice se vuelve parcial igual**, aunque la API ya no borre. Las filas
--    retiradas de limpiezas pasadas existen y hoy bloquean recreaciones
--    legitimas, y un borrado por SQL —una migracion, una reparacion a mano—
--    seguira siendo posible. Que el indice sea correcto no depende de que la
--    capa de arriba se porte bien.
--
-- ## El nombre cambia, y es a proposito
--
-- El indice se llama `uq_evaluacion_del_articulo` y no reusa
-- `uq_article_compliance`. **`db/05` tiene un bloque que re-crea el constraint
-- si no lo encuentra en `pg_constraint`**, y con el nombre reusado ese bloque
-- fallaria —ya existe una relacion con ese nombre— o, peor, volveria a poner el
-- constraint no-parcial y con el el 409 permanente. Con nombres distintos,
-- aplicar la lista en orden (05 antes que 37) termina en el estado correcto, que
-- es lo que hacen los dos compose, `db/run.sh` y CI.
--
-- Idempotente.
-- =============================================================================

BEGIN;

-- Antes de crear el indice parcial: que no haya duplicados **entre las filas
-- vivas**. Si los hubiera, el `CREATE UNIQUE INDEX` fallaria con un mensaje
-- sobre una clave duplicada que no dice que hacer. Medido el 13-oct: 0.
DO $$
DECLARE duplicados bigint;
BEGIN
    SELECT count(*) INTO duplicados FROM (
        SELECT matrix_norm_id, article_id, facility_id
        FROM article_compliance
        WHERE deleted_at IS NULL
        GROUP BY 1, 2, 3
        HAVING count(*) > 1
    ) d;

    IF duplicados > 0 THEN
        RAISE EXCEPTION
            'Hay % combinaciones duplicadas entre las evaluaciones vigentes. '
            'Resolverlas antes de aplicar la unicidad parcial: SELECT '
            'matrix_norm_id, article_id, facility_id, count(*) FROM '
            'article_compliance WHERE deleted_at IS NULL GROUP BY 1,2,3 HAVING '
            'count(*) > 1;', duplicados;
    END IF;
END $$;

ALTER TABLE article_compliance DROP CONSTRAINT IF EXISTS uq_article_compliance;

-- `NULLS NOT DISTINCT` sigue siendo imprescindible: `facility_id` es nullable
-- —NULL = evaluacion a nivel empresa— y con el comportamiento por defecto los
-- NULL no colisionan entre si, asi que se podria evaluar el mismo articulo a
-- nivel empresa tantas veces como se quisiera. Mismo motivo que en `db/01`.
CREATE UNIQUE INDEX IF NOT EXISTS uq_evaluacion_del_articulo
    ON article_compliance (matrix_norm_id, article_id, facility_id)
    NULLS NOT DISTINCT
    WHERE deleted_at IS NULL;

DO $$
DECLARE desbloqueadas bigint;
BEGIN
    SELECT count(*) INTO desbloqueadas
    FROM article_compliance WHERE deleted_at IS NOT NULL;

    RAISE NOTICE
        'OK · la unicidad es parcial. % evaluacion(es) retirada(s) dejan de '
        'bloquear su articulo.', desbloqueadas;
END $$;

COMMIT;
