"""
backend/tools/image_scanner.py

Image Scanner tool for NoFishyBusiness.

Accepts a JPEG or PNG image (≤10 MB), validates it, then calls the OpenAI
vision API (gpt-4o-mini) to identify the species and assess health.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 11.1
"""

import base64
import io
import json

import openai
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

from backend import logger
from backend.models import UserContext
from backend.prompt_factory import PromptFactory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}

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


def scan_image(file_bytes: bytes, content_type: str) -> dict | JSONResponse:
    """Identify species and assess health from an uploaded image.

    Validation steps (in order):
      1. Content type must be ``image/jpeg`` or ``image/png``.
      2. File size must not exceed 10 MB.
      3. Image must be decodable by Pillow (not corrupt).

    On success, calls the OpenAI vision API and returns a structured dict.

    Args:
        file_bytes:   Raw bytes of the uploaded image file.
        content_type: MIME type reported by the client (e.g. "image/jpeg").

    Returns:
        A dict with species identification and health assessment on success,
        or a :class:`fastapi.responses.JSONResponse` with status 400 or 502
        on failure.
    """
    # 1. Validate content type ------------------------------------------------
    if content_type not in _ALLOWED_CONTENT_TYPES:
        return JSONResponse(
            status_code=400,
            content={
                "message": (
                    f"Unsupported file type '{content_type}'. "
                    "Only JPEG and PNG images are accepted."
                ),
                "error_type": "validation_error",
            },
        )

    # 2. Validate file size ---------------------------------------------------
    if len(file_bytes) > _MAX_FILE_SIZE:
        size_mb = len(file_bytes) / (1024 * 1024)
        return JSONResponse(
            status_code=400,
            content={
                "message": (
                    f"File size {size_mb:.1f} MB exceeds the 10 MB limit. "
                    "Please upload a smaller image."
                ),
                "error_type": "validation_error",
            },
        )

    # 3. Validate image integrity (Pillow decode) -----------------------------
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.load()  # fully decode the image to catch truncation/corruption
    except (UnidentifiedImageError, Exception) as exc:
        logger.log_error("ImageDecodeError", str(exc))
        return JSONResponse(
            status_code=400,
            content={
                "message": (
                    "The uploaded image could not be read. "
                    "It may be corrupt or in an unsupported format."
                ),
                "error_type": "validation_error",
            },
        )

    # 4. Encode image as base64 data URI -------------------------------------
    # Determine the correct MIME type for the data URI
    mime = content_type  # already validated as image/jpeg or image/png
    b64_data = base64.b64encode(file_bytes).decode("utf-8")
    data_uri = f"data:{mime};base64,{b64_data}"

    # 5. Call OpenAI vision API — using PromptFactory "image_scanner" persona
    # The Diagnostic Pathologist prompt asks for scientific names, look-alike
    # comparisons, and a captivity_note for unsuitable species.
    system_prompt = PromptFactory.get_prompt(
        feature_id="image_scanner",
        context="",   # Image scanner doesn't use RAG context (vision-only)
        user=UserContext.guest(),
    )

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Please identify this aquatic organism and "
                                "assess its health based on the image."
                            ),
                        },
                    ],
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

    # Strip markdown code fences if the model wraps the JSON
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        result = json.loads(stripped)
    except json.JSONDecodeError as exc:
        logger.log_error("JSONDecodeError", f"Failed to parse LLM response: {exc}")
        return JSONResponse(
            status_code=502,
            content={
                "message": "API error: invalid JSON in LLM response",
                "error_type": "api_error",
            },
        )

    # 8. Enforce the species_name / confidence invariant ----------------------
    # If species_name is null, confidence must be "inconclusive" (Req 8.5)
    if result.get("species_name") is None:
        result["confidence"] = "inconclusive"

    return result
