-- 31 · Tareas del plan de accion (#169, cambio modelo-de-tareas-del-plan-de-accion)
--
-- ## Que agrega
--
-- `tasks.action_plan_id`: una tarea puede colgar de un plan de accion. Hasta
-- ahora `tasks` solo servia a las obligaciones, y la pantalla del plan mostraba
-- una lista de tareas que el modelo no tenia —siempre vacia, y marcar una se
-- perdia al recargar—. Esa seccion se quito el 13-sep a la espera de esto.
--
-- ## Por que una columna y no una tabla nueva
--
-- Decidido con el equipo: una tabla `action_plan_tasks` produciria **dos
-- conceptos de tarea**, con dos vocabularios de estado que se desincronizan, y
-- "lo que le toca a una persona" pasaria a ser dos consultas unidas. Con una
-- columna, calendario y Gantt ven las tareas del plan sin cambios.
--
-- ## Por que NO declara politica RLS ni GRANT
--
-- Agrega una columna a una tabla que **ya los tiene**. La trampa de CLAUDE.md
-- —una tabla nacida en una migracion no hereda la politica ni los GRANT de
-- `01_schema`— no aplica: `tasks` nacio alli. Duplicar la politica seria el
-- error contrario, y dos politicas permisivas se suman con OR.
--
-- Idempotente.

ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS action_plan_id uuid REFERENCES action_plans(id);

COMMENT ON COLUMN tasks.action_plan_id IS
  'Plan de accion del que cuelga la tarea (#169). Como maximo un padre: obligation_id o action_plan_id, o ninguno.';

-- **Se comprueba antes de crear el CHECK**, y se falla con un mensaje claro.
-- Hoy ninguna fila puede violarlo —la columna recien existe— pero una migracion
-- que falla a la mitad deja la base en un estado que nadie eligio.
DO $$
DECLARE
    dobles integer;
BEGIN
    SELECT count(*) INTO dobles
      FROM tasks
     WHERE obligation_id IS NOT NULL AND action_plan_id IS NOT NULL;
    IF dobles > 0 THEN
        RAISE EXCEPTION
          '31_tareas_del_plan_de_accion: % tarea(s) cuelgan de una obligacion Y de un plan. Resolverlas antes de aplicar el CHECK.',
          dobles;
    END IF;
END $$;

-- **Como maximo uno, no exactamente uno.** Una tarea suelta es legitima; lo que
-- no puede es contar en dos lugares a la vez y aparecer duplicada en dos fichas.
-- Distinto de `ck_crm_activities_un_solo_padre`, donde una actividad sin padre
-- no apareceria en ninguna ficha y por eso ahi si se exige uno.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_tasks_un_solo_padre') THEN
        ALTER TABLE tasks ADD CONSTRAINT ck_tasks_un_solo_padre
            CHECK (obligation_id IS NULL OR action_plan_id IS NULL);
    END IF;
END $$;

-- Parcial, en la misma forma que `ix_tasks_obligation`: las consultas siempre
-- excluyen las retiradas.
CREATE INDEX IF NOT EXISTS ix_tasks_action_plan
    ON tasks (action_plan_id) WHERE deleted_at IS NULL;
