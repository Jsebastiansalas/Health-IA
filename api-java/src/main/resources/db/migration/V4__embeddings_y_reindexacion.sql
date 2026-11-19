-- Proveedor Gemini por defecto, re-vectorizacion sin PDF y aviso de version OCR.
ALTER TABLE expedientes ALTER COLUMN embedding_model_activo SET DEFAULT 'gemini-embedding-001';

UPDATE expedientes e SET embedding_model_activo = 'gemini-embedding-001', embedding_dimension = 1536
WHERE NOT EXISTS (
    SELECT 1 FROM fragmentos f WHERE f.expediente_id = e.id AND f.embedding IS NOT NULL
);

UPDATE documentos d SET embedding_model = e.embedding_model_activo
FROM expedientes e
WHERE d.expediente_id = e.id
  AND d.estado_indexacion NOT IN ('INDEXADO_Y_PURGADO', 'ERROR_PURGADO', 'INDEXADO_PENDIENTE_PURGA');

ALTER TABLE documentos ADD COLUMN paginas_ocr INT NOT NULL DEFAULT 0;

CREATE TABLE reindexaciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    modelo_origen VARCHAR(80) NOT NULL,
    modelo_destino VARCHAR(80) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE', 'EN_PROCESO', 'COMPLETADA', 'ERROR')),
    total_fragmentos INT NOT NULL DEFAULT 0,
    fragmentos_procesados INT NOT NULL DEFAULT 0,
    error TEXT,
    created_by UUID NOT NULL REFERENCES usuarios(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- Como maximo una reindexacion activa por expediente.
CREATE UNIQUE INDEX uq_reindexacion_activa ON reindexaciones (expediente_id)
    WHERE estado IN ('PENDIENTE', 'EN_PROCESO');

CREATE TABLE fragmentos_reindex (
    reindexacion_id UUID NOT NULL REFERENCES reindexaciones(id) ON DELETE CASCADE,
    fragmento_id UUID NOT NULL REFERENCES fragmentos(id) ON DELETE CASCADE,
    embedding vector(1536) NOT NULL,
    PRIMARY KEY (reindexacion_id, fragmento_id)
);
