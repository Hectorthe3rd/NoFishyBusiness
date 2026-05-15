"""
backend/tools/species.py

Species Tool for NoFishyBusiness.

Provides fish care sheet information by combining RAG retrieval from the
local knowledge base with an OpenAI LLM call to produce a structured
species response.

Fuzzy Search:
  Before querying the knowledge base, a lightweight LLM "name resolver" step
  translates partial or misspelled inputs (e.g. "neon", "bata", "tetra") into
  the most likely full species name. This makes the tool feel smart rather
  than brittle.

Requirements: 4.1, 4.2, 4.3, 4.5, 11.1, 11.3, 11.4
"""

import json

import openai
from fastapi.responses import JSONResponse

from backend import logger, token_budget
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
# Name resolver — translates partial/fuzzy input to a full species name
# ---------------------------------------------------------------------------

def _resolve_species_name(raw_input: str) -> tuple[str, bool]:
    """Use a cheap LLM call to resolve a partial or misspelled species name.

    Returns:
        (resolved_name, is_fuzzy_match)
        - resolved_name: The best-guess full species name.
        - is_fuzzy_match: True if the input was partial/misspelled (not exact).
    """
    prompt = (
        "You are a freshwater aquarium species name resolver. "
        "Given a partial, misspelled, or abbreviated fish/plant/shrimp name, "
        "return the most likely full common name used in the aquarium hobby. "
        "If the input is already a full, exact name, return it unchanged. "
        "Respond ONLY with a JSON object: "
        '{"resolved": "<full common name>", "is_fuzzy": <true|false>}'
    )
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=60,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_input},
            ],
        )
        raw = response.choices[0].message.content or ""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        parsed = json.loads(raw)
        resolved = parsed.get("resolved", raw_input).strip()
        is_fuzzy = bool(parsed.get("is_fuzzy", False))
        return resolved, is_fuzzy
    except Exception as exc:
        logger.log_error("NameResolverError", str(exc))
        # Fall back to the raw input if the resolver fails
        return raw_input, False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_species_info(species_name: str) -> dict | JSONResponse:
    """Return a structured care sheet for the requested fish species.

    Flow:
      1. Run the name resolver to handle partial/fuzzy inputs.
      2. Call ``rag.retrieve(resolved_name)`` to fetch relevant KB records.
      3. If no records are found, return a 404 not-found response.
      4. If a RAGError occurs, return a 503 rag-error response.
      5. Truncate the concatenated context to 2000 tokens.
      6. Call OpenAI (gpt-4o-mini, max_tokens=1500) with the context.
      7. Parse the JSON response and return it.
         If the match was fuzzy, include a "did_you_mean" hint in the response.
      8. On any OpenAI error, log it and return a 502 api-error response.

    Args:
        species_name: The common or scientific name of the fish species
                      (partial names and misspellings are handled).

    Returns:
        A dict with the structured species care sheet on success, or a
        :class:`fastapi.responses.JSONResponse` with an appropriate error
        status code and body on failure.
    """
    # 1. Resolve the species name (fuzzy/partial → full name) ----------------
    resolved_name, is_fuzzy = _resolve_species_name(species_name)

    # 2. RAG retrieval — fetch top 5 to get species + related documents ------
    try:
        records = retrieve(resolved_name, top_k=5)
        # If resolved name found nothing, try the original input as fallback
        if not records and resolved_name.lower() != species_name.lower():
            records = retrieve(species_name, top_k=5)
    except RAGError as exc:
        logger.log_error("RAGError", str(exc))
        return JSONResponse(
            status_code=503,
            content={
                "message": f"Knowledge base unavailable: {exc}",
                "error_type": "rag_error",
            },
        )

    # 3. Not found ------------------------------------------------------------
    if not records:
        msg = f"No information found for '{resolved_name}'."
        if is_fuzzy and resolved_name.lower() != species_name.lower():
            msg = (
                f"No information found for '{resolved_name}' "
                f"(interpreted from '{species_name}'). "
                "Try a more specific name or check the spelling."
            )
        return JSONResponse(
            status_code=404,
            content={"message": msg, "error_type": "not_found"},
        )

    # 4. Build and truncate context ------------------------------------------
    raw_context = "\n\n".join(record.content for record in records)
    context = token_budget.truncate_context(raw_context, 2000)

    system_prompt = PromptFactory.get_prompt(
        feature_id="species",
        context=context,
        user=UserContext.guest(),
    )

    # 5. OpenAI call ----------------------------------------------------------
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Provide the care sheet for: {resolved_name}",
                },
            ],
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

    # 6. Log successful call --------------------------------------------------
    usage = response.usage
    if usage:
        logger.log_llm_call(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )

    # 7. Parse and return the JSON response -----------------------------------
    raw_text = response.choices[0].message.content or ""

    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        result = json.loads(stripped)
        # Attach fuzzy-match hint so the frontend can show "Did you mean X?"
        if is_fuzzy and resolved_name.lower() != species_name.lower():
            result["did_you_mean"] = resolved_name
        return result
    except json.JSONDecodeError as exc:
        logger.log_error("JSONDecodeError", f"Failed to parse LLM response: {exc}")
        return JSONResponse(
            status_code=502,
            content={
                "message": "API error: invalid JSON in LLM response",
                "error_type": "api_error",
            },
        )
