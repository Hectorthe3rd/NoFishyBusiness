import json, pytest, sys, os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.tools.chemistry import analyze_chemistry
from backend.rag import RAGError
from backend.models import KBRecord
from backend.topic_guard import TopicResult
from fastapi.responses import JSONResponse

_MOCK_RECORD = KBRecord(
    id=1, species_name="Ammonia", category="chemistry",
    content="Safe: 0 ppm. Caution: 0.25-0.5 ppm. Danger: above 0.5 ppm."
)

def _make_mock_client(params):
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "parameters": params,
        "summary": "Assessment complete."
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock

def test_no_parameters_returns_prompt_no_llm_call():
    with patch("backend.tools.chemistry._get_client") as mock_client:
        with patch("backend.tools.chemistry.check_topic") as mock_guard:
            mock_guard.return_value = TopicResult(status="allowed", message="")
            # Use input with no chemistry terms AND no parameter values
            result = analyze_chemistry("the weather is nice today", None)
            mock_client.return_value.chat.completions.create.assert_not_called()
    assert isinstance(result, JSONResponse)
    body = json.loads(result.body)
    assert body["error_type"] == "no_parameters"

def test_caution_parameter_has_corrective_action():
    params = [{"name": "ammonia", "value": "0.5 ppm", "status": "caution", "corrective_action": "Do a water change."}]
    with patch("backend.tools.chemistry.retrieve", return_value=[_MOCK_RECORD]):
        with patch("backend.tools.chemistry._get_client", return_value=_make_mock_client(params)):
            with patch("backend.tools.chemistry.check_topic") as mock_guard:
                mock_guard.return_value = TopicResult(status="allowed", message="")
                result = analyze_chemistry("ammonia is 0.5 ppm", None)
    assert isinstance(result, dict)
    for param in result["parameters"]:
        if param["status"] in ("caution", "danger"):
            assert param["corrective_action"] is not None
            assert len(param["corrective_action"]) > 0

def test_topic_guard_refusal_prevents_llm_call():
    with patch("backend.tools.chemistry._get_client") as mock_client:
        with patch("backend.tools.chemistry.check_topic") as mock_guard:
            mock_guard.return_value = TopicResult(status="refused", message="Only aquarium questions.")
            result = analyze_chemistry("what is the weather today", None)
            mock_client.return_value.chat.completions.create.assert_not_called()
    assert isinstance(result, JSONResponse)
    body = json.loads(result.body)
    assert body["error_type"] == "topic_refused"

def test_rag_failure_returns_503():
    with patch("backend.tools.chemistry.retrieve", side_effect=RAGError("DB error")):
        with patch("backend.tools.chemistry.check_topic") as mock_guard:
            mock_guard.return_value = TopicResult(status="allowed", message="")
            result = analyze_chemistry("ammonia is 0.5 ppm", None)
    assert isinstance(result, JSONResponse)
    assert result.status_code == 503
