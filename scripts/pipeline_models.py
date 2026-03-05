"""
Pipeline Data Models and Enums
==============================
Shared Pydantic models and enums for the citation extraction pipeline.
Consolidates duplicate definitions (SixfoldType was defined 3 times).

Usage:
    from pipeline_models import Region, SixfoldType, ClassificationResult
"""

from enum import StrEnum

from pydantic import BaseModel, Field

# =============================================================================
# ENUMS — consolidated from 3 duplicate definitions
# =============================================================================


class Region(StrEnum):
    """Geographic region classification for courts and jurisdictions."""

    GLOBAL_NORTH = "Global North"
    GLOBAL_SOUTH = "Global South"
    INTERNATIONAL = "International"
    UNKNOWN = "Unknown"


class SixfoldType(StrEnum):
    """
    The six citation classification types for transnational judicial dialogue.

    Each type represents a distinct pattern of cross-jurisdictional citation:
    1. National → National (same or different country)
    2. National → International (member court)
    3. National → International (non-member court)
    4. International → International
    5. International → National (member state)
    6. International → National (non-member state)
    """

    FOREIGN = "Foreign Citation"
    INTERNATIONAL = "International Citation"
    FOREIGN_INTERNATIONAL = "Foreign International Citation"
    INTER_SYSTEM = "Inter-System Citation"
    MEMBER_STATE = "Member-State Citation"
    NON_MEMBER = "Non-Member Citation"


# =============================================================================
# DATA MODELS — documentation-first, optional validation
# =============================================================================


class GeminiResponse(BaseModel):
    """Matches the dict returned by call_gemini() in gemini_client.py."""

    raw: str = ""
    parsed: dict | None = None
    tokens_in: int = 0
    tokens_out: int = 0


class ClassificationResult(BaseModel):
    """Result from decision classification (judicial vs. other)."""

    is_decision: bool | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str = ""


class CitationReference(BaseModel):
    """A single citation extracted from a document."""

    case_name: str = ""
    raw_text: str = ""
    context_before: str = ""
    context_after: str = ""


class OriginResult(BaseModel):
    """Result from origin identification (which court/jurisdiction a citation belongs to)."""

    origin: str = ""
    region: str = ""
    court: str = ""
    year: int | None = None
    tier: int = Field(ge=1, le=3, default=1)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    method: str = ""
