"""
backend/tools/chemistry.py

Chemistry Analyzer tool for NoFishyBusiness.

Accepts a text description of water test results and/or a base64-encoded
image of a test strip, and returns a danger assessment with corrective
actions for each recognized water parameter.

Flow:
    1. If only an image is provided (no text), run a Vision pre-processor
       LLM call to extract parameter readings from the image first.
    2. Call rag.retrieve() for threshold data.
    3. Truncate context to 2000 tokens.
    4. Call OpenAI (gpt-4o-mini, max_tokens=1500).
       If image_base64 is provided alongside text, include it as vision input.
    5. Parse and return the structured response.

Note: The topic guard is intentionally NOT used here. The LLM system prompt
handles scope — this avoids false refusals when users describe water conditions
in natural language without using exact aquarium keywords.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 10.4, 11.1
"""

import json

import openai
from fastapi.responses import JSONResponse

from backend import logger, token_budget
from backend.models import UserContext
from backend.prompt_factory import PromptFactory
from backend.rag import RAGError, retrieve


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
# Vision pre-processor — extract parameters from image when no text given
# ---------------------------------------------------------------------------

def _extract_params_from_image(image_base64: str) -> str:
    """Use the vision API to extract water parameter readings from a test strip image.

    Returns a text description of the detected parameters (e.g.
    "ammonia: 0.5 ppm, nitrite: 0 ppm, pH: 7.2, temperature: 78°F")
    that can then be passed to the main analysis flow.

    Returns an empty string if extraction fails.
    """
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a water chemistry test strip reader. "
                        "Look at the image and extract all visible water parameter readings. "
                        "Return ONLY a plain text description of the readings you can see, "
                        "e.g. 'ammonia: 0.5 ppm, nitrite: 0 ppm, pH: 7.2, temperature: 78°F'. "
                        "If you cannot read a parameter clearly, omit it. "
                        "If the image does not show a water test strip or test kit, "
                        "return: 'No water test parameters detected in image.'"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                        },
                        {"type": "text", "text": "Extract the water parameter readings from this test strip image."},
                    ],
                },
            ],
        )
        usage = response.usage
        if usage:
            logger.log_llm_call(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
        return response.choices[0].message.content or ""
    except openai.OpenAIError as exc:
        logger.log_error("VisionPreProcessorError", str(exc))
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_chemistry(description: str, image_base64: str | None) -> dict | JSONResponse:
    """Analyze water chemistry parameters from a text description and optional image.

    Args:
        description:   Text description of water test results. May be empty
                       if image_base64 is provided (image-only mode).
        image_base64:  Optional base64-encoded JPEG/PNG image of a test strip.

    Returns:
        A dict with ``parameters`` list and ``summary`` on success, or a
        :class:`fastapi.responses.JSONResponse` with an appropriate error
        status code and body on failure.
    """
    effective_description = description.strip() if description else ""

    # 1. Image-only mode: extract parameters from image first ----------------
    if not effective_description and image_base64:
        extracted = _extract_params_from_image(image_base64)
        if extracted and "No water test parameters" not in extracted:
            effective_description = extracted
        else:
            # Could not extract anything useful from the image
            return JSONResponse(
                status_code=200,
                content={
                    "message": (
                        "Could not detect water parameter readings in the uploaded image. "
                        "Please ensure the image clearly shows a test strip or test kit result, "
                        "or describe your water parameters in the text field."
                    ),
                    "error_type": "no_parameters",
                },
            )

    # 2. No input at all ------------------------------------------------------
    if not effective_description and not image_base64:
        return JSONResponse(
            status_code=200,
            content={
                "message": (
                    "Please describe your water conditions or upload a test strip image. "
                    "You can use natural language — for example: "
                    "'my water is a bit cloudy and the pH seems high' or "
                    "'ammonia 0.5 ppm, nitrite 0, pH 7.2, temp 78°F'."
                ),
                "error_type": "no_parameters",
            },
        )

    # 3. RAG retrieval --------------------------------------------------------
    try:
        records = retrieve(effective_description)
        if not records:
            # Broaden to chemistry category if description-based query returns nothing
            records = retrieve("water chemistry ammonia nitrite nitrate pH thresholds")
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

    system_prompt = PromptFactory.get_prompt(
        feature_id="chemistry",
        context=context,
        user=UserContext.guest(),
    )

    # 5. Build messages array -------------------------------------------------
    user_content: list[dict] = [
        {"type": "text", "text": effective_description},
    ]

    # Include the original image as additional vision context if provided
    # (even when we already extracted text from it — the LLM can cross-reference)
    if image_base64:
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
