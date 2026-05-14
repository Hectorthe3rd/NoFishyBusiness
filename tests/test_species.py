"""
tests/test_species.py

Unit tests for the Species Tool (backend/tools/species.py).

Requirements: 4.1, 4.3, 4.5
"""

import json
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.tools.species import get_species_info
from backend.rag import RAGError
from backend.models import KBRecord
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_MOCK_RECORD = KBRecord(
    id=1,
    species_name="Guppy",
    category="fish",
    content="Guppies are peaceful community fish. They prefer 72-82F and pH 6.8-7.8."
)

_MOCK_LLM_RESPONSE = {
    "species_name": "Guppy",
    "behavior": "Peaceful schooling fish",
    "compatible_tank_mates": ["Platy", "Molly"],
    "temperature_f": {"min": 72.0, "max": 82.0},
    "ph": {"min": 6.8, "max": 7.8},
    "hardness_dgh": {"min": 5.0, "max": 15.0},
    "min_tank_gallons": 5,
    "difficulty": "easy",
    "maintenance_notes": "Easy to care for, good for beginners."
}


def _make_mock_openai(response_dict):
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps(response_dict)
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_known_species_returns_all_required_fields():
    """Req 4.1 — known species returns a dict with all required care-sheet fields."""
    with patch("backend.tools.species.retrieve", return_value=[_MOCK_RECORD]):
        with patch("backend.tools.species._get_client", return_value=_make_mock_openai(_MOCK_LLM_RESPONSE)):
            result = get_species_info("Guppy")

    assert isinstance(result, dict)
    for field in [
        "behavior",
        "compatible_tank_mates",
        "temperature_f",
        "ph",
        "hardness_dgh",
        "min_tank_gallons",
        "difficulty",
        "maintenance_notes",
    ]:
        assert field in result, f"Missing field: {field}"


def test_unknown_species_returns_404_no_llm_call():
    """Req 4.3 — unknown species returns 404 with error_type 'not_found' and no LLM call."""
    with patch("backend.tools.species.retrieve", return_value=[]):
        with patch("backend.tools.species._get_client") as mock_client:
            result = get_species_info("XyzUnknownFish123")
            mock_client.return_value.chat.completions.create.assert_not_called()

    assert isinstance(result, JSONResponse)
    assert result.status_code == 404
    body = json.loads(result.body)
    assert body["error_type"] == "not_found"


def test_rag_failure_returns_error_no_llm_call():
    """Req 4.5 — RAG failure returns 503 with error_type 'rag_error' and no LLM call."""
    with patch("backend.tools.species.retrieve", side_effect=RAGError("DB error")):
        with patch("backend.tools.species._get_client") as mock_client:
            result = get_species_info("Guppy")
            mock_client.return_value.chat.completions.create.assert_not_called()

    assert isinstance(result, JSONResponse)
    assert result.status_code == 503
    body = json.loads(result.body)
    assert body["error_type"] == "rag_error"
