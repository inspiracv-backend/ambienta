-- ============================================================================
-- Ingesta de la BCN: relaciones entre normas y bitacora de solo agregar
-- ============================================================================
--
-- `legal_relations` existe desde el esquema inicial y **nadie la escribia**: el
-- requisito "las relaciones entre normas se leen de la fuente" estaba en el
-- spec de la ingesta y el sistema no lo cumplia (auditoria del 10-sep).
--
-- Desde el 21-sep la sincronizacion las lee de la BCN (`bcn:modifiesTo`,
-- `regulates`, `recasts`, `rectifies`, `agreeWith` y sus inversas). Esta
-- migracion hace tres cosas:
--
--   1. **Admite `rectifica`.** La BCN publica las rectificaciones como una
--      relacion propia, y el CHECK no la tenia. Guardarla como `modifica`
--      diria algo que la fuente no dice: una rectificacion corrige un error de
--      publicacion, no cambia la norma.
--   2. **Una relacion entre dos normas se guarda una vez.** La sincronizacion
--      corre todos los dias; sin esto cada corrida duplicaria todas las
--      relaciones. Solo a nivel de norma (sin articulos): las relaciones entre
--      articulos, si algun dia se cargan, llevan su propia clave.
--   3. **La bitacora de sincronizacion es de solo agregar.** El spec dice que
--      nadie puede editarla, y por la API se cumplia (solo hay un `GET`), pero
--      el rol de la aplicacion tenia `UPDATE` y `DELETE`: un error de codigo
--      podia reescribir que se sincronizo y cuando. Mismo criterio que
--      `audit_log`: se inserta y se lee.
--
-- **La BCN no publica derogaciones como relacion.** Que una norma ya no rige se
-- sabe por su vigencia (`legal_norms.status`), que la Matriz Legal muestra.
--
-- La tabla es catalogo global (sin `tenant_id`, sin RLS): los permisos del rol
-- de la aplicacion ya los tiene desde `01_schema`.
--
-- Idempotente: se puede correr dos veces.
-- ============================================================================

BEGIN;

ALTER TABLE legal_relations DROP CONSTRAINT IF EXISTS legal_relations_relation_type_check;
ALTER TABLE legal_relations ADD CONSTRAINT legal_relations_relation_type_check
    CHECK (relation_type IN (
        'modifica', 'deroga', 'reglamenta', 'concordancia', 'referencia', 'refundido', 'rectifica'
    ));

CREATE UNIQUE INDEX IF NOT EXISTS uq_legal_relations_entre_normas
    ON legal_relations (source_norm_id, target_norm_id, relation_type)
    WHERE source_article_id IS NULL AND target_article_id IS NULL;

COMMENT ON INDEX uq_legal_relations_entre_normas IS
  'Una relacion entre dos normas se guarda una vez: la sincronizacion de la BCN corre todos los dias.';

REVOKE UPDATE, DELETE ON norm_sync_runs FROM ambienta_app;

COMMIT;
