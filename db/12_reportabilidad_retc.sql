-- ============================================================================
-- Sistemas sectoriales del RETC y reportabilidad por instalacion (#102, #103)
-- ============================================================================
--
-- Implementa ADR-004 (Aceptado, 2026-06-01): el nucleo del modulo RETC es saber
-- **que sistemas aplican a cada instalacion y con que estado**. Hoy eso lo
-- determina un especialista a mano, cruzando articulos de la RCA con los
-- portales que corresponden: dias de trabajo por instalacion nueva.
--
-- ## Dos tablas, y la separacion importa
--
--   `retc_systems`              QUE portales existen. Es la ley, igual para
--                               todos: **sin `tenant_id`**, como `legal_norms`
--                               y `sectors`.
--   `facility_retc_reporting`   CUALES le tocan a esta instalacion. Es dato de
--                               empresa: con `tenant_id` y su propia RLS.
--
-- Mezclarlas obligaria a copiar el catalogo por empresa, y entonces una
-- resolucion del MMA habria que aplicarla N veces.
--
-- ## Un sistema sectorial NO es un sector CIIU
--
-- Conviene decirlo porque el repo tiene las dos cosas y **el numero 21 se usa
-- para las dos**, sin relacion:
--
--   * `sectors` = rubro economico de la empresa (CIIU). Responde "a que se
--     dedica". Sirve para proponerle normativa.
--   * `retc_systems` = ante quien declara. Responde "donde reporta".
--
-- Una minera y una termoelectrica pueden compartir sistema sin compartir
-- rubro. Son dimensiones ortogonales y esta migracion no las cruza.
--
-- ## Lo que este seed NO trae, dicho antes de que alguien lo cite
--
-- ADR-004 dice "21 portales (12 sistemas sectoriales + 9 sistemas SMA)" y cita
-- una fuente —`resources/normativa-legal-chile/retc-sistemas-calendarios-2026.md`—
-- **que no existe en el repositorio**.
--
-- Aca se siembran **los 12 sectoriales**, tomados del portal oficial
-- (https://portalvu.mma.gob.cl, consultado el 25-ago-2026), y cada fila lleva
-- su procedencia en `fuente`. Los 9 de la SMA quedan **sin sembrar**: no hay
-- fuente verificable en el repo ni la encontre publicada, y ponerlos de memoria
-- seria inventar un catalogo que despues se cita como un hecho.
--
-- `active = false` en todas: **es un borrador que negocio tiene que firmar**.
-- Hasta entonces la API las devuelve marcadas como no confirmadas, en vez de
-- pasar por catalogo cerrado.
-- ============================================================================

-- ── El catalogo: que portales existen ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS retc_systems (
    id            smallserial   PRIMARY KEY,
    code          varchar(20)   NOT NULL UNIQUE,
    name          varchar(200)  NOT NULL,

    -- Quien lo administra. No es adorno: determina a quien se le reclama
    -- cuando el portal cambia, y la particion 12+9 de ADR-004 sale de aca.
    organismo     varchar(60)   NOT NULL,

    -- La particion de ADR-004. `sectorial` son los de la Ventanilla Unica;
    -- `sma` los de la Superintendencia.
    familia       varchar(12)   NOT NULL DEFAULT 'sectorial'
                  CHECK (familia IN ('sectorial', 'sma')),

    -- **`variable_rca` no es un valor de relleno.** ADR-004 lo dice explicito:
    -- SSA, SRCA y SIVEM dependen de lo que diga la RCA de cada instalacion, asi
    -- que sus fechas **no se pueden autogenerar**. Un catalogo que asuma una
    -- periodicidad fija por sistema no puede representarlos, y el calendario
    -- saldria inventado.
    periodicidad  varchar(16)
                  CHECK (periodicidad IS NULL OR periodicidad IN
                        ('tiempo_real','mensual','trimestral','semestral',
                         'anual','variable_rca')),

    -- Para el boton "Ir al sistema" (ADR-004). Sin esto la pantalla manda a la
    -- persona a buscar el portal a mano, que es el trabajo que se quiere evitar.
    url_oficial   text,

    -- **De donde salio esta fila.** Es la columna que impide que el catalogo se
    -- vuelva folclore: cada sistema dice quien lo respalda y cuando se miro.
    fuente        text          NOT NULL,

    -- Las fechas del calendario RETC cambian por resolucion cada ano
    -- (ADR-004). Sin vigencia, el catalogo envejece en silencio.
    valid_from    date,
    valid_to      date,

    -- `false` hasta que negocio confirme la lista. Ver la cabecera.
    active        boolean       NOT NULL DEFAULT false,

    created_at    timestamptz   NOT NULL DEFAULT now(),
    updated_at    timestamptz   NOT NULL DEFAULT now(),
    deleted_at    timestamptz,

    CONSTRAINT ck_retc_systems_vigencia
      CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

COMMENT ON TABLE retc_systems IS
  'Portales del ecosistema RETC ante los que se declara (ADR-004, #103). '
  'NO es sectors: sectors es el rubro CIIU de la empresa, esto es donde reporta. '
  'Catalogo global sin tenant_id: los portales son los mismos para todas.';
COMMENT ON COLUMN retc_systems.fuente IS
  'De donde salio la fila. Obligatoria a proposito: un catalogo normativo sin '
  'procedencia se vuelve imposible de auditar y de actualizar.';
COMMENT ON COLUMN retc_systems.active IS
  'false mientras negocio no confirme la lista. El seed inicial trae los 12 '
  'sectoriales del portal oficial; los 9 de la SMA que menciona ADR-004 no '
  'estan sembrados porque no hay fuente verificable.';

-- `deleted_at` desde el CREATE TABLE: `CRUDBase` solo filtra lo borrado si el
-- modelo tiene la columna, asi que agregarla despues deja un periodo en que
-- las filas dadas de baja siguen apareciendo.
CREATE INDEX IF NOT EXISTS ix_retc_systems_activos
    ON retc_systems (familia, code) WHERE deleted_at IS NULL;

-- Sin `tenant_id` no lleva politica RLS —no hay nada que aislar— pero **si
-- necesita GRANT**: el `GRANT ON ALL TABLES` de `01_schema` corrio una sola vez.
GRANT SELECT, INSERT, UPDATE, DELETE ON retc_systems TO ambienta_app;
GRANT USAGE, SELECT ON SEQUENCE retc_systems_id_seq TO ambienta_app;


-- ── La reportabilidad: que le toca a cada instalacion ───────────────────────

CREATE TABLE IF NOT EXISTS facility_retc_reporting (
    id              uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    facility_id     uuid         NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    retc_system_id  smallint     NOT NULL REFERENCES retc_systems(id),

    -- Los cinco estados de ADR-004, literales. `condicional` es el que da
    -- trabajo: significa "aplica si se cumple algo", y ese algo va en
    -- `condicion` — si no, nadie puede reconstruir por que se decidio asi.
    estado          varchar(16)  NOT NULL DEFAULT 'no'
                    CHECK (estado IN ('si','condicional','na','no','obligatorio')),
    condicion       text,

    -- Las respuestas del wizard que llevaron a este estado (genera RESPEL?,
    -- tiene bodega de sustancias peligrosas?, esta en zona con PPDA?).
    -- **Se guardan aunque ya esten resumidas en `estado`**: sin ellas, revisar
    -- la decision un ano despues obliga a repetir la entrevista.
    variables       jsonb        NOT NULL DEFAULT '{}'::jsonb,

    responsable_id  uuid         REFERENCES users(id),
    notas           text,

    created_at      timestamptz  NOT NULL DEFAULT now(),
    created_by      uuid,
    updated_at      timestamptz  NOT NULL DEFAULT now(),
    updated_by      uuid,
    deleted_at      timestamptz,

    -- Una instalacion tiene UN estado por sistema. Dos filas serian dos
    -- verdades sobre si hay que declarar, y la pantalla mostraria la que
    -- ordene primero.
    CONSTRAINT uq_facility_retc_reporting UNIQUE (facility_id, retc_system_id),

    -- Un estado condicional sin decir de que depende no se puede revisar
    -- despues: es la diferencia entre una decision y un recuerdo.
    CONSTRAINT ck_facility_retc_condicion
      CHECK (estado <> 'condicional' OR condicion IS NOT NULL)
);

COMMENT ON TABLE facility_retc_reporting IS
  'ReportabilidadInstalacion (ADR-004, #102): que sistemas del RETC aplican a '
  'una instalacion y con que estado. Se configura una vez en el onboarding.';

CREATE INDEX IF NOT EXISTS ix_facility_retc_reporting_facility
    ON facility_retc_reporting (tenant_id, facility_id) WHERE deleted_at IS NULL;

-- ── Aislamiento entre empresas ──────────────────────────────────────────────
--
-- Se declara aca porque el bucle de `01_schema` ya corrio. Sin esto la tabla
-- **no falla**: muestra la reportabilidad de todas las empresas, que es
-- exactamente lo que RLS existe para impedir. Y esta tabla dice donde declara
-- cada planta de cada cliente: es informacion competitiva.

ALTER TABLE facility_retc_reporting ENABLE ROW LEVEL SECURITY;
ALTER TABLE facility_retc_reporting FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON facility_retc_reporting;
CREATE POLICY tenant_isolation ON facility_retc_reporting
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON facility_retc_reporting TO ambienta_app;


-- ── Seed: los 12 sistemas sectoriales de la Ventanilla Unica ────────────────
--
-- Fuente: https://portalvu.mma.gob.cl — seccion "Sistemas Sectoriales",
-- consultada el 25-ago-2026. Coincide en numero con los "12 sistemas
-- sectoriales" de ADR-004:14.
--
-- **La periodicidad va NULL a proposito.** El portal lista los sistemas pero
-- no su calendario, y ADR-004 dice que las fechas cambian por resolucion cada
-- ano. Poner una periodicidad sin fuente seria fabricar un calendario que
-- despues genera vencimientos falsos — el peor error posible en este dominio.
--
-- `ON CONFLICT DO NOTHING`: idempotente, y **no pisa** lo que negocio haya
-- corregido a mano.

INSERT INTO retc_systems (code, name, organismo, familia, url_oficial, fuente) VALUES
  ('RUEA',    'Registro Unico de Emisiones Atmosfericas',                    'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('RFP',     'Registro de Fuentes y Procesos',                              'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('SINADER', 'Sistema Nacional de Declaracion de Residuos',                 'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('DAE',     'Sistema de Desempeno Ambiental y Empresarial',                'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('DJA',     'Declaracion Jurada Anual del RETC',                           'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('SISAT',   'Sistema de Seguimiento Atmosferico',                          'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('SICTER',  'Sistema de Informacion de Centrales Termoelectricas',         'SMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('RILES',   'Declaracion de Descargas de Residuos Industriales Liquidos',  'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('LEY_REP', 'Ley REP - Declaracion de Productos y Gestor',                 'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('SIV',     'Sistema de Impuesto Verde',                                   'MMA',    'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('SIDREP',  'Sistema de Seguimiento y Declaracion de Residuos Peligrosos', 'MINSAL', 'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026'),
  ('DASUPEL', 'Declaracion de Instalaciones de Almacenamiento de Sustancias Peligrosas', 'MINSAL', 'sectorial', 'https://portalvu.mma.gob.cl', 'portalvu.mma.gob.cl, consultado 25-ago-2026')
ON CONFLICT (code) DO NOTHING;
