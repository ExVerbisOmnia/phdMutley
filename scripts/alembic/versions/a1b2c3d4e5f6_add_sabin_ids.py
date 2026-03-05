"""add sabin IDs to cases and documents

Revision ID: a1b2c3d4e5f6
Revises: 05bf47339860
Create Date: 2026-03-04

Decision D4: Store original Sabin Center identifiers (slugs + internal IDs)
so the knowledge base and Sabin-filter can reference them in later phases.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "05bf47339860"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- cases table --
    op.add_column(
        "cases",
        sa.Column(
            "sabin_case_id",
            sa.String(200),
            nullable=True,
            comment="Original Sabin slug (e.g. 'maules-creek-..._bed9')",
        ),
    )
    op.add_column(
        "cases",
        sa.Column(
            "sabin_internal_case_id",
            sa.String(100),
            nullable=True,
            comment="Sabin internal reference (e.g. 'Sabin.family.130691.0')",
        ),
    )
    op.create_unique_constraint("uq_cases_sabin_case_id", "cases", ["sabin_case_id"])

    # -- documents table --
    op.add_column(
        "documents",
        sa.Column(
            "sabin_document_id",
            sa.String(200),
            nullable=True,
            comment="Original Sabin slug (e.g. 'maules-creek-..._491c')",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "sabin_internal_document_id",
            sa.String(100),
            nullable=True,
            comment="Sabin internal reference (e.g. 'Sabin.document.130691.130693')",
        ),
    )
    op.create_unique_constraint(
        "uq_documents_sabin_document_id", "documents", ["sabin_document_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_sabin_document_id", "documents", type_="unique")
    op.drop_column("documents", "sabin_internal_document_id")
    op.drop_column("documents", "sabin_document_id")
    op.drop_constraint("uq_cases_sabin_case_id", "cases", type_="unique")
    op.drop_column("cases", "sabin_internal_case_id")
    op.drop_column("cases", "sabin_case_id")
