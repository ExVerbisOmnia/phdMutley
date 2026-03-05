"""initial schema from init_database

Revision ID: 05bf47339860
Revises:
Create Date: 2026-03-04 12:35:20.105461

Baseline migration capturing the existing schema from init_database.py.
This migration should be stamped (not run) on existing databases.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "05bf47339860"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all tables from init_database.py ORM models."""

    # cases
    op.create_table(
        "cases",
        sa.Column("case_id", sa.String(100), primary_key=True, comment="Unique case identifier"),
        sa.Column("case_name", sa.String(500), nullable=False, comment="Official case name"),
        sa.Column(
            "case_name_non_english", sa.String(500), comment="Case name in original language"
        ),
        sa.Column("case_number", sa.String(200), comment="Court docket/reference number"),
        sa.Column("jurisdiction", sa.String(300), nullable=False, comment="Court jurisdiction"),
        sa.Column("geographies", sa.String(300), comment="Geographic locations"),
        sa.Column("geography_iso", sa.String(100), comment="ISO country codes"),
        sa.Column("region", sa.String(50), comment="Global North or Global South"),
        sa.Column("case_filing_year", sa.Float, comment="Year case was initially filed"),
        sa.Column("document_filing_date", sa.DateTime, comment="Date decision was issued"),
        sa.Column("last_event_date", sa.DateTime, comment="Most recent case activity date"),
        sa.Column("case_summary", sa.Text, comment="Brief description of case context"),
        sa.Column("case_status", sa.String(500), comment="Current status of the case"),
        sa.Column("case_outcome", sa.String(500), comment="Outcome/disposition"),
        sa.Column("case_categories", sa.Text, comment="Thematic classification"),
        sa.Column("language", sa.String(100), comment="Primary language of case documents"),
        sa.Column("principal_laws", sa.Text, comment="Key legal provisions cited"),
        sa.Column("at_issue", sa.Text, comment="Main legal issues"),
        sa.Column("case_url", sa.String(500), comment="Link to Climate Case Chart page"),
        sa.Column("metadata_data", sa.JSON, comment="Additional metadata from Excel"),
        sa.Column("created_at", sa.DateTime, comment="Record creation timestamp"),
        sa.Column("updated_at", sa.DateTime, comment="Record last update timestamp"),
    )

    # documents
    op.create_table(
        "documents",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(100),
            sa.ForeignKey("cases.case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_title", sa.String(500)),
        sa.Column("document_type", sa.String(100)),
        sa.Column("document_date", sa.DateTime),
        sa.Column("document_summary", sa.Text),
        sa.Column("document_url", sa.String(500)),
        sa.Column("document_content_url", sa.String(500)),
        sa.Column("pdf_file_path", sa.String(500)),
        sa.Column("pdf_downloaded", sa.Boolean, default=False),
        sa.Column("download_date", sa.DateTime),
        sa.Column("download_error", sa.Text),
        sa.Column("file_size_bytes", sa.Integer),
        sa.Column("page_count", sa.Integer),
        sa.Column("is_scanned", sa.Boolean),
        sa.Column("is_decision", sa.Boolean),
        sa.Column("classification_confidence", sa.Float),
        sa.Column("decision_classification_method", sa.String(50)),
        sa.Column("decision_classification_confidence", sa.Float),
        sa.Column("decision_classification_date", sa.DateTime),
        sa.Column("metadata_data", sa.JSON),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # extracted_text
    op.create_table(
        "extracted_text",
        sa.Column("text_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("extraction_method", sa.String(50)),
        sa.Column("extraction_date", sa.DateTime),
        sa.Column("extraction_quality", sa.String(20)),
        sa.Column("extraction_notes", sa.Text),
        sa.Column("raw_text", sa.Text),
        sa.Column("processed_text", sa.Text),
        sa.Column("word_count", sa.Integer),
        sa.Column("character_count", sa.Integer),
        sa.Column("paragraph_count", sa.Integer),
        sa.Column("sentence_count", sa.Integer),
        sa.Column("language_detected", sa.String(10)),
        sa.Column("language_confidence", sa.Float),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    # citation_extraction_phased
    op.create_table(
        "citation_extraction_phased",
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_id", sa.String(100), sa.ForeignKey("cases.case_id", ondelete="CASCADE")),
        sa.Column("source_jurisdiction", sa.String(200)),
        sa.Column("source_region", sa.String(50)),
        sa.Column("case_name", sa.String(500)),
        sa.Column("raw_citation_text", sa.Text),
        sa.Column("section_heading", sa.String(500)),
        sa.Column("location_in_document", sa.String(50)),
        sa.Column("case_law_origin", sa.String(200)),
        sa.Column("case_law_region", sa.String(50)),
        sa.Column("origin_identification_tier", sa.Integer),
        sa.Column("origin_confidence", sa.DECIMAL(3, 2)),
        sa.Column("citation_type", sa.String(50)),
        sa.Column("is_cross_jurisdictional", sa.Boolean),
        sa.Column("cited_court", sa.String(500)),
        sa.Column("cited_year", sa.Integer),
        sa.Column("cited_case_citation", sa.String(500)),
        sa.Column("phase_2_model", sa.String(50)),
        sa.Column("phase_3_model", sa.String(50)),
        sa.Column("phase_4_model", sa.String(50)),
        sa.Column("processing_time_seconds", sa.DECIMAL(10, 2)),
        sa.Column("api_calls_used", sa.Integer),
        sa.Column("requires_manual_review", sa.Boolean, default=False),
        sa.Column("manual_review_reason", sa.Text),
        sa.Column("reviewed_by", sa.String(100)),
        sa.Column("reviewed_at", sa.TIMESTAMP),
        sa.Column("created_at", sa.TIMESTAMP),
        sa.Column("updated_at", sa.TIMESTAMP),
    )

    # citation_extraction_phased_summary
    op.create_table(
        "citation_extraction_phased_summary",
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("total_references_extracted", sa.Integer, default=0),
        sa.Column("foreign_citations_count", sa.Integer, default=0),
        sa.Column("international_citations_count", sa.Integer, default=0),
        sa.Column("foreign_international_citations_count", sa.Integer, default=0),
        sa.Column("total_api_calls", sa.Integer, default=0),
        sa.Column("total_tokens_input", sa.Integer, default=0),
        sa.Column("total_tokens_output", sa.Integer, default=0),
        sa.Column("total_cost_usd", sa.DECIMAL(10, 4)),
        sa.Column("extraction_started_at", sa.TIMESTAMP),
        sa.Column("extraction_completed_at", sa.TIMESTAMP),
        sa.Column("total_processing_time_seconds", sa.DECIMAL(10, 2)),
        sa.Column("extraction_success", sa.Boolean, default=False),
        sa.Column("extraction_error", sa.Text),
        sa.Column("average_confidence", sa.DECIMAL(3, 2)),
        sa.Column("items_requiring_review", sa.Integer, default=0),
        sa.Column("created_at", sa.TIMESTAMP),
        sa.Column("updated_at", sa.TIMESTAMP),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("citation_extraction_phased_summary")
    op.drop_table("citation_extraction_phased")
    op.drop_table("extracted_text")
    op.drop_table("documents")
    op.drop_table("cases")
