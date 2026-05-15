"""
backend/tools/setup.py

Setup Guide tool for NoFishyBusiness.

Provides beginner-friendly fish, plant, and aquascaping recommendations for a
new aquarium based on tank size, experience level, and challenge level.

Enhancements:
  - Unit toggle: accepts gallons or liters (converts to gallons before processing).
  - Pond logic: tanks > 500 gallons pivot to outdoor/pond species.
  - Challenge level: "basic" / "intermediate" / "advanced" — cross-referenced
    with experience_level to produce the right recommendation style.
  - Tank size expanded to 2000 gallons.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1
"""

import json
import os

import openai
from dotenv import load_dotenv

from backend import logger
from backend import token_budget
from backend.models import UserContext
from backend.prompt_factory import PromptFactory
from backend.rag import RAGError, retrieve

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LITERS_TO_GALLONS = 0.264172   # 1 liter = 0.264172 US gallons

# ---------------------------------------------------------------------------
# OpenAI client (lazy-initialised once)
# ---------------------------------------------------------------------------

load_dotenv()
_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    """Return a cached OpenAI client, creating it on first call."""
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_setup_guide(
    tank_gallons: float,
    experience_level: str,
    unit: str = "gallons",
    challenge_level: str = "intermediate",
) -> dict:
    """Return beginner fish, plant, and aquascaping recommendations.

    Workflow:
      1. Query the RAG pipeline with a beginner-focused search string.
      2. If no records are returned, return a not-found message (no LLM call).
      3. Truncate the concatenated context to 2000 tokens.
      4. Call OpenAI (max_tokens=1500) with a structured JSON prompt.
      5. Parse and return the JSON response.

    Args:
        tank_gallons:     Tank volume in US gallons (must be > 0 and ≤ 500).
        experience_level: One of "beginner", "intermediate", or "advanced".

    Returns:
        On success — a dict with keys:
          - ``fish_recommendations``: list of dicts with name, difficulty,
            min_tank_gallons (≥3 easy-rated fish).
          - ``plant_recommendations``: list of dicts with name, difficulty
            (≥2 easy-rated plants).
          - ``aquascaping_idea``: dict with substrate, hardscape, plant_zones.

        On empty RAG result — a dict with key ``message`` describing the
        not-found condition (HTTP 200).

        On RAG error — a JSONResponse with HTTP 503 and error_type "rag_error".

        On OpenAI error — a JSONResponse with HTTP 502 and error_type
        "api_error".
    """
    from fastapi.responses import JSONResponse  # local import to avoid circular

    # ------------------------------------------------------------------
    # 0. Unit conversion — liters → gallons
    # ------------------------------------------------------------------
    if unit == "liters":
        tank_gallons = round(tank_gallons * _LITERS_TO_GALLONS, 2)

    # ------------------------------------------------------------------
    # 1. Determine mode: pond (>500 gal) vs aquarium
    # ------------------------------------------------------------------
    is_pond = tank_gallons > 500

    # ------------------------------------------------------------------
    # 2. RAG retrieval — try multiple query angles
    # ------------------------------------------------------------------
    if is_pond:
        query = "koi pond outdoor goldfish water lily pond setup"
    else:
        query = "beginner fish plant aquascaping setup"

    try:
        records = retrieve(query, top_k=3)
        if not records:
            records = retrieve("fish beginner easy", top_k=3)
        if not records:
            records = retrieve("plant aquascaping", top_k=3)
    except RAGError as exc:
        logger.log_error("RAGError", str(exc))
        return JSONResponse(
            status_code=503,
            content={
                "message": "The knowledge base is currently unavailable. Please try again later.",
                "error_type": "rag_error",
            },
        )

    # ------------------------------------------------------------------
    # 2. Empty result — no beginner records found
    # ------------------------------------------------------------------
    if not records:
        return {
            "message": (
                "No beginner-rated records were found in the knowledge base "
                "for the provided tank size. Please try a different tank size "
                "or check back after the knowledge base has been updated."
            )
        }

    # ------------------------------------------------------------------
    # 3. Build and truncate context
    # ------------------------------------------------------------------
    raw_context = "\n\n".join(
        f"[{r.category.upper()}] {r.species_name}\n{r.content}" for r in records
    )
    context = token_budget.truncate_context(raw_context, 2000)

    # ------------------------------------------------------------------
    # 4. Build system prompt via PromptFactory — "The Project Planner"
    # ------------------------------------------------------------------
    user_ctx = UserContext.from_experience_level(experience_level)

    # Build a challenge context note for the prompt
    if is_pond:
        challenge_note = (
            f"This is a POND setup ({tank_gallons:.0f} gallons). "
            "Recommend outdoor/pond species: Koi, Comet Goldfish, Water Lilies, "
            "Lotus, and other pond-appropriate plants. "
            "Focus on filtration capacity, predator protection, and seasonal care."
        )
    elif experience_level == "advanced" and challenge_level == "basic":
        challenge_note = (
            "The user is an ADVANCED hobbyist seeking a BASIC/ZEN setup. "
            "Recommend low-maintenance, visually clean setups — "
            "e.g. a simple Iwagumi with Anubias, or a single-species Betta tank. "
            "Emphasize simplicity and elegance over complexity."
        )
    elif experience_level in ("beginner", "intermediate") and challenge_level == "advanced":
        challenge_note = (
            f"The user is {experience_level.upper()} but wants a CHALLENGING setup. "
            "Recommend a high-tech planted tank with CO2 injection, "
            "demanding species (e.g. Discus, Altum Angelfish, Crystal Red Shrimp), "
            "and specialty substrates. Include a clear warning about the difficulty."
        )
    else:
        challenge_note = (
            f"Match recommendations to {experience_level.upper()} experience "
            f"with {challenge_level.upper()} challenge level."
        )

    system_prompt = PromptFactory.get_prompt(
        feature_id="setup",
        context=context,
        user=user_ctx,
        extra={
            "tank_size":        str(int(tank_gallons)),
            "experience_level": experience_level,
            "challenge_note":   challenge_note,
        },
    )

    user_message = (
        f"Generate a setup guide for a {tank_gallons:.0f}-gallon "
        f"{'pond' if is_pond else 'tank'} "
        f"for a {experience_level} aquarist (challenge level: {challenge_level})."
    )

    # ------------------------------------------------------------------
    # 5. Call OpenAI
    # ------------------------------------------------------------------
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1500,
        )
        usage = response.usage
        logger.log_llm_call(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )
    except openai.RateLimitError as exc:
        logger.log_error("RateLimitError", str(exc))
        return JSONResponse(
            status_code=502,
            content={
                "message": "API error: rate limit exceeded. Please try again later.",
                "error_type": "api_error",
            },
        )
    except openai.AuthenticationError as exc:
        logger.log_error("AuthenticationError", str(exc))
        return JSONResponse(
            status_code=502,
            content={
                "message": "API error: invalid API key. Check your OPENAI_API_KEY.",
                "error_type": "api_error",
            },
        )
    except openai.OpenAIError as exc:
        logger.log_error(type(exc).__name__, str(exc))
        return JSONResponse(
            status_code=502,
            content={
                "message": f"API error: {type(exc).__name__}",
                "error_type": "api_error",
            },
        )

    # ------------------------------------------------------------------
    # 6. Parse and return the JSON response
    # ------------------------------------------------------------------
    raw_text = response.choices[0].message.content or ""
    # Strip markdown code fences if the model adds them despite instructions
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```", 2)[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.log_error("JSONDecodeError", f"Failed to parse LLM response: {exc}")
        return JSONResponse(
            status_code=502,
            content={
                "message": "API error: the model returned an unparseable response.",
                "error_type": "api_error",
            },
        )

    return result
