-- 20 · La plantilla de aviso de vencimiento, en TODAS las empresas (#121)
--
-- `notification_templates` tenia tres filas y **todas en una sola empresa**:
-- las sembro `02_seed.sql` como datos de demostracion. Cualquier otra empresa
-- —incluida la segunda del propio seed— se quedaba sin plantilla.
--
-- Eso no rompe nada, y por eso conviene decirlo: sin plantilla el aviso sale
-- igual, con el texto por defecto que arma `avisos_de_vencimiento._cuerpo()`.
-- Falla suave a proposito. Pero significa que la personalizacion del correo
-- —lo que pedia #121— existia para una empresa de ejemplo y para nadie mas.
--
-- Mismo criterio que `09_roles_por_codigo.sql`: lo que toda empresa necesita
-- para funcionar se crea en todas, no solo en la que sirvio de demostracion.
--
-- **Lo que esto NO arregla:** una empresa creada despues de correr esta
-- migracion nace sin plantillas. El alta de empresa tendria que crearlas, y
-- hoy no lo hace. Queda anotado en vez de simulado — el sistema funciona sin
-- ellas, asi que es una mejora pendiente y no un bloqueo.
--
-- Idempotente: se puede correr dos veces.

BEGIN;

INSERT INTO notification_templates
    (tenant_id, code, name, event_type, channel, locale,
     subject_template, body_template, variables_schema, version_no, active)
SELECT
    t.id,
    'OBL_VENCIMIENTO',
    'Aviso de vencimiento de obligacion',
    'obligation_due',
    'email',
    'es-CL',
    'Obligación {{obligation_code}} vence en {{days_remaining}} días',
    'La obligación "{{obligation_title}}" asignada a {{facility_name}} vence el '
    || '{{due_date}}. Por favor tome las acciones necesarias.',
    -- Las variables que la plantilla usa, declaradas. Sirven para que una
    -- pantalla de edicion pueda ofrecerlas en vez de que alguien las adivine y
    -- escriba un marcador que nunca se rellena.
    '{"obligation_code": "string", "obligation_title": "string",
       "days_remaining": "number", "due_date": "string",
       "facility_name": "string"}'::jsonb,
    1,
    true
FROM tenants t
WHERE t.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM notification_templates nt
      WHERE nt.tenant_id = t.id
        AND nt.event_type = 'obligation_due'
        AND nt.channel = 'email'
        AND nt.locale = 'es-CL'
        AND nt.deleted_at IS NULL
  );

-- La fila que ya existia tiene `variables_schema` en `{}`, o sea sin declarar
-- nada. Se completa: una pantalla de edicion que lea eso ofreceria cero
-- variables, y quien edite la plantilla tendria que adivinar los nombres.
UPDATE notification_templates
   SET variables_schema = '{"obligation_code": "string", "obligation_title": "string",
                            "days_remaining": "number", "due_date": "string",
                            "facility_name": "string"}'::jsonb
 WHERE event_type = 'obligation_due'
   AND channel = 'email'
   AND variables_schema = '{}'::jsonb
   AND deleted_at IS NULL;

COMMIT;
