-- 24_datos_por_tipo_de_registro.sql
--
-- El tipo de un registro de mejora decide que datos exige la norma (#37, RF-46,
-- RF-96). Hoy `record_type` y `detection_origin` existen con su CHECK, y **no
-- hay donde guardar lo que cada tipo pide ni nada que lo exija**: se puede
-- registrar una salida no conforme sin decir que producto ni que lote.
--
--   ISO 9001 §8.7  — una salida no conforme se identifica y se controla:
--                    sin producto y lote no se sabe que se controlo.
--   ISO 9001 §9.1.2 — un reclamo es informacion sobre la percepcion del
--                    cliente: sin cliente ni canal no es un reclamo, es una nota.
--
-- ## Por que las restricciones van en la base y no solo en Pydantic
--
-- Un `UPDATE` a mano tambien tiene que respetarlas, y el registro de mejora es
-- de las tablas que alguien corrige por SQL cuando algo sale mal. Pydantic
-- responde el 422 legible; el CHECK es el que no se puede saltar. Mismo criterio
-- que `ck_crm_deals_perdido_con_motivo`.
--
-- ## Y por que JSONB y no columnas sueltas
--
-- `producto` y `reclamo` son estructuras de cuatro y cinco campos que solo
-- existen para un tipo de registro cada una. Nueve columnas nulas en el 60 % de
-- las filas —los tipos `no_conformidad`, `riesgo` y `oportunidad` no usan
-- ninguna— describen peor el modelo que dos objetos con su forma comprobada.
--
-- ## Un CHECK que evalua a NULL PASA
--
-- La primera version escribia `product_data ? 'sku'` a secas. Con
-- `product_data IS NULL` esa expresion no da falso: **da NULL**, y un CHECK solo
-- rechaza cuando su expresion es falsa. O sea que la restriccion admitia
-- exactamente el caso que existe para impedir, y en silencio.
--
-- Lo cazo la prueba que escribe saltandose Pydantic
-- (`TestLaBaseTambienLoExige`). Sin ella la barrera de la base habria quedado
-- decorativa y la unica real habria sido el schema — justo el que no protege un
-- `UPDATE` a mano, que es el motivo por el que estas restricciones existen.
--
-- De ahi el `IS NOT NULL` explicito y los `coalesce`: una clave ausente en `->>`
-- tambien devuelve NULL.
--
-- Idempotente: se puede volver a aplicar.

BEGIN;

-- ── Los datos que cada tipo exige ──────────────────────────────────────────

ALTER TABLE nonconformities ADD COLUMN IF NOT EXISTS product_data   jsonb;
ALTER TABLE nonconformities ADD COLUMN IF NOT EXISTS complaint_data jsonb;
ALTER TABLE nonconformities ADD COLUMN IF NOT EXISTS risk_opportunity_id uuid;

COMMENT ON COLUMN nonconformities.product_data IS
  'Solo para record_type = salida_no_conforme (ISO 9001 8.7). Claves: sku, '
  'lote, nombre, cantidad, unidad.';
COMMENT ON COLUMN nonconformities.complaint_data IS
  'Solo para record_type = reclamo (ISO 9001 9.1.2). Claves: cliente_nombre, '
  'canal, fecha_reclamo, y cliente_id cuando el reclamante es un tenant.';

-- ── Lo que cada tipo exige, con dientes ────────────────────────────────────
--
-- Las tres restricciones admiten `record_type IS NULL` a proposito: las filas
-- que ya existen no lo declaran, y esta migracion **no inventa el tipo de un
-- registro historico**. Deducirlo seria escribir una clasificacion que nadie
-- hizo, en la tabla que un auditor lee.

ALTER TABLE nonconformities DROP CONSTRAINT IF EXISTS ck_nc_salida_con_producto;
ALTER TABLE nonconformities ADD  CONSTRAINT ck_nc_salida_con_producto CHECK (
    record_type IS DISTINCT FROM 'salida_no_conforme'
    OR (
        product_data IS NOT NULL
    AND btrim(coalesce(product_data ->> 'sku',  '')) <> ''
    AND btrim(coalesce(product_data ->> 'lote', '')) <> ''
    )
);

ALTER TABLE nonconformities DROP CONSTRAINT IF EXISTS ck_nc_reclamo_con_cliente;
ALTER TABLE nonconformities ADD  CONSTRAINT ck_nc_reclamo_con_cliente CHECK (
    record_type IS DISTINCT FROM 'reclamo'
    OR (
        complaint_data IS NOT NULL
    AND btrim(coalesce(complaint_data ->> 'cliente_nombre', '')) <> ''
    AND btrim(coalesce(complaint_data ->> 'canal',          '')) <> ''
    )
);

-- Un registro que dice venir de una auditoria tiene que decir de cual hallazgo.
-- Sin eso la trazabilidad hacia la auditoria que lo origino no existe, y es lo
-- primero que se pide al revisar el seguimiento de una auditoria.
ALTER TABLE nonconformities DROP CONSTRAINT IF EXISTS ck_nc_auditoria_con_hallazgo;
ALTER TABLE nonconformities ADD  CONSTRAINT ck_nc_auditoria_con_hallazgo CHECK (
    detection_origin IS NULL
    OR detection_origin NOT IN ('auditoria_interna', 'auditoria_externa')
    OR audit_item_id IS NOT NULL
);

-- Y los datos de un tipo no se cuelan en otro: un reclamo con `product_data`
-- es un registro mal clasificado, y se veria igual que uno bien hecho.
ALTER TABLE nonconformities DROP CONSTRAINT IF EXISTS ck_nc_datos_del_tipo_que_es;
ALTER TABLE nonconformities ADD  CONSTRAINT ck_nc_datos_del_tipo_que_es CHECK (
    (product_data   IS NULL OR record_type = 'salida_no_conforme')
AND (complaint_data IS NULL OR record_type = 'reclamo')
);

-- ── Clave foranea del riesgo u oportunidad ─────────────────────────────────
--
-- Apunta a `environmental_risks`, que es donde vive el registro de riesgos y
-- oportunidades de §6.1. Se agrega solo si la tabla existe, para que esta
-- migracion no dependa del orden con la de matrices ISO.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'environmental_risks')
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_nc_riesgo')
    THEN
        ALTER TABLE nonconformities
            ADD CONSTRAINT fk_nc_riesgo
            FOREIGN KEY (risk_opportunity_id) REFERENCES environmental_risks(id);
    END IF;
END $$;

-- ── RLS y permisos ─────────────────────────────────────────────────────────
--
-- `nonconformities` ya los tiene: es una tabla de `01_schema`, no nace aca. Las
-- columnas nuevas viven dentro de la misma fila, asi que heredan su politica.
-- Se deja escrito para que nadie tenga que ir a comprobarlo.

COMMIT;
