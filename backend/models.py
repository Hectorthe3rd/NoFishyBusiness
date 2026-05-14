"""
backend/models.py

Pydantic data models shared across the NoFishyBusiness backend.
"""

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# UserContext — Future-proofing for user profile system
# ---------------------------------------------------------------------------
# Even without user accounts, this model is passed into every LLM call so
# the PromptFactory can adjust tone and depth based on experience level.
# When accounts are added, populate this from the session/JWT instead of
# using the GuestProfile default.

class UserContext(BaseModel):
    """
    Represents the calling user's profile for contextual prompt generation.

    Fields:
        experience_level: "beginner" | "intermediate" | "advanced" | "guest"
            Controls how technical the LLM's language is:
            - beginner   → defines jargon, uses analogies, reassuring tone
            - intermediate → assumes basic knowledge, focuses on nuance
            - advanced   → scientific names, precise parameters, technical depth
            - guest      → safe middle ground (default when level is unknown)

        current_tanks: List of tank descriptions the user has mentioned.
            Used in future to personalise maintenance and setup advice.

        recent_queries: Last few questions asked, for context continuity.
            Used in future to avoid repeating the same advice.
    """
    experience_level: str = Field(
        default="guest",
        description="User's aquarium experience level"
    )
    current_tanks: list[str] = Field(
        default_factory=list,
        description="Tank descriptions the user has mentioned"
    )
    recent_queries: list[str] = Field(
        default_factory=list,
        description="Recent questions for context continuity"
    )

    @classmethod
    def guest(cls) -> "UserContext":
        """
        Return the default GuestProfile used when no user context is available.

        This is the hardcoded fallback that keeps the prompt system working
        before user accounts are implemented. When accounts are added, replace
        this with a session lookup.
        """
        return cls(
            experience_level="guest",
            current_tanks=[],
            recent_queries=[],
        )

    @classmethod
    def from_experience_level(cls, level: str) -> "UserContext":
        """
        Convenience constructor — create a UserContext from just an experience level.

        Used by the Setup Guide and other tools that receive experience_level
        as a direct input field.
        """
        # Normalise to valid values; default to "guest" if unrecognised
        valid = {"beginner", "intermediate", "advanced", "guest"}
        return cls(experience_level=level if level in valid else "guest")


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------

class KBRecord(BaseModel):
    """A single record retrieved from the knowledge base."""

    id: int
    species_name: str
    category: str
    content: str


# ---------------------------------------------------------------------------
# Volume Calculator
# ---------------------------------------------------------------------------

class VolumeRequest(BaseModel):
    length: float = Field(gt=0, description="Tank length in inches")
    width: float = Field(gt=0, description="Tank width in inches")
    depth: float = Field(gt=0, description="Water depth in inches")


class VolumeResponse(BaseModel):
    volume_gallons: float
    weight_pounds: float


# ---------------------------------------------------------------------------
# Species Tool
# ---------------------------------------------------------------------------

class SpeciesRequest(BaseModel):
    species_name: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Maintenance Guide
# ---------------------------------------------------------------------------

class MaintenanceRequest(BaseModel):
    tank_gallons: float = Field(gt=0)
    fish_count: int = Field(ge=0)
    fish_species: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Setup Guide
# ---------------------------------------------------------------------------

class SetupRequest(BaseModel):
    tank_gallons: float = Field(gt=0, le=500)
    experience_level: str = Field(pattern="^(beginner|intermediate|advanced)$")


# ---------------------------------------------------------------------------
# Chemistry Analyzer
# ---------------------------------------------------------------------------

class ChemistryRequest(BaseModel):
    description: str
    image_base64: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Assistant
# ---------------------------------------------------------------------------

class AssistantRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[dict] = Field(default_factory=list, max_length=10)


# ---------------------------------------------------------------------------
# Error Response
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    message: str
    error_type: str
