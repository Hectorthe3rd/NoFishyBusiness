"""
tests/test_setup.py

Unit tests for the Setup Guide tool (backend/tools/setup.py).

Requirements: 6.1, 6.5
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import KBRecord
from backend.rag import RAGError
from backend.tools.setup import get_setup_guide

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_MOCK_RECORD = KBRecord(
    id=1,
    species_name="Aquascaping Basics",
    category="aquascaping",
    content="Use fine sand substrate. Place rocks off-center.",
)


def _make_mock_client(tank_gallons: float = 20.0) -> MagicMock:
    """Return a mock OpenAI client whose completions return valid JSON."""
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps(
        {
            "fish_recommendations": [
                {"name": "Guppy", "difficulty": "easy", "min_tank_gallons": 5},
                {"name": "Platy", "difficulty": "easy", "min_tank_gallons": 10},
                {"name": "Zebra Danio", "difficulty": "easy", "min_tank_gallons": 10},
            ],
            "plant_recommendations": [
                {"name": "Java Fern", "difficulty": "easy"},
                {"name": "Anubias", "difficulty": "easy"},
            ],
            "aquascaping_idea": {
                "substrate": "Fine sand",
                "hardscape": "Rocks off-center",
                "plant_zones": ["Foreground", "Background"],
            },
        }
    )
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock


# ---------------------------------------------------------------------------
# Test 1 – empty RAG result → not-found message, no LLM call  (Req 6.1)
# ---------------------------------------------------------------------------


def test_empty_rag_returns_not_found_no_llm_call():
    """When RAG returns no records the function must return a dict with a
    'message' key and must NOT call the OpenAI client at all."""
    with patch("backend.tools.setup.retrieve", return_value=[]):
        with patch("backend.tools.setup._get_client") as mock_get_client:
            result = get_setup_guide(20.0, "beginner")
            # The client factory must never have been called
            mock_get_client.return_value.chat.completions.create.assert_not_called()

    assert isinstance(result, dict)
    assert "message" in result, "Expected a 'message' key in the not-found response"


# ---------------------------------------------------------------------------
# Test 2 – fish recommendations are easy-rated and fit the tank  (Req 6.5)
# ---------------------------------------------------------------------------


def test_fish_recommendations_are_easy_and_fit_tank():
    """Every fish in fish_recommendations must have difficulty='easy' and
    min_tank_gallons ≤ the requested tank size."""
    tank_gallons = 20.0
    with patch("backend.tools.setup.retrieve", return_value=[_MOCK_RECORD]):
        with patch(
            "backend.tools.setup._get_client",
            return_value=_make_mock_client(tank_gallons),
        ):
            result = get_setup_guide(tank_gallons, "beginner")

    assert isinstance(result, dict)
    assert "fish_recommendations" in result, "Expected 'fish_recommendations' in result"

    for fish in result["fish_recommendations"]:
        assert fish["difficulty"] == "easy", (
            f"Fish '{fish['name']}' has difficulty '{fish['difficulty']}', expected 'easy'"
        )
        assert fish["min_tank_gallons"] <= tank_gallons, (
            f"Fish '{fish['name']}' requires {fish['min_tank_gallons']} gallons "
            f"but tank is only {tank_gallons} gallons"
        )


# ---------------------------------------------------------------------------
# Test 3 – RAGError → 503 JSONResponse
# ---------------------------------------------------------------------------


def test_rag_error_returns_503():
    """A RAGError raised during retrieval must produce a JSONResponse with
    status_code 503 (no LLM call should be attempted)."""
    from fastapi.responses import JSONResponse

    with patch(
        "backend.tools.setup.retrieve", side_effect=RAGError("DB error")
    ):
        result = get_setup_guide(20.0, "beginner")

    assert isinstance(result, JSONResponse), (
        "Expected a JSONResponse when RAGError is raised"
    )
    assert result.status_code == 503
