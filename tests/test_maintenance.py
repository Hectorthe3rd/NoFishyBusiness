"""
tests/test_maintenance.py

Unit tests for the Maintenance Guide tool.

Requirements: 5.4, 5.5
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import KBRecord
from backend.rag import RAGError
from backend.tools.maintenance import get_maintenance_guide

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_MOCK_RECORD = KBRecord(
    id=1,
    species_name="Nitrogen Cycle",
    category="maintenance",
    content="Ammonia spike, nitrite spike, nitrate accumulation.",
)


def _make_mock_client():
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps(
        {
            "nitrogen_cycle": "Stage 1: Ammonia. Stage 2: Nitrite. Stage 3: Nitrate.",
            "feeding": {"quantity": "a pinch", "frequency": "twice daily"},
            "weekly_tasks": ["25% water change", "Test parameters"],
            "monthly_tasks": ["Rinse filter", "Full test"],
        }
    )
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock


# ---------------------------------------------------------------------------
# Tests — Requirement 5.4: empty RAG → not-found message, no LLM call
# ---------------------------------------------------------------------------


def test_empty_rag_returns_not_found_no_llm_call():
    """When RAG returns no records, return a not-found dict and skip the LLM."""
    with patch("backend.tools.maintenance.retrieve", return_value=[]):
        with patch("backend.tools.maintenance._get_client") as mock_client_factory:
            result = get_maintenance_guide(20.0, 5, ["Guppy"])
            mock_client_factory.return_value.chat.completions.create.assert_not_called()

    assert isinstance(result, dict)
    assert "message" in result


# ---------------------------------------------------------------------------
# Tests — Requirement 5.5: response contains all four required top-level fields
# ---------------------------------------------------------------------------


def test_response_contains_all_required_fields():
    """Successful guide must include nitrogen_cycle, feeding, weekly_tasks, monthly_tasks."""
    with patch("backend.tools.maintenance.retrieve", return_value=[_MOCK_RECORD]):
        with patch(
            "backend.tools.maintenance._get_client", return_value=_make_mock_client()
        ):
            result = get_maintenance_guide(20.0, 5, ["Guppy"])

    assert isinstance(result, dict)
    assert "nitrogen_cycle" in result
    assert "feeding" in result
    assert "weekly_tasks" in result
    assert "monthly_tasks" in result


# ---------------------------------------------------------------------------
# Tests — RAG error → 503 JSONResponse
# ---------------------------------------------------------------------------


def test_rag_error_returns_503():
    """A RAGError during retrieval must produce a 503 JSONResponse."""
    from fastapi.responses import JSONResponse

    with patch(
        "backend.tools.maintenance.retrieve", side_effect=RAGError("DB error")
    ):
        result = get_maintenance_guide(20.0, 5, [])

    assert isinstance(result, JSONResponse)
    assert result.status_code == 503
