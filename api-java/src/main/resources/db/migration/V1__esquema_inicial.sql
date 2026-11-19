-- Esquema inicial MedTender RAG. Fuente unica del esquema: tanto la API Java como el agente Python
-- (y sus pruebas) lo usan tal cual. Traduccion 1:1 de las migraciones Alembic 0001-0006.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(150) NOT NULL,
    nit VARCHAR(50) UNIQUE NOT NULL,
    politica_borrado VARCHAR(30) NOT NULL DEFAULT 'INMEDIATO'
        CHECK (politica_borrado IN ('INMEDIATO', 'DIFERIDO_1H')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    rol_global VARCHAR(40) NOT NULL
        CHECK (rol_global IN ('ADMIN_TENANT', 'JURIDICO', 'AUDITOR_MEDICO', 'BIOMEDICO', 'LECTOR')),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usuarios_tenant ON usuarios (tenant_id);

CREATE TABLE expedientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    codigo_expediente VARCHAR(80) NOT NULL,
    titulo VARCHAR(250) NOT NULL,
    entidad_contratante VARCHAR(200),
    tipo_expediente VARCHAR(50) NOT NULL
        CHECK (tipo_expediente IN ('LICITACION_MEDICAMENTOS', 'DOTACION_BIOMEDICA', 'AUDITORIA_CLINICA')),
    estado VARCHAR(40) NOT NULL DEFAULT 'ABIERTO'
        CHECK (estado IN ('ABIERTO', 'CERRADO', 'ARCHIVADO')),
    embedding_model_activo VARCHAR(80) NOT NULL DEFAULT 'text-embedding-3-small',
    embedding_dimension INT NOT NULL DEFAULT 1536,
    created_by UUID NOT NULL REFERENCES usuarios(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, codigo_expediente)
);

CREATE TABLE expediente_permisos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    permiso VARCHAR(30) NOT NULL CHECK (permiso IN ('LECTOR', 'EDITOR', 'ADMIN')),
    UNIQUE (expediente_id, usuario_id)
);
CREATE INDEX idx_permisos_usuario ON expediente_permisos (tenant_id, usuario_id);

CREATE TABLE documentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    nombre_archivo_original VARCHAR(255) NOT NULL,
    tipo_documento VARCHAR(50) NOT NULL
        CHECK (tipo_documento IN ('PLIEGO', 'ADENDA', 'FICHA_TECNICA', 'REGISTRO_SANITARIO',
                                  'HISTORIA_CLINICA', 'PRESUPUESTO')),
    numero_adenda INT DEFAULT 0,
    sha256_original CHAR(64) NOT NULL,
    tamano_bytes BIGINT NOT NULL,
    total_paginas INT,
    estado_indexacion VARCHAR(40) NOT NULL
        CHECK (estado_indexacion IN ('RECIBIDO', 'VALIDANDO', 'EXTRAYENDO_OCR', 'FRAGMENTANDO',
                                     'VECTORIZANDO', 'INDEXADO_Y_PURGADO', 'ERROR_PURGADO')),
    ocr_version VARCHAR(30) NOT NULL DEFAULT 'tesseract-5.x-v1',
    extractor_version VARCHAR(30) NOT NULL DEFAULT 'pymupdf-pdfplumber-v1',
    embedding_model VARCHAR(80) NOT NULL,
    total_chunks_esperados INT DEFAULT 0,
    total_chunks_guardados INT DEFAULT 0,
    temp_file_purged BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    purged_at TIMESTAMPTZ
);
CREATE INDEX idx_documentos_tenant_expediente ON documentos (tenant_id, expediente_id);
CREATE INDEX idx_documentos_sha256 ON documentos (expediente_id, sha256_original);

CREATE TABLE fragmentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    documento_id UUID NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    orden INT NOT NULL,
    pagina_inicio INT NOT NULL,
    pagina_fin INT NOT NULL,
    seccion VARCHAR(255) NOT NULL,
    contenido_texto TEXT NOT NULL,
    contenido_vectorizado TEXT NOT NULL,
    token_count INT NOT NULL,
    embedding_model VARCHAR(80) NOT NULL,
    embedding vector(1536) NOT NULL,
    fts_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('spanish', coalesce(seccion, '') || ' ' || coalesce(contenido_texto, ''))
    ) STORED,
    metadata_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (documento_id, orden)
);

CREATE INDEX idx_fragmentos_tenant_expediente ON fragmentos (tenant_id, expediente_id);
CREATE INDEX idx_fragmentos_doc_orden ON fragmentos (documento_id, orden);
CREATE INDEX idx_fragmentos_fts ON fragmentos USING GIN (fts_vector);
CREATE INDEX idx_fragmentos_embedding_hnsw ON fragmentos
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
