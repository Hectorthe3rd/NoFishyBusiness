"""
backend/tools/maintenance.py

Maintenance Guide tool for NoFishyBusiness.

Provides a single public function:

    get_maintenance_guide(tank_gallons, fish_count, fish_species) -> dict

which retrieves relevant maintenance content from the knowledge base via the
RAG pipeline, then calls the OpenAI API to generate a structured maintenance
guide covering the nitrogen cycle, feeding schedule, and routine tasks.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 11.1
"""

import json

import openai
from fastapi.responses import JSONResponse

from backend import logger
from backend import token_budget
from backend.models import UserContext
from backend.prompt_factory import PromptFactory
from backend.rag import RAGError, retrieve

# ---------------------------------------------------------------------------
# OpenAI client — lazy singleton (reads OPENAI_API_KEY from environment)
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    """Return the shared OpenAI client, creating it on first use."""
    global _client
    if _client is None:
        _client = openai.OpenAI()
    return _client

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_maintenance_guide(
    tank_gallons: float,
    fish_count: int,
    fish_species: list[str],
) -> dict | JSONResponse:
    """Generate a maintenance guide for the given tank and fish load.

    Workflow:
      1. Build a RAG query combining "nitrogen cycle maintenance" with any
         provided fish species names.
      2. Retrieve up to 3 records from the knowledge base.
      3. If no records are found, return a not-found message (no LLM call).
      4. Truncate the concatenated context to 2000 tokens.
      5. Call OpenAI (max_tokens=1500) with a system prompt that instructs the
         LLM to return JSON matching the required response schema.
      6. Parse and return the structured response.

    Args:
        tank_gallons: Tank volume in US gallons (must be > 0).
        fish_count:   Number of fish in the tank (must be ≥ 0).
        fish_species: List of fish species names in the tank.

    Returns:
        On success — a dict with keys:
          - ``nitrogen_cycle`` (str): Explanation covering all three stages.
          - ``feeding`` (dict): ``{"quantity": str, "frequency": str}``.
          - ``weekly_tasks`` (list[str]): At least two weekly maintenance tasks.
          - ``monthly_tasks`` (list[str]): At least two monthly maintenance tasks.

        On RAG failure — a :class:`fastapi.responses.JSONResponse` with
        HTTP 503 and ``error_type: "rag_error"``.

        On OpenAI failure — a :class:`fastapi.responses.JSONResponse` with
        HTTP 502 and ``error_type: "api_error"``.
    """
    # ------------------------------------------------------------------
    # 1. Build RAG query — extract meaningful keywords from species names
    # ------------------------------------------------------------------
    # Use the sanitize_query helper so free-form species names like
    # "Neon Tetras" or "Some shrimp" don't break FTS5
    from backend.rag import sanitize_query
    species_keywords = sanitize_query(" ".join(fish_species)) if fish_species else ""
    query = f"nitrogen cycle maintenance {species_keywords}".strip()

    # ------------------------------------------------------------------
    # 2. Retrieve from knowledge base
    # ------------------------------------------------------------------
    try:
        records = retrieve(query, top_k=3)
    except RAGError as exc:
        logger.log_error("RAGError", str(exc))
        return JSONResponse(
            status_code=503,
            content={
                "message": "Maintenance guide service is temporarily unavailable.",
                "error_type": "rag_error",
            },
        )

    # ------------------------------------------------------------------
    # 3. Handle empty result — broaden the query and try again
    # ------------------------------------------------------------------
    if not records:
        # Try a broader fallback query focused on maintenance alone
        try:
            records = retrieve("maintenance nitrogen cycle feeding")
        except RAGError:
            pass

    # If still nothing, return a helpful message
    if not records:
        return {
            "message": (
                "No maintenance information was found. "
                "Please ensure the knowledge base is seeded by running: "
                "python knowledge_base/seed.py"
            )
        }

    # ------------------------------------------------------------------
    # 4. Build and truncate context
    # ------------------------------------------------------------------
    species_list_str = (
        ", ".join(fish_species) if fish_species else "unspecified species"
    )
    raw_context = "\n\n".join(
        f"[{r.category}] {r.species_name}\n{r.content}" for r in records
    )
    context = token_budget.truncate_context(raw_context, 2000)

    # ------------------------------------------------------------------
    # 5. Calculate bioload and build prompt via PromptFactory
    # ------------------------------------------------------------------
    # Bioload = fish_count / tank_gallons ratio
    # This drives the maintenance intensity in the "maintenance" persona prompt.
    # The PromptFactory injects the bioload_note into the system prompt so the
    # LLM knows whether to recommend weekly or bi-weekly water changes.
    if tank_gallons > 0 and fish_count > 0:
        ratio = fish_count / tank_gallons
        if ratio < 0.2:
            bioload_note = f"LOW bioload ({fish_count} fish in {tank_gallons}gal). Lighter schedule appropriate."
        elif ratio < 0.5:
            bioload_note = f"MEDIUM bioload ({fish_count} fish in {tank_gallons}gal). Standard schedule."
        else:
            bioload_note = f"HIGH bioload ({fish_count} fish in {tank_gallons}gal). Intensive schedule required — more frequent water changes."
    else:
        bioload_note = "Bioload not assessed (no fish count provided)."

    system_prompt = PromptFactory.get_prompt(
        feature_id="maintenance",
        context=context,
        user=UserContext.guest(),
        extra={
            "tank_size":    str(tank_gallons),
            "fish_count":   str(fish_count),
            "bioload_note": bioload_note,
        },
    )

    user_prompt = (
        f"Generate a maintenance guide for a {tank_gallons}-gallon tank "
        f"with {fish_count} fish ({species_list_str})."
    )

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1500,
        )
    except openai.OpenAIError as exc:
        error_type = type(exc).__name__
        logger.log_error(error_type, str(exc))
        return JSONResponse(
            status_code=502,
            content={
                "message": f"API error: {error_type}",
                "error_type": "api_error",
            },
        )

    # Log the successful LLM call
    usage = response.usage
    logger.log_llm_call(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )

    # ------------------------------------------------------------------
    # 6. Parse and return the structured response
    # ------------------------------------------------------------------
    raw_text = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model included them despite instructions
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        # Remove opening fence (```json or ```)
        lines = lines[1:] if lines[0].startswith("```") else lines
        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.log_error("JSONDecodeError", f"Could not parse LLM response: {raw_text[:200]}")
        return JSONResponse(
            status_code=502,
            content={
                "message": "API error: malformed response from language model.",
                "error_type": "api_error",
            },
        )

    return result
