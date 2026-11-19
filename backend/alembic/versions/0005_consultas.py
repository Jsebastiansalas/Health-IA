"""Sprint 5: trazabilidad de las consultas RAG.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-19
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_consultas_expediente ON consultas (tenant_id, expediente_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS consultas")
