"""
tests/test_integration.py

Integration tests for NoFishyBusiness backend wiring.

Verifies that:
  1. RAG is called before OpenAI in every LLM-powered tool
     (/species, /maintenance, /setup, /chemistry, /assistant).
  2. Topic Guard is invoked on every /assistant and /chemistry request.
  3. max_tokens=1500 is present in every mocked OpenAI call.
  4. backend/app.log receives an entry for every mocked LLM call.

Requirements: 4.2, 5.4, 6.4, 7.5, 9.1, 10.4, 11.1, 11.4, 12.1, 12.2
"""

import importlib
import json
import os
import sys

import pytest
from unittest.mock import patch, MagicMock, call

# Ensure the project root is on sys.path so backend imports work.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import KBRecord
from backend.topic_guard import TopicResult

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_MOCK_RECORD = KBRecord(
    id=1,
    species_name="Guppy",
    category="fish",
    content="Guppies are peaceful community fish.",
)

_MOCK_RECORD_CHEMISTRY = KBRecord(
    id=2,
    species_name="Ammonia",
    category="chemistry",
    content="Ammonia safe range: 0 ppm. Caution: 0.25 ppm. Danger: >0.5 ppm.",
)

_MOCK_RECORD_MAINTENANCE = KBRecord(
    id=3,
    species_name="Nitrogen Cycle",
    category="maintenance",
    content=(
        "The nitrogen cycle has three stages: ammonia spike, nitrite spike, "
        "and nitrate accumulation."
    ),
)

_MOCK_RECORD_SETUP = KBRecord(
    id=4,
    species_name="Guppy",
    category="fish",
    content="Guppies are easy beginner fish. Min tank: 5 gallons.",
)


def _make_species_mock_client():
    """Return a MagicMock OpenAI client pre-configured for the species tool."""
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "species_name": "Guppy",
        "behavior": "Peaceful",
        "compatible_tank_mates": ["Tetra", "Molly"],
        "temperature_f": {"min": 72, "max": 82},
        "ph": {"min": 6.5, "max": 7.5},
        "hardness_dgh": {"min": 5, "max": 15},
        "min_tank_gallons": 5,
        "difficulty": "easy",
        "maintenance_notes": "Easy care.",
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock


def _make_maintenance_mock_client():
    """Return a MagicMock OpenAI client pre-configured for the maintenance tool."""
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "nitrogen_cycle": (
            "Stage 1: ammonia spike. Stage 2: nitrite spike. "
            "Stage 3: nitrate accumulation."
        ),
        "feeding": {"quantity": "small pinch", "frequency": "twice daily"},
        "weekly_tasks": ["25% water change", "clean filter media"],
        "monthly_tasks": ["deep gravel vacuum", "check equipment"],
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=120, completion_tokens=60, total_tokens=180
    )
    return mock


def _make_setup_mock_client():
    """Return a MagicMock OpenAI client pre-configured for the setup tool."""
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "fish_recommendations": [
            {"name": "Guppy", "difficulty": "easy", "min_tank_gallons": 5},
            {"name": "Platy", "difficulty": "easy", "min_tank_gallons": 10},
            {"name": "Molly", "difficulty": "easy", "min_tank_gallons": 10},
        ],
        "plant_recommendations": [
            {"name": "Java Fern", "difficulty": "easy"},
            {"name": "Anubias", "difficulty": "easy"},
        ],
        "aquascaping_idea": {
            "substrate": "fine gravel",
            "hardscape": "driftwood",
            "plant_zones": ["foreground", "background"],
        },
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=130, completion_tokens=70, total_tokens=200
    )
    return mock


def _make_chemistry_mock_client():
    """Return a MagicMock OpenAI client pre-configured for the chemistry tool."""
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "parameters": [
            {
                "name": "ammonia",
                "value": "0.5 ppm",
                "status": "caution",
                "corrective_action": "Perform a 25% water change.",
            }
        ],
        "summary": "Ammonia is slightly elevated.",
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=110, completion_tokens=55, total_tokens=165
    )
    return mock


