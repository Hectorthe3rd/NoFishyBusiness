import json, pytest, sys, os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.assistant import get_assistant_reply
from backend.rag import RAGError
from backend.models import KBRecord
from backend.topic_guard import TopicResult
import openai

_MOCK_RECORD = KBRecord(id=1, species_name="Guppy", category="fish",
    content="Guppies are peaceful community fish.")

def _make_mock_client():
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "reply": "Guppies are great beginner fish.",
        "suggested_section": "Species Tool"
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150)
    return mock

def test_empty_rag_returns_insufficient_info_no_llm_call():
    """Req 9.5 — empty RAG returns insufficient info message, no LLM call."""
    with patch("backend.assistant.check_topic",
               return_value=TopicResult(status="allowed", message="")):
        with patch("backend.assistant.retrieve", return_value=[]):
            with patch("backend.assistant._get_client") as mock_client:
                result = get_assistant_reply("Tell me about guppies", [])
                mock_client.return_value.chat.completions.create.assert_not_called()
    assert isinstance(result, dict)
    assert "reply" in result
    assert "insufficient" in result["reply"].lower() or "information" in result["reply"].lower()

def test_llm_failure_returns_temporarily_unavailable():
    """Req 9.6 — LLM API failure returns 'temporarily unavailable' message."""
    with patch("backend.assistant.check_topic",
               return_value=TopicResult(status="allowed", message="")):
        with patch("backend.assistant.retrieve", return_value=[_MOCK_RECORD]):
            with patch("backend.assistant._get_client") as mock_client:
                mock_client.return_value.chat.completions.create.side_effect = openai.OpenAIError("API down")
                result = get_assistant_reply("Tell me about guppies", [])
    assert isinstance(result, dict)
    assert "reply" in result
    assert "temporarily unavailable" in result["reply"].lower() or "unavailable" in result["reply"].lower()

def test_topic_guard_refusal_prevents_llm_call():
    """Topic Guard refusal must prevent any LLM call."""
    with patch("backend.assistant.check_topic",
               return_value=TopicResult(status="refused", message="Off-topic.")):
        with patch("backend.assistant._get_client") as mock_client:
            result = get_assistant_reply("What is the capital of France?", [])
            mock_client.return_value.chat.completions.create.assert_not_called()
    assert isinstance(result, dict)
    assert "reply" in result
    assert result["reply"] == "Off-topic."
