-- ============================================================================
-- De quien es la solicitud de un invitado (RF-02, RF-07)
-- ============================================================================
--
-- `support_tickets` sabe que un ticket lo abrio un invitado —`guest_name` y
-- `guest_email`, con el CHECK `ck_support_tickets_autor`— pero **no sabe cual**.
--
-- Sin eso, "el invitado solo ve sus propias solicitudes" no se puede cumplir:
-- no hay contra que comparar. Filtrar por `guest_email` seria peor que no
-- filtrar, porque el correo lo escribe la misma persona en el formulario y
-- **cualquiera puede escribir el de otro** para ver sus tickets.
--
-- La credencial, en cambio, hay que probarla. Por eso el vinculo va contra
-- `guest_credentials.id`.
--
-- ## Se borra en cascada, y esa es la decision
--
-- `ON DELETE SET NULL` y no `CASCADE`: si algun dia se purga una credencial
-- vencida, **el ticket se queda**. La solicitud es del negocio y puede seguir
-- abierta; la credencial es solo la forma en que esa persona entra. Borrar el
-- trabajo junto con la llave seria perder lo que importa para conservar lo
-- desechable.
--
-- ## No crea tablas
--
-- Asi que no declara RLS ni GRANT: la columna hereda los de `support_tickets`,
-- que ya los tiene. (Una tabla *nueva* si tendria que declararlos — el bucle de
-- `01_schema` corre una sola vez.)
-- ============================================================================

ALTER TABLE support_tickets
    ADD COLUMN IF NOT EXISTS guest_credential_id uuid
        REFERENCES guest_credentials(id) ON DELETE SET NULL;

COMMENT ON COLUMN support_tickets.guest_credential_id IS
  'Con que credencial de invitado se abrio la solicitud (RF-02, RF-07). NULL '
  'cuando la abrio un usuario registrado. Es lo unico contra lo que se puede '
  'comprobar que un invitado ve solo lo suyo: el correo lo escribe el mismo.';

-- Parcial: la enorme mayoria de los tickets son de usuarios registrados y
-- llevan NULL aca. Un indice completo indexaria sobre todo ausencias.
CREATE INDEX IF NOT EXISTS ix_support_tickets_guest_credential
    ON support_tickets (guest_credential_id)
    WHERE guest_credential_id IS NOT NULL AND deleted_at IS NULL;