def _make_assistant_mock_client():
    """Return a MagicMock OpenAI client pre-configured for the assistant tool."""
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "reply": "Guppies are great beginner fish.",
        "suggested_section": "Species Tool",
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=105, completion_tokens=45, total_tokens=150
    )
    return mock


# ---------------------------------------------------------------------------
# Helper: redirect logger to a temp file
# ---------------------------------------------------------------------------

def _redirect_log(monkeypatch, tmp_path):
    """Monkeypatch backend.logger._LOG_PATH to a temp file and return its path."""
    import backend.logger as logger_mod
    log_file = tmp_path / "test.log"
    monkeypatch.setattr(logger_mod, "_LOG_PATH", str(log_file))
    return log_file


# ===========================================================================
# 1. Species Tool — RAG before OpenAI, max_tokens=1500, logging
# ===========================================================================


def test_species_rag_called_before_openai(tmp_path, monkeypatch):
    """RAG must be called before OpenAI in the species tool."""
    _redirect_log(monkeypatch, tmp_path)

    call_order = []

    def mock_retrieve(query, top_k=3):
        call_order.append("rag")
        return [_MOCK_RECORD]

    mock_client = _make_species_mock_client()
    original_create = mock_client.chat.completions.create

    def mock_create(*args, **kwargs):
        call_order.append("openai")
        return original_create(*args, **kwargs)

    mock_client.chat.completions.create = mock_create

    import backend.tools.species as species_mod
    with patch.object(species_mod, "retrieve", side_effect=mock_retrieve):
        with patch.object(species_mod, "_get_client", return_value=mock_client):
            # Reset cached client so _get_client() is actually called
            species_mod._client = None
            species_mod.get_species_info("Guppy")

    assert "rag" in call_order, "RAG was never called"
    assert "openai" in call_order, "OpenAI was never called"
    assert call_order.index("rag") < call_order.index("openai"), (
        "RAG must be called before OpenAI"
    )


def test_species_max_tokens_1500(tmp_path, monkeypatch):
    """max_tokens must be 1500 in the species tool OpenAI call."""
    _redirect_log(monkeypatch, tmp_path)

    mock_client = _make_species_mock_client()

    import backend.tools.species as species_mod
    with patch.object(species_mod, "retrieve", return_value=[_MOCK_RECORD]):
        with patch.object(species_mod, "_get_client", return_value=mock_client):
            species_mod._client = None
            species_mod.get_species_info("Guppy")

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs is not None, "OpenAI was never called"
    assert call_kwargs.kwargs.get("max_tokens") == 1500, (
        f"Expected max_tokens=1500, got {call_kwargs.kwargs.get('max_tokens')}"
    )


def test_species_logs_llm_call(tmp_path, monkeypatch):
    """A log entry with event='llm_call' must be written for the species LLM call."""
    log_file = _redirect_log(monkeypatch, tmp_path)

    import backend.tools.species as species_mod
    with patch.object(species_mod, "retrieve", return_value=[_MOCK_RECORD]):
        with patch.object(species_mod, "_get_client", return_value=_make_species_mock_client()):
            species_mod._client = None
            species_mod.get_species_info("Guppy")

    assert log_file.exists(), "Log file was not created"
    lines = [l for l in log_file.read_text().strip().split("\n") if l.strip()]
    assert len(lines) >= 1, "No log entries written"
    entry = json.loads(lines[-1])
    assert entry["event"] == "llm_call", f"Expected event='llm_call', got {entry['event']}"


# ===========================================================================
# 2. Maintenance Tool — RAG before OpenAI, max_tokens=1500, logging
# ===========================================================================


