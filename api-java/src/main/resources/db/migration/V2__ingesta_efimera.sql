-- Estados EN_COLA / INDEXADO_PENDIENTE_PURGA, motivo de error y Acta de Purga.
ALTER TABLE documentos DROP CONSTRAINT documentos_estado_indexacion_check;
ALTER TABLE documentos ADD CONSTRAINT documentos_estado_indexacion_check
    CHECK (estado_indexacion IN ('RECIBIDO', 'VALIDANDO', 'EN_COLA', 'EXTRAYENDO_OCR', 'FRAGMENTANDO',
                                 'VECTORIZANDO', 'INDEXADO_PENDIENTE_PURGA', 'INDEXADO_Y_PURGADO',
                                 'ERROR_PURGADO'));
ALTER TABLE documentos ADD COLUMN motivo_error TEXT;
ALTER TABLE documentos ADD COLUMN purga_programada_at TIMESTAMPTZ;
ALTER TABLE documentos ADD COLUMN estado_actualizado_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Indice para el barrido: documentos aun no finalizados.
CREATE INDEX idx_documentos_no_finales ON documentos (estado_indexacion)
    WHERE estado_indexacion NOT IN ('INDEXADO_Y_PURGADO', 'ERROR_PURGADO');

CREATE TABLE actas_purga (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    documento_id UUID REFERENCES documentos(id) ON DELETE SET NULL,
    sha256_original CHAR(64),
    motivo VARCHAR(30) NOT NULL CHECK (motivo IN ('INDEXADO', 'ERROR_VALIDACION',
        'ERROR_PROCESAMIENTO', 'TIMEOUT', 'HUERFANO', 'DOCUMENTO_ELIMINADO')),
    chunks_esperados INT,
    chunks_verificados INT,
    archivo_existia BOOLEAN NOT NULL,
    detalle TEXT,
    purged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_actas_documento ON actas_purga (documento_id);
CREATE INDEX idx_actas_tenant ON actas_purga (tenant_id, purged_at DESC);
