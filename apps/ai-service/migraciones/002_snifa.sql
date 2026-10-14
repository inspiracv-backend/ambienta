-- Datos abiertos de la SMA (SNIFA), SPEC-10.
--
-- Son públicos: no llevan tenant_id ni RLS. Los escribe el sincronizador y los lee el servicio.
-- Cada corrida reemplaza un conjunto entero en una transacción: nunca se ve a medio cargar.
--
-- Verificado el 21/09/2026: la SMA publica estos datos como archivos en carpetas públicas de
-- Google Drive (snifa.sma.gob.cl/DatosAbiertos). No hay API; la que describe el ADD de Ambienta
-- (/DatosAbiertos/expedientes?rut=) responde 404. Y ningún conjunto trae RUT: todo se cruza por
-- el id de unidad fiscalizable.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE snifa_unidad (
    id              integer PRIMARY KEY,           -- UnidadFiscalizableId
    nombre          text NOT NULL,
    region          text,
    comuna          text,
    latitud         double precision,
    longitud        double precision,
    categoria       text,
    subcategoria    text,
    enlace          text
);
CREATE INDEX ix_snifa_unidad_nombre ON snifa_unidad USING gin (nombre gin_trgm_ops);

CREATE TABLE snifa_instrumento (
    unidad_id       integer NOT NULL,
    instrumento_id  integer NOT NULL,
    sigla           text,                          -- RCA, PPDA, NE...
    descripcion     text,
    detalle         text,
    id_sea          text,
    enlace          text,
    PRIMARY KEY (unidad_id, instrumento_id)
);

CREATE TABLE snifa_sancionatorio (
    id              integer PRIMARY KEY,           -- ProcesoSancionId
    expediente      text NOT NULL,
    tipo            text,
    estado          text,
    fecha_inicio    date,
    fecha_termino   date,
    programa_cumplimiento boolean,
    multa_uta       numeric,
    enlace          text,
    unidad_id       integer
);
CREATE INDEX ix_snifa_sanc_unidad ON snifa_sancionatorio (unidad_id);

CREATE TABLE snifa_fiscalizacion (
    id              integer PRIMARY KEY,           -- ProcesoFiscalizacionId
    expediente      text NOT NULL,
    anio            integer,
    mes             integer,
    organismo       text,
    enlace          text,
    unidad_id       integer
);
CREATE INDEX ix_snifa_fisc_unidad ON snifa_fiscalizacion (unidad_id);

CREATE TABLE snifa_carga (
    conjunto        text PRIMARY KEY,              -- sancionatorios | unidades | fiscalizaciones
    archivo_id      text NOT NULL,
    sha256          text NOT NULL,
    filas           integer NOT NULL,
    actualizado_sma text,                          -- FechaActualizacion que declara la SMA
    cargado_en      timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT ON snifa_unidad, snifa_instrumento, snifa_sancionatorio, snifa_fiscalizacion, snifa_carga
    TO ia_consulta, ia_sincronizador;
GRANT INSERT, UPDATE, DELETE, TRUNCATE
    ON snifa_unidad, snifa_instrumento, snifa_sancionatorio, snifa_fiscalizacion, snifa_carga
    TO ia_sincronizador;
