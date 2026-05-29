"""add text_md column to extracted_text

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-04

Phase 3: Markdown text extraction via pymupdf4llm.
Adds nullable text_md column alongside existing raw_text/processed_text.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str = "a1b2c3d4e5f6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "extracted_text",
        sa.Column(
            "text_md",
            sa.Text(),
            nullable=True,
            comment="Markdown-formatted text (pymupdf4llm)",
        ),
    )


def downgrade() -> None:
    op.drop_column("extracted_text", "text_md")