def test_maintenance_rag_called_before_openai(tmp_path, monkeypatch):
    """RAG must be called before OpenAI in the maintenance tool."""
    _redirect_log(monkeypatch, tmp_path)

    call_order = []

    def mock_retrieve(query, top_k=3):
        call_order.append("rag")
        return [_MOCK_RECORD_MAINTENANCE]

    mock_client = _make_maintenance_mock_client()
    original_create = mock_client.chat.completions.create

    def mock_create(*args, **kwargs):
        call_order.append("openai")
        return original_create(*args, **kwargs)

    mock_client.chat.completions.create = mock_create

    import backend.tools.maintenance as maintenance_mod
    with patch.object(maintenance_mod, "retrieve", side_effect=mock_retrieve):
        with patch.object(maintenance_mod, "_get_client", return_value=mock_client):
            maintenance_mod._client = None
            maintenance_mod.get_maintenance_guide(20.0, 5, ["Guppy"])

    assert "rag" in call_order, "RAG was never called"
    assert "openai" in call_order, "OpenAI was never called"
    assert call_order.index("rag") < call_order.index("openai"), (
        "RAG must be called before OpenAI"
    )


def test_maintenance_max_tokens_1500(tmp_path, monkeypatch):
    """max_tokens must be 1500 in the maintenance tool OpenAI call."""
    _redirect_log(monkeypatch, tmp_path)

    mock_client = _make_maintenance_mock_client()

    import backend.tools.maintenance as maintenance_mod
    with patch.object(maintenance_mod, "retrieve", return_value=[_MOCK_RECORD_MAINTENANCE]):
        with patch.object(maintenance_mod, "_get_client", return_value=mock_client):
            maintenance_mod._client = None
            maintenance_mod.get_maintenance_guide(20.0, 5, ["Guppy"])

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs is not None, "OpenAI was never called"
    assert call_kwargs.kwargs.get("max_tokens") == 1500, (
        f"Expected max_tokens=1500, got {call_kwargs.kwargs.get('max_tokens')}"
    )


def test_maintenance_logs_llm_call(tmp_path, monkeypatch):
    """A log entry with event='llm_call' must be written for the maintenance LLM call."""
    log_file = _redirect_log(monkeypatch, tmp_path)

    import backend.tools.maintenance as maintenance_mod
    with patch.object(maintenance_mod, "retrieve", return_value=[_MOCK_RECORD_MAINTENANCE]):
        with patch.object(maintenance_mod, "_get_client", return_value=_make_maintenance_mock_client()):
            maintenance_mod._client = None
            maintenance_mod.get_maintenance_guide(20.0, 5, ["Guppy"])

    assert log_file.exists(), "Log file was not created"
    lines = [l for l in log_file.read_text().strip().split("\n") if l.strip()]
    assert len(lines) >= 1, "No log entries written"
    entry = json.loads(lines[-1])
    assert entry["event"] == "llm_call", f"Expected event='llm_call', got {entry['event']}"


# ===========================================================================
# 3. Setup Tool — RAG before OpenAI, max_tokens=1500, logging
# ===========================================================================


def test_setup_rag_called_before_openai(tmp_path, monkeypatch):
    """RAG must be called before OpenAI in the setup tool."""
    _redirect_log(monkeypatch, tmp_path)

    call_order = []

    def mock_retrieve(query, top_k=3):
        call_order.append("rag")
        return [_MOCK_RECORD_SETUP]

    mock_client = _make_setup_mock_client()
    original_create = mock_client.chat.completions.create

    def mock_create(*args, **kwargs):
        call_order.append("openai")
        return original_create(*args, **kwargs)

    mock_client.chat.completions.create = mock_create

    import backend.tools.setup as setup_mod
    with patch.object(setup_mod, "retrieve", side_effect=mock_retrieve):
        with patch.object(setup_mod, "_get_client", return_value=mock_client):
            setup_mod._client = None
            setup_mod.get_setup_guide(20.0, "beginner")

    assert "rag" in call_order, "RAG was never called"
    assert "openai" in call_order, "OpenAI was never called"
    assert call_order.index("rag") < call_order.index("openai"), (
        "RAG must be called before OpenAI"
    )


