"""
tests/test_image_scanner.py

Unit tests for backend/tools/image_scanner.py

Requirements: 8.3, 8.4, 8.5, 8.6
"""

import json
import io
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Ensure a dummy API key is present so the module-level openai.OpenAI() call
# at import time does not raise a missing-credentials error.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.tools.image_scanner import scan_image
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_jpeg():
    """Create a minimal valid JPEG image in memory."""
    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_mock_client(species_name, confidence):
    """Build a mock OpenAI client that returns a canned LLM response."""
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "species_name": species_name,
        "confidence": confidence,
        "care_summary": "This fish needs clean water.",
        "health_assessment": {
            "issues_detected": None,
            "status": "Healthy",
        },
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock


# ---------------------------------------------------------------------------
# Tests — Requirement 8.3: only JPEG/PNG accepted
# ---------------------------------------------------------------------------

def test_non_jpeg_png_returns_400():
    """Non-JPEG/PNG content type must return 400 with error_type validation_error."""
    result = scan_image(b"fake gif data", "image/gif")
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400
    body = json.loads(result.body)
    assert body["error_type"] == "validation_error"


def test_non_jpeg_png_webp_returns_400():
    """WebP content type must also be rejected with 400 validation_error."""
    result = scan_image(b"fake webp data", "image/webp")
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400
    body = json.loads(result.body)
    assert body["error_type"] == "validation_error"


# ---------------------------------------------------------------------------
# Tests — Requirement 8.4: file size ≤ 10 MB
# ---------------------------------------------------------------------------

def test_file_exceeding_10mb_returns_400():
    """File larger than 10 MB must return 400 with error_type validation_error."""
    large_file = b"x" * (10 * 1024 * 1024 + 1)
    result = scan_image(large_file, "image/jpeg")
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400
    body = json.loads(result.body)
    assert body["error_type"] == "validation_error"


def test_file_exactly_10mb_is_rejected():
    """File of exactly 10 MB + 1 byte must be rejected; exactly 10 MB is the limit."""
    # Exactly at the limit (10 MB) should pass size check — only over should fail.
    # This test verifies the boundary: 10 MB + 1 byte is rejected.
    over_limit = b"x" * (10 * 1024 * 1024 + 1)
    result = scan_image(over_limit, "image/png")
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400
    body = json.loads(result.body)
    assert body["error_type"] == "validation_error"


# ---------------------------------------------------------------------------
# Tests — Requirement 8.6: corrupt image returns 400
# ---------------------------------------------------------------------------

def test_corrupt_image_returns_400():
    """Corrupt bytes with a valid MIME type must return 400 validation_error."""
    corrupt_bytes = b"this is not a valid image file at all"
    result = scan_image(corrupt_bytes, "image/jpeg")
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400
    body = json.loads(result.body)
    assert body["error_type"] == "validation_error"


def test_corrupt_png_returns_400():
    """Corrupt bytes declared as PNG must also return 400 validation_error."""
    corrupt_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20  # truncated PNG header
    result = scan_image(corrupt_bytes, "image/png")
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400
    body = json.loads(result.body)
    assert body["error_type"] == "validation_error"


# ---------------------------------------------------------------------------
# Tests — Requirement 8.5: null species_name forces confidence to "inconclusive"
# ---------------------------------------------------------------------------

def test_null_species_name_sets_confidence_inconclusive():
    """When LLM returns species_name=null, confidence must be forced to 'inconclusive'."""
    valid_jpeg = _make_minimal_jpeg()
    # LLM returns null species with a non-inconclusive confidence value
    mock_client = _make_mock_client(None, "low")
    with patch("backend.tools.image_scanner._client", mock_client):
        result = scan_image(valid_jpeg, "image/jpeg")
    assert isinstance(result, dict)
    assert result["species_name"] is None
    assert result["confidence"] == "inconclusive"


def test_identified_species_preserves_confidence():
    """When LLM returns a species name, the original confidence value is preserved."""
    valid_jpeg = _make_minimal_jpeg()
    mock_client = _make_mock_client("Betta splendens", "high")
    with patch("backend.tools.image_scanner._client", mock_client):
        result = scan_image(valid_jpeg, "image/jpeg")
    assert isinstance(result, dict)
    assert result["species_name"] == "Betta splendens"
    assert result["confidence"] == "high"
