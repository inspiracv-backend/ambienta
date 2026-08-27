-- ─────────────────────────────────────────────────────────────────────────
-- 17. Un aviso por vencimiento y ventana, no tres (#119, #120, epica #22)
-- ─────────────────────────────────────────────────────────────────────────
--
-- **`create_deadline_notifications()` duplica.** Medido con una sonda antes de
-- tocar nada: tres corridas seguidas sobre la misma obligacion y la misma
-- ventana dejaron **tres avisos**.
--
--     1a corrida: 1 aviso
--     2a corrida: 1 aviso
--     3a corrida: 1 aviso
--     avisos para LA MISMA obligacion: 3
--
-- El generador esta pensado para correr en un cron diario (#119). Un reinicio,
-- un reintento, dos trabajadores, o alguien apretando el boton dos veces, y la
-- persona recibe el mismo "vence en 7 dias" repetido.
--
-- **El dano no es el ruido, es lo que el ruido provoca.** Un sistema que avisa
-- de mas se deja de leer, y entonces el aviso que si importaba pasa de largo.
-- En este dominio eso termina en una declaracion no presentada.
--
-- ## Por que va en la base y no en un `if`
--
-- Una comprobacion en Python protege mientras nadie escriba un segundo camino
-- que inserte avisos — y ya hay dos lugares que escriben en esta tabla. Una
-- restriccion de unicidad protege siempre, incluso contra dos procesos
-- corriendo a la vez, que es exactamente el caso del cron con reintentos.
--
-- ## Por que una clave generica y no `obligation_id`
--
-- `notifications` sirve a cualquier evento: vencimientos hoy, y manana
-- asignaciones, aprobaciones, cambios normativos. Una columna `obligation_id`
-- la ataria a un solo dominio y obligaria a agregar otra por cada evento nuevo.
--
-- `dedupe_key` la calcula quien produce el aviso y describe **que aviso es**:
--
--     vencimiento:<obligation_id>:<dias_de_anticipacion>
--
-- Es nullable: un aviso escrito a mano, o uno que legitimamente puede repetirse,
-- va sin clave y no choca con nada. El indice es parcial por eso.
--
-- Idempotente.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'notifications' AND column_name = 'dedupe_key'
    ) THEN
        ALTER TABLE notifications ADD COLUMN dedupe_key varchar(200);

        COMMENT ON COLUMN notifications.dedupe_key IS
          'Identifica QUE aviso es, para no repetirlo. La calcula quien lo '
          'produce; formato de los vencimientos: '
          '`vencimiento:<obligation_id>:<dias>`. NULL = un aviso que puede '
          'repetirse (escrito a mano, o de un evento que ocurre varias veces).';

        RAISE NOTICE 'notifications.dedupe_key agregada.';
    ELSE
        RAISE NOTICE 'notifications.dedupe_key ya existia; no se toca.';
    END IF;
END $$;


-- **Se limpia antes de crear el indice, o la migracion falla en una base con
-- datos.** No es hipotetico: las pruebas de esta serie ya dejaron avisos
-- duplicados en la base de desarrollo.
--
-- Se conserva **el mas antiguo** de cada grupo: es el que la persona
-- probablemente ya vio, y borrar ese dejaria un `read_at` perdido.
--
-- Solo toca filas que ya son duplicados exactos por su contexto. Un aviso sin
-- `obligation_id` en el contexto no entra en el `GROUP BY` y no se toca.
WITH duplicados AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY tenant_id,
                            recipient_user_id,
                            context->>'obligation_id',
                            context->>'days_before'
               ORDER BY created_at
           ) AS n
    FROM notifications
    WHERE deleted_at IS NULL
      AND context->>'obligation_id' IS NOT NULL
      AND context->>'days_before' IS NOT NULL
)
UPDATE notifications
SET deleted_at = now()
WHERE id IN (SELECT id FROM duplicados WHERE n > 1);


-- Se rellena la clave de los avisos que ya existen, para que el generador los
-- reconozca y no los vuelva a emitir la proxima vez que corra.
UPDATE notifications
SET dedupe_key = 'vencimiento:' || (context->>'obligation_id')
                 || ':' || (context->>'days_before')
WHERE dedupe_key IS NULL
  AND deleted_at IS NULL
  AND context->>'obligation_id' IS NOT NULL
  AND context->>'days_before' IS NOT NULL;


-- ── La clave incluye al destinatario, y esa parte costo un intento ───────
--
-- La primera version indexaba `(tenant_id, dedupe_key)` a secas, con el
-- razonamiento de que un aviso escalado a varios administradores es "el mismo
-- aviso". **La base lo rechazo en la primera prueba**, y tenia razon: escalar
-- inserta una fila por administrador, todas con la misma clave.
--
-- El razonamiento tambien era flojo por otro lado. Decia que incluir al
-- destinatario haria que un administrador agregado manana recibiera de golpe
-- todos los avisos viejos. No pasa: las ventanas se miden contra **ahora**, asi
-- que una obligacion cuya ventana de 7 dias ya paso no se vuelve a evaluar.
--
-- La clave natural de un aviso es **que evento, a quien**.
--
-- El indice es parcial en dos sentidos: ignora lo borrado —si no, reenviar un
-- aviso dado de baja seria imposible— y las claves nulas, que si no chocarian
-- todas entre si.
--
-- `recipient_user_id` es nullable en el esquema. En un indice unico los NULL no
-- colisionan entre si, asi que un aviso sin destinatario concreto no bloquea a
-- otro: es lo correcto, porque esos avisos no son "el mismo" de nadie.

DROP INDEX IF EXISTS uq_notifications_dedupe;

CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_dedupe_destinatario
    ON notifications (tenant_id, dedupe_key, recipient_user_id)
    WHERE deleted_at IS NULL AND dedupe_key IS NOT NULL;
