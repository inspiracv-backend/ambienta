-- ============================================================================
--  35 · Un hallazgo de auditoria se sostiene en evidencia (ISO 19011)
-- ============================================================================
--
--  ## Que hueco llena
--
--  El spec de `gestion-mejoras` pide "evidencia objetiva en todo hallazgo,
--  **separada de su descripcion**": un hallazgo sin evidencia no es defendible
--  cuando el auditado lo apela. `nonconformities` tenia `description` y nada
--  mas, asi que la evidencia —si alguien la escribia— quedaba mezclada con el
--  relato, y nada obligaba a registrarla.
--
--  ## Por que solo a los de auditoria, y por que `NOT VALID`
--
--  **Hallazgo** es el registro que sale de una auditoria (`detection_origin`
--  `auditoria_interna` o `auditoria_externa`). Un reclamo de cliente o un
--  riesgo detectado en la revision anual no se "sostienen en evidencia
--  objetiva" en el sentido de ISO 19011: nacen de otra cosa.
--
--  `NOT VALID` hace que la restriccion rija **desde ahora**: las filas que ya
--  estaban no se revisan. Medido el 4-oct-2026: cero registros con origen en
--  auditoria, asi que hoy no hay ninguna fila en esa situacion — pero la base
--  de otro entorno podria tenerla, y hacer fallar la migracion por datos
--  historicos seria peor que el hueco que cierra.
--
--  Idempotente.
-- ============================================================================

BEGIN;

ALTER TABLE nonconformities ADD COLUMN IF NOT EXISTS objective_evidence text;

COMMENT ON COLUMN nonconformities.objective_evidence IS
  'La evidencia objetiva del hallazgo (ISO 19011), separada de su descripcion: que se vio, donde y cuando.';

ALTER TABLE nonconformities DROP CONSTRAINT IF EXISTS ck_nc_hallazgo_con_evidencia;
ALTER TABLE nonconformities ADD CONSTRAINT ck_nc_hallazgo_con_evidencia CHECK (
    detection_origin IS NULL
    OR detection_origin NOT IN ('auditoria_interna', 'auditoria_externa')
    OR (objective_evidence IS NOT NULL AND length(btrim(objective_evidence)) > 0)
) NOT VALID;

COMMIT;
