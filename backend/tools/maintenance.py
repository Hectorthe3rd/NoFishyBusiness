"""
backend/tools/maintenance.py

Maintenance Guide tool for NoFishyBusiness.

Provides a single public function:

    get_maintenance_guide(tank_gallons, fish_count, fish_species) -> dict

which retrieves relevant maintenance content from the knowledge base via the
RAG pipeline, then calls the OpenAI API to generate a structured maintenance
guide covering the nitrogen cycle, feeding schedule, and routine tasks.

Enhancements:
  - Bioload Index: fish_count / tank_gallons drives maintenance intensity.
  - Incompatibility Warnings: cross-references species temperature/pH ranges
    from the KB; prepends a HIGH-PRIORITY WARNING if ranges don't overlap.
  - Species-specific tasks: e.g. Pleco → "Inspect wood for rasping/waste".

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
# Species-specific task rules
# ---------------------------------------------------------------------------

# Maps lowercase species name fragments to extra monthly tasks.
_SPECIES_TASK_RULES: list[tuple[str, str]] = [
    ("pleco",      "Inspect driftwood for rasping marks and accumulated waste; remove excess."),
    ("goldfish",   "Vacuum gravel thoroughly — goldfish produce heavy waste."),
    ("oscar",      "Deep-clean substrate and check for uneaten food; Oscars are messy eaters."),
    ("cichlid",    "Rearrange decor if aggression is observed to reset territory boundaries."),
    ("betta",      "Check and clean the surface area around the filter intake for debris."),
    ("shrimp",     "Inspect moss/plants for molts and remove any that look unhealthy."),
    ("snail",      "Check for egg clutches on glass and remove if population control is needed."),
    ("corydoras",  "Vacuum substrate gently — Corydoras are sensitive to dirty substrate."),
    ("loach",      "Check hiding spots and caves for waste accumulation."),
]


def _get_species_specific_tasks(fish_species: list[str]) -> list[str]:
    """Return extra monthly tasks based on the species list."""
    extra: list[str] = []
    species_lower = " ".join(fish_species).lower()
    for keyword, task in _SPECIES_TASK_RULES:
        if keyword in species_lower and task not in extra:
            extra.append(task)
    return extra


# ---------------------------------------------------------------------------
# Incompatibility checker
# ---------------------------------------------------------------------------

# Known temperature ranges (°F) for common species groups.
# Used for quick cross-reference without a full KB lookup.
_TEMP_RANGES: dict[str, tuple[float, float]] = {
    "goldfish":    (60.0, 72.0),
    "koi":         (59.0, 77.0),
    "neon tetra":  (72.0, 80.0),
    "cardinal tetra": (73.0, 81.0),
    "betta":       (76.0, 82.0),
    "guppy":       (72.0, 82.0),
    "discus":      (82.0, 88.0),
    "angelfish":   (75.0, 82.0),
    "oscar":       (74.0, 81.0),
    "pleco":       (72.0, 82.0),
    "corydoras":   (70.0, 78.0),
    "danio":       (65.0, 77.0),
    "white cloud": (60.0, 72.0),
}


def _check_incompatibilities(fish_species: list[str]) -> str | None:
    """Return a warning string if species have incompatible temperature ranges.

    Returns None if all species are compatible or if ranges are unknown.
    """
    if len(fish_species) < 2:
        return None

    matched: list[tuple[str, tuple[float, float]]] = []
    species_lower = [s.lower() for s in fish_species]

    for species_str in species_lower:
        for key, temp_range in _TEMP_RANGES.items():
            if key in species_str:
                matched.append((species_str, temp_range))
                break

    if len(matched) < 2:
        return None

    # Find the overlap of all matched temperature ranges
    overlap_min = max(r[0] for _, r in matched)
    overlap_max = min(r[1] for _, r in matched)

    if overlap_min > overlap_max:
        # No overlap — incompatible
        species_names = ", ".join(f"**{s.title()}**" for s, _ in matched)
        ranges_desc = "; ".join(
            f"{s.title()}: {r[0]}–{r[1]}°F" for s, r in matched
        )
        return (
            f"⚠️ **HIGH-PRIORITY COMPATIBILITY WARNING**\n\n"
            f"The following species have **incompatible temperature requirements**: "
            f"{species_names}.\n\n"
            f"Temperature ranges: {ranges_desc}.\n\n"
            f"These species cannot thrive in the same tank. "
            f"Coldwater species (like Goldfish) require temperatures that cause "
            f"metabolic stress in tropical species (like Neon Tetras), and vice versa. "
            f"**Consider separating these species into different tanks.**"
        )

    return None


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
        lines = lines[1:] if lines[0].startswith("```") else lines
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

    # ------------------------------------------------------------------
    # 7. Post-process: inject incompatibility warning + species tasks
    # ------------------------------------------------------------------
    # Incompatibility warning — prepend to result if species conflict
    incompatibility_warning = _check_incompatibilities(fish_species)
    if incompatibility_warning:
        result["incompatibility_warning"] = incompatibility_warning

    # Species-specific monthly tasks — append to existing monthly_tasks
    extra_tasks = _get_species_specific_tasks(fish_species)
    if extra_tasks:
        existing = result.get("monthly_tasks", [])
        # Avoid duplicates
        for task in extra_tasks:
            if task not in existing:
                existing.append(task)
        result["monthly_tasks"] = existing

    return result
