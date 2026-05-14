"""
backend/tools/setup.py

Setup Guide tool for NoFishyBusiness.

Provides beginner-friendly fish, plant, and aquascaping recommendations for a
new aquarium based on tank size and experience level.

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


def get_setup_guide(tank_gallons: float, experience_level: str) -> dict:
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
    # 1. RAG retrieval — try multiple query angles
    # ------------------------------------------------------------------
    query = "beginner fish plant aquascaping setup"
    try:
        records = retrieve(query, top_k=3)
        # Fallback: try individual category queries if combined returns nothing
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
    # The experience_level is passed as a UserContext so the PromptFactory
    # can inject the correct tone modifier AND the setup template uses it
    # to enforce strict species filtering (no Discus for beginners, etc.)
    user_ctx = UserContext.from_experience_level(experience_level)

    system_prompt = PromptFactory.get_prompt(
        feature_id="setup",
        context=context,
        user=user_ctx,
        extra={
            "tank_size":        str(int(tank_gallons)),
            "experience_level": experience_level,
        },
    )

    user_message = (
        f"Generate a setup guide for a {tank_gallons}-gallon tank "
        f"for a {experience_level} aquarist."
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