def test_setup_max_tokens_1500(tmp_path, monkeypatch):
    """max_tokens must be 1500 in the setup tool OpenAI call."""
    _redirect_log(monkeypatch, tmp_path)

    mock_client = _make_setup_mock_client()

    import backend.tools.setup as setup_mod
    with patch.object(setup_mod, "retrieve", return_value=[_MOCK_RECORD_SETUP]):
        with patch.object(setup_mod, "_get_client", return_value=mock_client):
            setup_mod._client = None
            setup_mod.get_setup_guide(20.0, "beginner")

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs is not None, "OpenAI was never called"
    assert call_kwargs.kwargs.get("max_tokens") == 1500, (
        f"Expected max_tokens=1500, got {call_kwargs.kwargs.get('max_tokens')}"
    )


def test_setup_logs_llm_call(tmp_path, monkeypatch):
    """A log entry with event='llm_call' must be written for the setup LLM call."""
    log_file = _redirect_log(monkeypatch, tmp_path)

    import backend.tools.setup as setup_mod
    with patch.object(setup_mod, "retrieve", return_value=[_MOCK_RECORD_SETUP]):
        with patch.object(setup_mod, "_get_client", return_value=_make_setup_mock_client()):
            setup_mod._client = None
            setup_mod.get_setup_guide(20.0, "beginner")

    assert log_file.exists(), "Log file was not created"
    lines = [l for l in log_file.read_text().strip().split("\n") if l.strip()]
    assert len(lines) >= 1, "No log entries written"
    entry = json.loads(lines[-1])
    assert entry["event"] == "llm_call", f"Expected event='llm_call', got {entry['event']}"


# ===========================================================================
# 4. Chemistry Tool — Topic Guard invoked, RAG before OpenAI,
#    max_tokens=1500, logging
# ===========================================================================


def test_chemistry_topic_guard_invoked(tmp_path, monkeypatch):
    """Topic Guard must be invoked on every /chemistry request."""
    _redirect_log(monkeypatch, tmp_path)

    import backend.tools.chemistry as chemistry_mod
    with patch.object(
        chemistry_mod,
        "check_topic",
        return_value=TopicResult(status="allowed", message=""),
    ) as mock_guard:
        with patch.object(chemistry_mod, "retrieve", return_value=[_MOCK_RECORD_CHEMISTRY]):
            with patch.object(chemistry_mod, "_get_client", return_value=_make_chemistry_mock_client()):
                chemistry_mod._client = None
                chemistry_mod.analyze_chemistry("ammonia is 0.5 ppm", None)

    mock_guard.assert_called_once()


def test_chemistry_rag_called_before_openai(tmp_path, monkeypatch):
    """RAG must be called before OpenAI in the chemistry tool."""
    _redirect_log(monkeypatch, tmp_path)

    call_order = []

    def mock_retrieve(query, top_k=3):
        call_order.append("rag")
        return [_MOCK_RECORD_CHEMISTRY]

    mock_client = _make_chemistry_mock_client()
    original_create = mock_client.chat.completions.create

    def mock_create(*args, **kwargs):
        call_order.append("openai")
        return original_create(*args, **kwargs)

    mock_client.chat.completions.create = mock_create

    import backend.tools.chemistry as chemistry_mod
    with patch.object(
        chemistry_mod,
        "check_topic",
        return_value=TopicResult(status="allowed", message=""),
    ):
        with patch.object(chemistry_mod, "retrieve", side_effect=mock_retrieve):
            with patch.object(chemistry_mod, "_get_client", return_value=mock_client):
                chemistry_mod._client = None
                chemistry_mod.analyze_chemistry("ammonia is 0.5 ppm", None)

    assert "rag" in call_order, "RAG was never called"
    assert "openai" in call_order, "OpenAI was never called"
    assert call_order.index("rag") < call_order.index("openai"), (
        "RAG must be called before OpenAI"
    )


