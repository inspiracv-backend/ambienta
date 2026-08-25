-- ============================================================================
-- Credenciales del Cliente Invitado (RF-01, RF-02, RF-07)
-- ============================================================================
--
-- Una persona sin cuenta abre una solicitud y necesita poder volver a verla.
-- El analisis pide RUT y clave dinamica, sin registro previo.
--
-- ## Por que una tabla propia y no una fila en `users`
--
-- Decision D2 del cambio `credenciales-de-acceso`, confirmada por el equipo:
-- **el invitado no es una cuenta de Clerk ni un usuario del sistema.**
--
--   * RF-02 dice literalmente que no necesita cuenta previa.
--   * Meterlos en `users` mezcla en la misma tabla a los empleados de la
--     empresa y a terceros ocasionales, y el volumen de invitados es por
--     diseno el mas alto y el menos valioso de mantener.
--   * Todo lo que hoy lee `users` —permisos, roles, alcance— tendria que
--     aprender a distinguirlos, y basta olvidarlo en un lugar para darle a un
--     tercero algo que no le toca.
--
-- ## Lo que se pierde y como se acota
--
-- Quedan dos emisores de credenciales, que es justo lo que ADR-006 quiso
-- evitar. Se acota con D3: **el acceso del invitado no abre ningun endpoint de
-- negocio.** La superficie donde importa que la identidad sea fuerte sigue
-- teniendo un solo emisor.
--
-- ## Idempotente
--
-- `db/01_schema.sql` no es una migracion: su bucle de politicas y su
-- `GRANT ON ALL TABLES` corren **una sola vez**, al crear el volumen. Una tabla
-- que nace aca no los hereda, asi que declara **su propia politica RLS y sus
-- GRANT** o queda visible entre empresas.
-- ============================================================================

CREATE TABLE IF NOT EXISTS guest_credentials (
    id            uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- El RUT normalizado: sin puntos, con guion, verificador en mayuscula.
    -- **Se guarda normalizado y no como lo escribio la persona**: el mismo RUT
    -- admite tres formatos, y sin normalizar la unicidad no encuentra el
    -- duplicado.
    rut           varchar(20)   NOT NULL,

    -- Nunca la clave en claro. Se guarda su hash, igual que cualquier otra.
    -- Que el acceso sea temporal y de bajo privilegio no cambia que la persona
    -- probablemente reuse esa clave en otro lado.
    password_hash varchar(255)  NOT NULL,

    -- Hasta cuando sirve. **Con vigencia y no perpetua**: son credenciales que
    -- se entregan sin verificar quien las recibe, y una credencial sin
    -- caducidad emitida a un desconocido no se puede retirar.
    valid_until   timestamptz   NOT NULL,

    -- Para poder decirle "generaste tu acceso el 3 de marzo" y para medir el
    -- uso real del canal de invitados.
    created_at    timestamptz   NOT NULL DEFAULT now(),
    last_used_at  timestamptz,

    -- Se revoca sin borrar: si una credencial se filtro, hay que poder cortarla
    -- **y conservar el rastro** de que existio y que solicitudes abrio.
    revoked_at    timestamptz,

    -- El RUT es unico dentro de la empresa, no globalmente. Un contratista que
    -- trabaja para dos empresas del sistema recibe una credencial en cada una:
    -- son accesos distintos a datos distintos, y unificarlos exigiria un modelo
    -- de identidad que hoy no existe (decision abierta #3).
    CONSTRAINT uq_guest_credentials_tenant_rut UNIQUE (tenant_id, rut),

    -- Una vigencia que termina antes de empezar es un dato imposible, y el
    -- unico momento de detectarlo es al escribirlo.
    CONSTRAINT ck_guest_credentials_vigencia CHECK (valid_until > created_at)
);

COMMENT ON TABLE guest_credentials IS
  'Acceso temporal del Cliente Invitado (RF-01, RF-02, RF-07). NO es un usuario: '
  'no abre ningun endpoint de negocio, solo el seguimiento de sus propias solicitudes.';

CREATE INDEX IF NOT EXISTS ix_guest_credentials_tenant_rut
    ON guest_credentials (tenant_id, rut) WHERE revoked_at IS NULL;

-- ── Aislamiento entre empresas ──────────────────────────────────────────────
--
-- Se declara aca porque el bucle de `01_schema` ya corrio. Sin esto la tabla
-- **no falla**: devuelve las credenciales de todas las empresas, que es
-- exactamente la fuga que RLS existe para impedir.

ALTER TABLE guest_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE guest_credentials FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON guest_credentials;
CREATE POLICY tenant_isolation ON guest_credentials
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- ── Permisos de la conexion de la aplicacion ────────────────────────────────
--
-- El `GRANT ON ALL TABLES` de `01_schema` tampoco alcanza a una tabla nacida
-- despues. Sin esto, la API responde "permission denied" sobre una tabla que
-- existe y esta bien.

GRANT SELECT, INSERT, UPDATE, DELETE ON guest_credentials TO ambienta_app;
