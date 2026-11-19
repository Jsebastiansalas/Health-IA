"""Sprint 2: estados EN_COLA / INDEXADO_PENDIENTE_PURGA, motivo de error y Acta de Purga.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ESTADOS = (
    "'RECIBIDO', 'VALIDANDO', 'EN_COLA', 'EXTRAYENDO_OCR', 'FRAGMENTANDO', 'VECTORIZANDO', "
    "'INDEXADO_PENDIENTE_PURGA', 'INDEXADO_Y_PURGADO', 'ERROR_PURGADO'"
)

UPGRADE = [
    "ALTER TABLE documentos DROP CONSTRAINT documentos_estado_indexacion_check",
    f"ALTER TABLE documentos ADD CONSTRAINT documentos_estado_indexacion_check "
    f"CHECK (estado_indexacion IN ({ESTADOS}))",
    "ALTER TABLE documentos ADD COLUMN motivo_error TEXT",
    "ALTER TABLE documentos ADD COLUMN purga_programada_at TIMESTAMPTZ",
    "ALTER TABLE documentos ADD COLUMN estado_actualizado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    # Índice para el barrido: documentos aún no finalizados.
    "CREATE INDEX idx_documentos_no_finales ON documentos (estado_indexacion) "
    "WHERE estado_indexacion NOT IN ('INDEXADO_Y_PURGADO', 'ERROR_PURGADO')",
    """
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
    )
    """,
    "CREATE INDEX idx_actas_documento ON actas_purga (documento_id)",
    "CREATE INDEX idx_actas_tenant ON actas_purga (tenant_id, purged_at DESC)",
]


def upgrade() -> None:
    for sentencia in UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS actas_purga")
    op.execute("DROP INDEX IF EXISTS idx_documentos_no_finales")
    op.execute(
        "ALTER TABLE documentos DROP COLUMN IF EXISTS motivo_error, "
        "DROP COLUMN IF EXISTS purga_programada_at, DROP COLUMN IF EXISTS estado_actualizado_at"
    )
