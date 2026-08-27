-- 19 · El estado que le faltaba a la cola de avisos (RF-41, #118)
--
-- `notifications` ya era una cola: tiene `status` con `queued` por defecto,
-- `scheduled_at`, `sent_at`, `provider_message_id`, `dedupe_key` con indice
-- unico, y hasta un indice parcial sobre los pendientes. Lo que no tenia es
-- **como reintentar**.
--
-- Sin esto, un fallo del proveedor de correo deja dos salidas y las dos son
-- malas: marcar `failed` —que es terminal y pierde el aviso para siempre, que
-- es justo lo que este sistema existe para que no pase— o dejarlo en `queued`
-- y que el despachador lo reintente en bucle cerrado contra un servicio caido,
-- cada minuto, sin registrar por que falla. Un aviso de vencimiento perdido no
-- avisa a nadie y **nadie se entera de que no aviso**.
--
-- Las tres columnas:
--
--   attempts         cuantas veces se intento. Es lo unico que permite
--                    rendirse: sin contador, "reintentar hasta que salga" y
--                    "reintentar para siempre" son la misma cosa.
--   last_error       por que fallo el ultimo intento. Un `failed` sin motivo
--                    obliga a reproducir el fallo para diagnosticarlo, y estos
--                    fallan de noche.
--   next_attempt_at  cuando volver a intentar. Nulo = usar `scheduled_at`.
--
-- **Por que `next_attempt_at` aparte y no correr `scheduled_at`.** Empujar
-- `scheduled_at` en cada reintento seria una columna menos, pero borraria
-- cuando *debia* salir el aviso. Esa fecha es la que contesta "¿avisamos a
-- tiempo?" en una auditoria, y un reintento no cambia la respuesta.
--
-- Idempotente: se puede correr dos veces.

BEGIN;

ALTER TABLE notifications ADD COLUMN IF NOT EXISTS attempts        smallint    NOT NULL DEFAULT 0;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS last_error      text;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;

COMMENT ON COLUMN notifications.attempts IS
    'Intentos de entrega. Permite rendirse; sin el, reintentar es reintentar para siempre.';
COMMENT ON COLUMN notifications.last_error IS
    'Por que fallo el ultimo intento. Un failed sin motivo no se diagnostica de noche.';
COMMENT ON COLUMN notifications.next_attempt_at IS
    'Cuando reintentar. NULL = usar scheduled_at. Aparte para no perder cuando DEBIA salir.';

-- El contador no puede ser negativo ni desbocarse: si algo lo escribe mal,
-- mejor que reviente aca y no que un aviso se reintente cuatro mil veces.
ALTER TABLE notifications DROP CONSTRAINT IF EXISTS ck_notifications_intentos;
ALTER TABLE notifications ADD  CONSTRAINT ck_notifications_intentos
    CHECK (attempts >= 0 AND attempts <= 100);

-- El indice por el que el despachador toma trabajo. Ordena por la fecha
-- efectiva —el reintento si lo hay, si no la programada— porque es el orden en
-- que hay que atender: un aviso que ya fallo y toca reintentar no debe colarse
-- delante de uno que nunca se intento y vence antes.
CREATE INDEX IF NOT EXISTS ix_notifications_por_despachar
    ON notifications (COALESCE(next_attempt_at, scheduled_at))
    WHERE status = 'queued' AND deleted_at IS NULL;

-- El viejo queda estrictamente contenido en el nuevo: misma tabla, mismo
-- predicado salvo que aquel no excluia los borrados. Dos indices para la misma
-- consulta se pagan en cada escritura y solo uno se usa.
DROP INDEX IF EXISTS ix_notifications_pending;

COMMIT;
