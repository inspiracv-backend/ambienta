-- 29_normativa_propia.sql
--
-- RF-10 y RF-11 (bloque D): la normativa **propia** de cada empresa — su
-- Resolucion de Calificacion Ambiental y sus normas internas.
--
-- ## Que faltaba, medido el 7-sep-2026
--
-- El catalogo normativo es enteramente publico, y **no puede dejar de serlo
-- sin este cambio**:
--
-- | tabla | tenant_id | RLS |
-- |---|---|---|
-- | legal_norms | no | no |
-- | legal_norm_versions | no | no |
-- | legal_articles | no | no |
--
-- Y esta bien que sea asi: la ley es la misma para todos, y por eso 24 normas
-- y 689 articulos se comparten. La consecuencia es que **una empresa no puede
-- registrar su RCA**: es el permiso de ESE proyecto, con condiciones que solo
-- la obligan a ella, y escribirla en `legal_norms` la dejaria visible para
-- todas las demas. El dano no es abstracto — las condiciones de una RCA
-- describen la operacion de la planta.
--
-- ## Una columna nulable, no una tabla aparte
--
-- Con una `tenant_norms` separada, `matrix_norms.norm_id` tendria que apuntar
-- a dos tablas —polimorfico, sin clave foranea— y habria que duplicar el
-- camino en la matriz, la evaluacion por articulo, el calculo de cumplimiento,
-- el tablero y los reportes. Serian **dos implementaciones del mismo
-- concepto**, y la primera vez que se separen la empresa vera dos porcentajes
-- distintos sobre la misma planta.
--
-- Con una columna, una RCA **es** una norma y todo lo construido funciona sin
-- tocarse.
--
-- Idempotente.

BEGIN;

ALTER TABLE legal_norms          ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE legal_norm_versions  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
ALTER TABLE legal_articles       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;

COMMENT ON COLUMN legal_norms.tenant_id IS
    'NULL = norma publica, del catalogo compartido. Con valor = normativa '
    'propia de esa empresa (su RCA, sus ISO internas). RF-10.';

COMMENT ON COLUMN legal_articles.tenant_id IS
    'Acompana al de la norma. Una RCA sin sus considerandos es un titulo: los '
    'compromisos —caudales, horarios, monitoreos— viven aca, asi que esta '
    'tabla se protege igual. Dejarla afuera seria poner la puerta y olvidar '
    'la pared.';

-- Las consultas por empresa filtran por aca; las publicas piden `IS NULL`.
CREATE INDEX IF NOT EXISTS ix_legal_norms_tenant
    ON legal_norms (tenant_id) WHERE tenant_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_legal_articles_tenant
    ON legal_articles (tenant_id) WHERE tenant_id IS NOT NULL;

-- ── RLS: la politica de dos lados ───────────────────────────────────────────
--
-- El `USING` deja **leer** lo publico; el `WITH CHECK` **no** deja escribirlo.
-- Si los dos dijeran lo mismo, cualquier empresa podria insertar una norma con
-- `tenant_id` nulo y quedaria en el catalogo de todas — o sea, escribirle la
-- ley a las demas.
--
-- ## El `WITH CHECK` admite DOS casos, y el segundo se descubrio probando
--
-- La primera version decia solo `tenant_id = current_tenant_id()`, apoyada en
-- que la sincronizacion de la BCN escribe con `AdminSessionLocal` —el rol
-- `ambienta`, superusuario con `BYPASSRLS`— asi que la politica no la tocaria.
--
-- **Eso es falso cuando `DATABASE_ADMIN_URL` no esta configurada.**
-- `engine_admin` cae a la URL de la aplicacion (ver `app/db.py`), y entonces
-- la "sesion de administracion" conecta como `ambienta_app`, que no se salta
-- nada. Medido: con la variable vacia, `current_user` es `ambienta_app`.
--
-- El compose de este repositorio si la define, asi que dentro del contenedor
-- funcionaba — pero `.env.example` la trae vacia, y un despliegue que la
-- olvidara **dejaria el catalogo sin actualizarse**. Antes esa omision solo
-- degradaba el webhook de Clerk; con esta migracion habria pasado a romper la
-- BCN, y el sintoma seria "la BCN no trae nada".
--
-- Asi que la politica nombra los dos casos legitimos:
--
-- | quien escribe | que puede escribir |
-- |---|---|
-- | una sesion con tenant declarado | **solo lo suyo** |
-- | una sesion sin tenant (tareas, catalogo) | **solo lo publico** |
--
-- Lo que importa se conserva entero: **una empresa nunca puede escribir una
-- norma publica**, ni una de otra empresa. Y ninguna ruta de empresa escribe
-- `legal_norms` — las del catalogo exigen Admin Global y tocan `norm_sectors`.
--
-- ## Y estas tres van SIN `FORCE ROW LEVEL SECURITY`
--
-- Es lo contrario de lo que hacen `25` y `28`. `FORCE` sujeta tambien al
-- **dueno** de la tabla a la politica; aca haria falta que el dueno pudiera
-- saltarsela cuando si esta configurado el superusuario. Con la politica de
-- dos casos ya no es imprescindible, pero se deja sin `FORCE` para no
-- depender de que la configuracion sea la correcta.
--
-- `test_normativa_propia.py` **escribe una norma global por el camino de la
-- sincronizacion** despues de aplicar esto, y comprueba que las tres tablas
-- sigan sin `FORCE`.

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'legal_norms', 'legal_norm_versions', 'legal_articles'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        -- Deliberadamente NO se llama a FORCE. Ver arriba.
        EXECUTE format('ALTER TABLE %I NO FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS normativa_propia_o_publica ON %I', t);
        EXECUTE format(
            'CREATE POLICY normativa_propia_o_publica ON %I '
            'USING (tenant_id IS NULL OR tenant_id = current_tenant_id()) '
            -- Con tenant declarado, solo lo suyo. Sin tenant —tareas de fondo,
            -- catalogo—, solo lo publico. Nunca una empresa escribiendo lo
            -- publico ni lo de otra. Ver el comentario de arriba.
            'WITH CHECK (tenant_id = current_tenant_id() '
            '            OR (tenant_id IS NULL AND current_tenant_id() IS NULL))', t);
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO ambienta_app', t);
    END LOOP;
END $$;

COMMIT;
