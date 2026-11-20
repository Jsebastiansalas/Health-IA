-- Base de medicamentos de Colombia (datos abiertos de INVIMA, datos.gov.co, licencia CC BY-SA 4.0).
-- Son datos de referencia PÚBLICOS: no llevan tenant_id ni contenido de clientes. La carga la hace
-- el agente (python -m app.cli cargar-medicamentos); aquí solo se define el esquema.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Un registro por CUM (código único de medicamentos = expediente INVIMA + consecutivo) y por estado
-- (fuente). Los principios activos y los roles (titular, fabricante, importador…) del conjunto de
-- origen vienen en varias filas por CUM; se agrupan aquí en JSONB.
CREATE TABLE med_cum (
    id                  BIGSERIAL PRIMARY KEY,
    fuente              VARCHAR(12)  NOT NULL CHECK (fuente IN ('VIGENTE', 'RENOVACION', 'OTROS', 'VENCIDO')),
    expediente_invima   VARCHAR(20)  NOT NULL,
    consecutivo         VARCHAR(10)  NOT NULL,
    producto            VARCHAR(400),
    titular             VARCHAR(300),
    registro_sanitario  VARCHAR(60),
    estado_registro     VARCHAR(60),
    fecha_expedicion    DATE,
    fecha_vencimiento   DATE,
    estado_cum          VARCHAR(40),
    fecha_activo        DATE,
    fecha_inactivo      DATE,
    descripcion_comercial TEXT,
    cantidad_cum        VARCHAR(40),
    unidad              VARCHAR(20),
    muestra_medica      VARCHAR(10),
    atc                 VARCHAR(20),
    descripcion_atc     VARCHAR(300),
    via_administracion  VARCHAR(120),
    forma_farmaceutica  VARCHAR(200),
    principios          JSONB NOT NULL DEFAULT '[]'::jsonb,
    roles               JSONB NOT NULL DEFAULT '[]'::jsonb,
    ium                 VARCHAR(40),
    -- Texto normalizado (minúsculas, sin tildes) para búsqueda; lo calcula la carga.
    producto_n          TEXT,
    titular_n           TEXT,
    busqueda            TEXT NOT NULL,
    fts                 TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', busqueda)) STORED,
    cargado_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_med_cum_fuente ON med_cum (fuente);
CREATE INDEX idx_med_cum_cum ON med_cum (expediente_invima, consecutivo);
CREATE INDEX idx_med_cum_registro ON med_cum (registro_sanitario);
CREATE INDEX idx_med_cum_atc ON med_cum (atc text_pattern_ops);
CREATE INDEX idx_med_cum_fts ON med_cum USING GIN (fts);
CREATE INDEX idx_med_cum_busqueda_trgm ON med_cum USING GIN (busqueda gin_trgm_ops);
CREATE INDEX idx_med_cum_producto_trgm ON med_cum USING GIN (producto_n gin_trgm_ops);
CREATE INDEX idx_med_cum_titular_trgm ON med_cum USING GIN (titular_n gin_trgm_ops);

-- Precios máximos de venta regulados (Comisión Nacional de Precios de Medicamentos y Dispositivos Médicos).
CREATE TABLE med_precio (
    id                  BIGSERIAL PRIMARY KEY,
    cum                 VARCHAR(30) NOT NULL,
    mercado_relevante   VARCHAR(300),
    medicamento         TEXT,
    cantidad_unidad     VARCHAR(40),
    unidad_medida       VARCHAR(40),
    precio_institucional NUMERIC(16, 2),
    margen_ips          NUMERIC(16, 2),
    precio_comercial    NUMERIC(16, 2),
    precio_final_comercial NUMERIC(16, 2),
    circular            VARCHAR(120),
    vigencia_desde      DATE,
    busqueda            TEXT NOT NULL,
    cargado_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_med_precio_cum ON med_precio (cum);
CREATE INDEX idx_med_precio_busqueda_trgm ON med_precio USING GIN (busqueda gin_trgm_ops);

-- Procedencia de cada conjunto: qué se cargó, de dónde y cuándo (se muestra al usuario).
CREATE TABLE med_carga (
    fuente      VARCHAR(12) PRIMARY KEY,
    dataset_id  VARCHAR(12) NOT NULL,
    nombre      VARCHAR(200) NOT NULL,
    filas       INTEGER NOT NULL,
    cargado_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