def test_chemistry_max_tokens_1500(tmp_path, monkeypatch):
    """max_tokens must be 1500 in the chemistry tool OpenAI call."""
    _redirect_log(monkeypatch, tmp_path)

    mock_client = _make_chemistry_mock_client()

    import backend.tools.chemistry as chemistry_mod
    with patch.object(
        chemistry_mod,
        "check_topic",
        return_value=TopicResult(status="allowed", message=""),
    ):
        with patch.object(chemistry_mod, "retrieve", return_value=[_MOCK_RECORD_CHEMISTRY]):
            with patch.object(chemistry_mod, "_get_client", return_value=mock_client):
                chemistry_mod._client = None
                chemistry_mod.analyze_chemistry("ammonia is 0.5 ppm", None)

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs is not None, "OpenAI was never called"
    assert call_kwargs.kwargs.get("max_tokens") == 1500, (
        f"Expected max_tokens=1500, got {call_kwargs.kwargs.get('max_tokens')}"
    )


def test_chemistry_logs_llm_call(tmp_path, monkeypatch):
    """A log entry with event='llm_call' must be written for the chemistry LLM call."""
    log_file = _redirect_log(monkeypatch, tmp_path)

    import backend.tools.chemistry as chemistry_mod
    with patch.object(
        chemistry_mod,
        "check_topic",
        return_value=TopicResult(status="allowed", message=""),
    ):
        with patch.object(chemistry_mod, "retrieve", return_value=[_MOCK_RECORD_CHEMISTRY]):
            with patch.object(chemistry_mod, "_get_client", return_value=_make_chemistry_mock_client()):
                chemistry_mod._client = None
                chemistry_mod.analyze_chemistry("ammonia is 0.5 ppm", None)

    assert log_file.exists(), "Log file was not created"
    lines = [l for l in log_file.read_text().strip().split("\n") if l.strip()]
    assert len(lines) >= 1, "No log entries written"
    entry = json.loads(lines[-1])
    assert entry["event"] == "llm_call", f"Expected event='llm_call', got {entry['event']}"


def test_chemistry_topic_guard_refusal_prevents_llm_call(tmp_path, monkeypatch):
    """When Topic Guard refuses, no LLM call should be made."""
    _redirect_log(monkeypatch, tmp_path)

    mock_client = _make_chemistry_mock_client()

    import backend.tools.chemistry as chemistry_mod
    with patch.object(
        chemistry_mod,
        "check_topic",
        return_value=TopicResult(
            status="refused",
            message="I can only answer aquarium-related questions.",
        ),
    ):
        with patch.object(chemistry_mod, "_get_client", return_value=mock_client):
            chemistry_mod._client = None
            chemistry_mod.analyze_chemistry("What is the capital of France?", None)

    mock_client.chat.completions.create.assert_not_called()


# ===========================================================================
# 5. Assistant Tool — Topic Guard invoked, RAG before OpenAI,
#    max_tokens=1500, logging
# ===========================================================================


def test_assistant_topic_guard_invoked(tmp_path, monkeypatch):
    """Topic Guard must be invoked on every /assistant request."""
    _redirect_log(monkeypatch, tmp_path)

    import backend.assistant as assistant_mod
    with patch.object(
        assistant_mod,
        "check_topic",
        return_value=TopicResult(status="allowed", message=""),
    ) as mock_guard:
        with patch.object(assistant_mod, "retrieve", return_value=[_MOCK_RECORD]):
            with patch.object(assistant_mod, "_get_client", return_value=_make_assistant_mock_client()):
                assistant_mod._client = None
                assistant_mod.get_assistant_reply("Tell me about guppies", [])

    mock_guard.assert_called_once()


