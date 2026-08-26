-- ============================================================================
-- El DS 90/2000 viene de la BCN, no de ISO
-- ============================================================================
--
-- `db/02_seed.sql` lo sembro con `source_id = 2` (ISO). Es un error de dato:
-- el DS 90/2000 es el **Decreto Supremo que fija la norma de emision para
-- contaminantes en descargas de residuos liquidos a aguas marinas y
-- continentales**, publicado en el Diario Oficial. ISO es para estandares
-- internos de la empresa (ISO 14001), no para legislacion chilena.
--
-- ## Por que hay que corregirlo antes de sincronizar
--
-- La sincronizacion adopta la fila sembrada **solo dentro de su misma fuente**,
-- a proposito: re-hospedar una norma de una fuente a otra por cuenta propia
-- seria cambiarle la identidad a un dato que alguien declaro.
--
-- El efecto de dejarlo asi no es un error visible: la BCN traeria el DS 90 real
-- como fila **nueva**, y las 2 clasificaciones por sector que tiene la fila
-- sembrada —trabajo humano— se quedarian pegadas a la copia. El CORE seguiria
-- proponiendo la falsa y la real no le aplicaria a nadie. **Sin ningun error a
-- la vista**, que es la peor forma de romperlo.
--
-- ## Lo que NO se toca
--
-- La `RE-574/2019`, sembrada como fuente `RCA`. Ahi no hay nada que corregir:
-- la BCN no devuelve esa resolucion sino el DS 1/2013 del RETC, que es **otra
-- norma**. No se duplica nada, y forzar una equivalencia entre las dos seria
-- inventarla.
--
-- ## Idempotente
--
-- Solo mueve la fila si sigue en ISO y sin identificador externo. Una vez
-- adoptada por la BCN, `external_norm_id` deja de ser nulo y esta migracion no
-- vuelve a tocarla.
-- ============================================================================

DO $$
DECLARE
    id_bcn smallint;
    movidas int;
BEGIN
    SELECT id INTO id_bcn FROM legal_sources WHERE code = 'BCN_LEYCHILE';

    IF id_bcn IS NULL THEN
        RAISE EXCEPTION
          'No existe la fuente BCN_LEYCHILE. Se siembra en db/02_seed.sql: '
          'aplica ese script antes que este.';
    END IF;

    UPDATE legal_norms
       SET source_id = id_bcn
     WHERE norm_number = '90/2000'
       AND external_norm_id IS NULL
       AND source_id <> id_bcn
       AND deleted_at IS NULL;

    GET DIAGNOSTICS movidas = ROW_COUNT;

    IF movidas > 0 THEN
        RAISE NOTICE 'DS 90/2000 movido a la fuente BCN_LEYCHILE.';
    ELSE
        RAISE NOTICE 'DS 90/2000 ya estaba en la BCN o no existe: nada que hacer.';
    END IF;
END $$;
