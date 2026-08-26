-- ─────────────────────────────────────────────────────────────────────────
-- 16. La evidencia de un articulo evaluado (#126, epica #23)
-- ─────────────────────────────────────────────────────────────────────────
--
-- **La evidencia se estaba perdiendo en silencio, con respuesta 200.**
--
-- Medido con una sonda antes de escribir esto:
--
--     POST /compliance/article-compliance/{id}/evaluate?evidence_url=...
--     -> 200 OK, y el enlace no quedaba en ningun lado
--
-- El viaje completo estaba conectado por los dos extremos salvo por el medio:
-- el dialogo de evaluar pide "Evidencia (Google Drive / OneDrive)", el store
-- la manda como `evidence_url`, `evaluate_article()` hace
-- `art.evidence_url = evidence_url` — y **esa columna no existe**. SQLAlchemy
-- acepta que se le asigne un atributo cualquiera a una instancia y no lo
-- persiste; nada falla.
--
-- Para quien usa el sistema: pega el enlace, ve "guardado", recarga, y no esta.
-- Es la peor forma de perder un dato, porque nadie se entera hasta que hace
-- falta — y hace falta justo cuando llega un fiscalizador.
--
-- ## Por que una URL y no `entity_documents`
--
-- El esquema tiene un modulo documental completo (`documents`,
-- `document_versions`, `entity_documents`) con versiones, aprobacion y ciclo
-- de vida. **No es lo que corresponde aca todavia**: RF-07 pide adjuntar
-- evidencia desde Google Drive u OneDrive, o sea un enlace a un archivo que
-- vive fuera, y el frontend ya modela `Articulo.evidenciaUrl` como texto.
--
-- Meterla por `entity_documents` obligaria a crear un `document` por cada
-- enlace pegado, con version y estado, para algo que no gestionamos nosotros.
-- Cuando el control documental entre de verdad (epica de Info Documentada), la
-- migracion natural es poblar `entity_documents` desde esta columna — no al
-- reves.
--
-- No hace falta politica RLS ni GRANT: `article_compliance` ya los tiene y una
-- columna nueva los hereda.
--
-- Idempotente.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'article_compliance' AND column_name = 'evidence_url'
    ) THEN
        ALTER TABLE article_compliance ADD COLUMN evidence_url text;

        COMMENT ON COLUMN article_compliance.evidence_url IS
          'Enlace a la evidencia que respalda la evaluacion (RF-07): Google '
          'Drive, OneDrive u otro repositorio del cliente. Es un enlace y no un '
          'archivo nuestro; el control documental con versiones vive en '
          '`documents` y entra despues.';

        RAISE NOTICE 'article_compliance.evidence_url agregada.';
    ELSE
        RAISE NOTICE 'article_compliance.evidence_url ya existia; no se toca.';
    END IF;
END $$;

-- El indice sirve a la vista de incumplimientos (#126), que necesita separar
-- **lo que incumple con respaldo de lo que incumple sin nada que mostrar** — la
-- segunda categoria es la que hay que atender primero.
CREATE INDEX IF NOT EXISTS ix_ac_sin_evidencia
    ON article_compliance (matrix_norm_id)
    WHERE deleted_at IS NULL
      AND compliance_status = 'non_compliant'
      AND evidence_url IS NULL;
