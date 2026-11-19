"""Sprint 3: los fragmentos se guardan antes de vectorizar (embedding NULL hasta el Sprint 4).

La verificación del Paso 9 cuenta COUNT(fragmentos WHERE embedding IS NOT NULL), lo que supone
fragmentos persistidos sin vector. Un documento solo es consultable en INDEXADO_*, así que los
fragmentos sin vector nunca llegan a una búsqueda.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE fragmentos ALTER COLUMN embedding DROP NOT NULL")
    op.execute(
        "ALTER TABLE documentos ALTER COLUMN extractor_version SET DEFAULT 'pdfium-pdfplumber-v1'"
    )


def downgrade() -> None:
    op.execute("DELETE FROM fragmentos WHERE embedding IS NULL")
    op.execute("ALTER TABLE fragmentos ALTER COLUMN embedding SET NOT NULL")
    op.execute(
        "ALTER TABLE documentos ALTER COLUMN extractor_version SET DEFAULT 'pymupdf-pdfplumber-v1'"
    )
