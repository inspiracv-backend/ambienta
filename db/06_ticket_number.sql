-- =============================================================================
-- 06 · Numero de ticket generado por la base
-- =============================================================================
-- `support_tickets.ticket_number` es NOT NULL UNIQUE y nadie lo generaba: el
-- esquema de entrada de la API no lo pedia y el servicio no lo calculaba, asi
-- que POST /api/v1/support/tickets respondia 500 con NotNullViolation. Era el
-- unico endpoint roto de los 91, y justo el que sostiene el flujo del Cliente
-- Invitado (RF-02/RF-03), cuyo unico proposito es crear solicitudes.
--
-- Lo genera la base y no Python a proposito:
--
--   * La unicidad es GLOBAL, no por empresa. Calcular `max(...) + 1` en la
--     aplicacion abre una carrera entre dos peticiones simultaneas de tenants
--     distintos, que terminaria en un 500 esporadico imposible de reproducir.
--     Una secuencia no tiene ese problema.
--   * Cualquier otro escritor —una carga masiva, un script de migracion— lo
--     obtiene sin repetir la logica.
--
-- Formato: TKT-000001. Correlativo y legible para citarlo por telefono o
-- correo, que es como se referencia un ticket en la practica.
--
-- Idempotente: se puede correr sobre una base ya migrada.
-- =============================================================================

CREATE SEQUENCE IF NOT EXISTS support_ticket_number_seq;

ALTER TABLE support_tickets
    ALTER COLUMN ticket_number
    SET DEFAULT 'TKT-' || lpad(nextval('support_ticket_number_seq')::text, 6, '0');

-- El GRANT del esquema corre una sola vez, sobre lo que existia entonces: una
-- secuencia creada despues NO lo hereda. Sin esto, `ambienta_app` puede
-- insertar el ticket pero no avanzar el contador, y el INSERT falla con
-- "permission denied for sequence". Es la misma trampa que ya costo una tarde
-- con las politicas RLS de una tabla nacida en migracion.
GRANT USAGE, SELECT ON SEQUENCE support_ticket_number_seq TO ambienta_app;

-- Si ya hubiera tickets sin numero (no deberia: el INSERT fallaba antes de
-- llegar a la tabla), se numeran para no dejar la columna inconsistente.
UPDATE support_tickets
SET ticket_number = 'TKT-' || lpad(nextval('support_ticket_number_seq')::text, 6, '0')
WHERE ticket_number IS NULL;

DO $$
BEGIN
    RAISE NOTICE 'OK · ticket_number lo genera la secuencia support_ticket_number_seq';
END $$;
