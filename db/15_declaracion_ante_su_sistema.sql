-- ─────────────────────────────────────────────────────────────────────────
-- 15. Una declaracion sabe ante que sistema se presenta (#114, epica #21)
-- ─────────────────────────────────────────────────────────────────────────
--
-- **Hoy el sistema se deduce del codigo, leyendo la cadena.** El frontend
-- parte `OBL-SIDREP-2026S1` por guiones y se queda con el trozo del medio.
-- Funciona hasta que alguien escribe un codigo con otra forma —y el codigo lo
-- escribe una persona en un campo de texto libre— y entonces la obligacion
-- deja de tener sistema **sin ningun error**: simplemente el boton "ir al
-- sistema oficial" no aparece y nadie sabe por que.
--
-- Peor: dos obligaciones del mismo portal escritas `SIDREP` y `sidrep` serian
-- sistemas distintos para el codigo que las agrupa.
--
-- La referencia va a `retc_systems`, que es donde vive `url_oficial` — el dato
-- que hace posible el boton. Que la URL este en el catalogo y no copiada en
-- cada obligacion importa: los portales del Estado cambian de direccion, y
-- copiada habria que corregirla fila por fila.
--
-- **Es opcional a proposito.** Una obligacion puede no presentarse ante ningun
-- portal: un compromiso de una RCA, una tarea interna. Obligar a elegir uno
-- forzaria a inventar el sistema.
--
-- No hace falta politica RLS ni GRANT nuevos: `obligations` ya los tiene y una
-- columna nueva los hereda. `retc_systems` es catalogo global sin `tenant_id`
-- (ver `12_reportabilidad_retc.sql`), asi que la referencia no cruza empresas.
--
-- Idempotente.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'obligations' AND column_name = 'retc_system_id'
    ) THEN
        ALTER TABLE obligations ADD COLUMN retc_system_id smallint;

        ALTER TABLE obligations
            ADD CONSTRAINT fk_obligations_retc_system
            FOREIGN KEY (retc_system_id) REFERENCES retc_systems(id);

        COMMENT ON COLUMN obligations.retc_system_id IS
          'Portal ante el que se declara. NULL = no se presenta ante ninguno '
          '(compromiso de RCA, tarea interna). La URL sale de retc_systems, no '
          'se copia aca: los portales cambian de direccion.';

        RAISE NOTICE 'obligations.retc_system_id agregada.';
    ELSE
        RAISE NOTICE 'obligations.retc_system_id ya existia; no se toca.';
    END IF;
END $$;

-- El indice sirve a "que declaraciones tengo pendientes en SIDREP", que es la
-- pregunta con la que se abre el calendario de un encargado.
CREATE INDEX IF NOT EXISTS ix_obligations_retc_system
    ON obligations (retc_system_id)
    WHERE deleted_at IS NULL AND retc_system_id IS NOT NULL;


-- ── El motivo del rechazo ────────────────────────────────────────────────
--
-- `obligations.status` ya admite 'rejected' desde `01_schema.sql`, pero no hay
-- donde decir **por que**. Un rechazo sin motivo obliga a quien lo recibe a
-- adivinar que corregir, y en una declaracion ambiental eso son semanas: el
-- plazo sigue corriendo mientras tanto.
--
-- Va en `data`, que es jsonb y ya existe, y no en una columna propia: el
-- motivo es texto libre que solo se lee en la pantalla de la declaracion, no
-- algo por lo que se filtre ni se agrupe. Se documenta aca para que la clave
-- no se invente distinta en cada lugar.

COMMENT ON COLUMN obligations.data IS
  'Datos libres de la obligacion. Claves con significado fijado: '
  '`motivo_rechazo` (texto que dejo quien rechazo, ver services/declaracion.py).';