def test_assistant_rag_called_before_openai(tmp_path, monkeypatch):
    """RAG must be called before OpenAI in the assistant tool."""
    _redirect_log(monkeypatch, tmp_path)

    call_order = []

    def mock_retrieve(query, top_k=3):
        call_order.append("rag")
        return [_MOCK_RECORD]

    mock_client = _make_assistant_mock_client()
    original_create = mock_client.chat.completions.create

    def mock_create(*args, **kwargs):
        call_order.append("openai")
        return original_create(*args, **kwargs)

    mock_client.chat.completions.create = mock_create

    import backend.assistant as assistant_mod
    with patch.object(
        assistant_mod,
        "check_topic",
        return_value=TopicResult(status="allowed", message=""),
    ):
        with patch.object(assistant_mod, "retrieve", side_effect=mock_retrieve):
            with patch.object(assistant_mod, "_get_client", return_value=mock_client):
                assistant_mod._client = None
                assistant_mod.get_assistant_reply("Tell me about guppies", [])

    assert "rag" in call_order, "RAG was never called"
    assert "openai" in call_order, "OpenAI was never called"
    assert call_order.index("rag") < call_order.index("openai"), (
        "RAG must be called before OpenAI"
    )


def test_assistant_max_tokens_1500(tmp_path, monkeypatch):
    """max_tokens must be 1500 in the assistant tool OpenAI call."""
    _redirect_log(monkeypatch, tmp_path)

    mock_client = _make_assistant_mock_client()

    import backend.assistant as assistant_mod
    with patch.object(
        assistant_mod,
        "check_topic",
        return_value=TopicResult(status="allowed", message=""),
    ):
        with patch.object(assistant_mod, "retrieve", return_value=[_MOCK_RECORD]):
            with patch.object(assistant_mod, "_get_client", return_value=mock_client):
                assistant_mod._client = None
                assistant_mod.get_assistant_reply("Tell me about guppies", [])

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs is not None, "OpenAI was never called"
    assert call_kwargs.kwargs.get("max_tokens") == 1500, (
        f"Expected max_tokens=1500, got {call_kwargs.kwargs.get('max_tokens')}"
    )


def test_assistant_logs_llm_call(tmp_path, monkeypatch):
    """A log entry with event='llm_call' must be written for the assistant LLM call."""
    log_file = _redirect_log(monkeypatch, tmp_path)

    import backend.assistant as assistant_mod
    with patch.object(
        assistant_mod,
        "check_topic",
        return_value=TopicResult(status="allowed", message=""),
    ):
        with patch.object(assistant_mod, "retrieve", return_value=[_MOCK_RECORD]):
            with patch.object(assistant_mod, "_get_client", return_value=_make_assistant_mock_client()):
                assistant_mod._client = None
                assistant_mod.get_assistant_reply("Tell me about guppies", [])

    assert log_file.exists(), "Log file was not created"
    lines = [l for l in log_file.read_text().strip().split("\n") if l.strip()]
    assert len(lines) >= 1, "No log entries written"
    entry = json.loads(lines[-1])
    assert entry["event"] == "llm_call", f"Expected event='llm_call', got {entry['event']}"


def test_assistant_topic_guard_refusal_prevents_llm_call(tmp_path, monkeypatch):
    """When Topic Guard refuses, no LLM call should be made in the assistant."""
    _redirect_log(monkeypatch, tmp_path)

    mock_client = _make_assistant_mock_client()

    import backend.assistant as assistant_mod
    with patch.object(
        assistant_mod,
        "check_topic",
        return_value=TopicResult(
            status="refused",
            message="I can only answer aquarium-related questions.",
        ),
    ):
        with patch.object(assistant_mod, "_get_client", return_value=mock_client):
            assistant_mod._client = None
            result = assistant_mod.get_assistant_reply("What is the capital of France?", [])

    mock_client.chat.completions.create.assert_not_called()
    assert "reply" in result
