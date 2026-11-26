-- Trazabilidad de las consultas RAG.
CREATE TABLE consultas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    pregunta TEXT NOT NULL,
    respuesta JSONB NOT NULL,
    sin_evidencia BOOLEAN NOT NULL,
    modelo_embeddings VARCHAR(80) NOT NULL,
    modelo_llm VARCHAR(80),
    fragmentos_recuperados INT NOT NULL DEFAULT 0,
    latencia_ms INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_consultas_expediente ON consultas (tenant_id, expediente_id, created_at DESC);
