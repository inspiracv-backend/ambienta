-- 27_vinculos_de_documentos.sql
--
-- RF-108 nombra cuatro anclajes para un documento: norma, proceso, obligacion
-- y auditoria. El CHECK de `entity_type` admitia once valores y **dos de esos
-- cuatro no estaban**: `legal_norm` y `process`. O sea que un procedimiento no
-- se podia colgar del proceso que describe, ni una politica de la norma que la
-- exige, y el requisito se leia como cumplido porque la tabla existia.
--
-- Idempotente: se puede volver a aplicar sobre una base que ya la tiene.
--
-- **No se agrega clave foranea, y no se puede.** `entity_id` apunta a trece
-- tablas distintas segun `entity_type`; una FK exige una sola. Por eso la
-- comprobacion de que ese identificador existe y es de esta empresa vive en
-- `services/vinculos_de_documentos.py`, y hay una prueba que lee ESTE archivo
-- para exigir que las dos listas digan lo mismo.

BEGIN;

ALTER TABLE entity_documents
    DROP CONSTRAINT IF EXISTS entity_documents_entity_type_check;

ALTER TABLE entity_documents
    ADD CONSTRAINT entity_documents_entity_type_check
    CHECK (entity_type IN ('article_compliance','obligation','task','action_plan','audit',
                           'nonconformity','contract','environmental_aspect','risk_opportunity',
                           'regulated_equipment','declaration_submission',
                           -- RF-108: los dos que faltaban.
                           'legal_norm','process'));

COMMENT ON COLUMN entity_documents.entity_type IS
    'Que clase de registro respalda este documento. Sin clave foranea: '
    'apunta a trece tablas distintas. La lista tiene que coincidir con el '
    'mapa ANCLAJES de services/vinculos_de_documentos.py, y una prueba lee '
    'este archivo para comprobarlo.';

COMMIT;
