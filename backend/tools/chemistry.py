"""
backend/tools/chemistry.py

Chemistry Analyzer tool for NoFishyBusiness.

Accepts a text description of water test results (and an optional base64-encoded
image of a test strip) and returns a danger assessment with corrective actions
for each recognized water parameter.

Flow:
    1. Run topic_guard.check_topic(description) — return refusal if refused.
    2. Use regex to detect recognizable parameter values in the description.
        If none found, return a prompt message (no LLM call).
    3. Call rag.retrieve(description) for threshold data.
        Return 503 error if RAG fails.
    4. Truncate context to 2000 tokens.
    5. Call OpenAI (gpt-4o-mini, max_tokens=1500).
        If image_base64 is provided, include it as a vision input.
    6. Parse and return the structured response.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 10.4, 11.1
"""

import json
import re

import openai
from fastapi.responses import JSONResponse

from backend import logger, token_budget
from backend.models import UserContext
from backend.prompt_factory import PromptFactory
from backend.rag import RAGError, retrieve
from backend.topic_guard import check_topic


# ---------------------------------------------------------------------------
# OpenAI client (lazy initialization — reads OPENAI_API_KEY from environment)
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    """Return the shared OpenAI client, creating it on first call."""
    global _client
    if _client is None:
        _client = openai.OpenAI()
    return _client

# ---------------------------------------------------------------------------
# Parameter detection regex — kept here for the input validation gate
# ---------------------------------------------------------------------------

_PARAM_PATTERNS = [
    re.compile(r"\bammonia\b.*?\d+(?:\.\d+)?", re.IGNORECASE),
    re.compile(r"\bnitrite\b.*?\d+(?:\.\d+)?", re.IGNORECASE),
    re.compile(r"\bnitrate\b.*?\d+(?:\.\d+)?", re.IGNORECASE),
    re.compile(r"\bph\b.*?\d+(?:\.\d+)?", re.IGNORECASE),
    re.compile(r"\btemperature\b.*?\d+(?:\.\d+)?", re.IGNORECASE),
    re.compile(r"\d+(?:\.\d+)?\s*(?:ppm|mg/l)", re.IGNORECASE),
    re.compile(r"\d+(?:\.\d+)?\s*(?:°f|degrees?\s*f\b)", re.IGNORECASE),
]


def _has_parameter_values(text: str) -> bool:
    """Return True if *text* contains at least one recognizable parameter value."""
    for pattern in _PARAM_PATTERNS:
        if pattern.search(text):
            return True
    return False

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_chemistry(description: str, image_base64: str | None) -> dict | JSONResponse:
    """Analyze water chemistry parameters from a text description and optional image.

    Args:
        description:   Text description of water test results.
        image_base64:  Optional base64-encoded JPEG/PNG image of a test strip.

    Returns:
        A dict with ``parameters`` list and ``summary`` on success, or a
        :class:`fastapi.responses.JSONResponse` with an appropriate error
        status code and body on failure.
    """
    # 1. Topic guard ----------------------------------------------------------
    topic_result = check_topic(description)
    if topic_result.status == "refused":
        return JSONResponse(
            status_code=200,
            content={
                "message": topic_result.message,
                "error_type": "topic_refused",
            },
        )
    if topic_result.status == "error":
        return JSONResponse(
            status_code=503,
            content={
                "message": topic_result.message,
                "error_type": "topic_error",
            },
        )

    # 2. Parameter detection --------------------------------------------------
    # If no image is provided, check for recognizable parameter values OR
    # aquarium-related keywords. Free-form sentences like "my shrimp seem
    # stressed, ammonia might be high" are valid even without exact numbers.
    if not image_base64 and not _has_parameter_values(description):
        # Check if the description at least mentions chemistry-related terms
        chemistry_terms = re.compile(
            r"\b(ammonia|nitrite|nitrate|ph|temperature|hardness|oxygen|"
            r"ppm|water|tank|fish|shrimp|sick|stressed|dying|cloudy|smell)\b",
            re.IGNORECASE
        )
        if not chemistry_terms.search(description):
            return JSONResponse(
                status_code=200,
                content={
                    "message": (
                        "Please describe your water conditions or mention specific "
                        "parameters (e.g., ammonia, pH, temperature) for analysis."
                    ),
                    "error_type": "no_parameters",
                },
            )

    # 3. RAG retrieval --------------------------------------------------------
    try:
        records = retrieve(description)
    except RAGError as exc:
        logger.log_error("RAGError", str(exc))
        return JSONResponse(
            status_code=503,
            content={
                "message": f"Analysis service unavailable: {exc}",
                "error_type": "rag_error",
            },
        )

    # 4. Build and truncate context -------------------------------------------
    raw_context = "\n\n".join(record.content for record in records) if records else ""
    context = token_budget.truncate_context(raw_context, 2000)

    # Use PromptFactory "chemistry" persona — the Laboratory Analyst.
    # This prompt explains chemical interactions (e.g. pH/ammonia relationship)
    # rather than just classifying numbers.
    system_prompt = PromptFactory.get_prompt(
        feature_id="chemistry",
        context=context,
        user=UserContext.guest(),
    )

    # 5. Build messages array -------------------------------------------------
    user_content: list[dict] = [
        {"type": "text", "text": description},
    ]

    if image_base64:
        # Include the image as a vision input (data URL format)
        user_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}",
                },
            }
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # 6. OpenAI call ----------------------------------------------------------
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=messages,
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

    # 7. Log successful call --------------------------------------------------
    usage = response.usage
    if usage:
        logger.log_llm_call(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )

    # 8. Parse and return the JSON response -----------------------------------
    raw_text = response.choices[0].message.content or ""

    # Strip markdown code fences if the model wraps the JSON
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        logger.log_error("JSONDecodeError", f"Failed to parse LLM response: {exc}")
        return JSONResponse(
            status_code=502,
            content={
                "message": "API error: invalid JSON in LLM response",
                "error_type": "api_error",
            },
        )
