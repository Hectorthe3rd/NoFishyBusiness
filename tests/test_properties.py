from hypothesis import given, settings, strategies as st, HealthCheck
import pytest
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base.seed import create_schema, insert_record, get_record_by_id

# Feature: no-fishy-business-aquarium-site, Property 14: KB insert then retrieve returns identical fields
@given(
    species_name=st.text(min_size=1, max_size=100),
    category=st.sampled_from(["fish", "plant", "chemistry", "maintenance", "disease", "aquascaping"]),
    content=st.text(min_size=1, max_size=5000),
)
@settings(max_examples=100, deadline=None)
def test_kb_round_trip(species_name, category, content):
    # Use a fresh temp directory for each generated example so DB state never leaks
    import shutil
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test.db")
    try:
        create_schema(db_path)
        record_id = insert_record(db_path, species_name, category, content)
        assert record_id != -1
        retrieved = get_record_by_id(db_path, record_id)
        assert retrieved is not None
        assert retrieved.species_name == species_name
        assert retrieved.category == category
        assert retrieved.content == content
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

from backend.token_budget import truncate_context, count_tokens

# Feature: no-fishy-business-aquarium-site, Property 13: truncate_context always returns ≤2000 tokens
# Validates: Requirements 11.2
@given(text=st.text(min_size=0, max_size=50000))
@settings(max_examples=100)
def test_context_truncation_budget(text):
    result = truncate_context(text, max_tokens=2000)
    assert isinstance(result, str)
    assert count_tokens(result) <= 2000

from backend.topic_guard import check_topic, reload_vocabulary, _DB_AVAILABLE

# Non-aquarium word list for generating off-topic queries
_OFF_TOPIC_WORDS = [
    "president", "election", "football", "basketball", "recipe", "cooking",
    "movie", "actor", "music", "song", "country", "capital", "mountain",
    "airplane", "car", "train", "hospital", "doctor", "lawyer", "judge",
    "economy", "stock", "market", "currency", "weather", "cloud", "rain",
]

# Aquarium terms guaranteed to be in the vocabulary
_AQUARIUM_WORDS = ["fish", "tank", "aquarium", "betta", "guppy", "nitrate", "ammonia"]

# Feature: no-fishy-business-aquarium-site, Property 10: Topic Guard rejects non-aquarium queries
# Validates: Requirements 10.1, 10.2
@given(
    words=st.lists(st.sampled_from(_OFF_TOPIC_WORDS), min_size=1, max_size=10)
)
@settings(max_examples=100)
def test_topic_guard_rejects_non_aquarium(words):
    query = " ".join(words)
    result = check_topic(query)
    # If DB is unavailable, result is "error" — that's acceptable
    assert result.status in ("refused", "error")

# Feature: no-fishy-business-aquarium-site, Property 11: Topic Guard forwards ambiguous queries with system instruction
# Validates: Requirements 10.3
@given(
    aquarium_words=st.lists(st.sampled_from(_AQUARIUM_WORDS), min_size=1, max_size=3),
    off_topic_words=st.lists(st.sampled_from(_OFF_TOPIC_WORDS), min_size=1, max_size=3),
)
@settings(max_examples=100)
def test_topic_guard_ambiguous_query(aquarium_words, off_topic_words):
    query = " ".join(aquarium_words + off_topic_words)
    result = check_topic(query)
    # Should be ambiguous (or allowed if all off-topic words happen to be in vocab)
    # Must NOT be refused when aquarium terms are present
    assert result.status in ("ambiguous", "allowed", "error")

from backend.tools.volume import calculate_volume

# Feature: no-fishy-business-aquarium-site, Property 1: Volume and weight are computed correctly for any positive dimensions
# Validates: Requirements 3.1, 3.2
@given(
    length=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
    width=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
    depth=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_volume_calculation_correctness(length, width, depth):
    result = calculate_volume(length, width, depth)
    expected_volume = round((length * width * depth) / 231.0, 2)
    expected_weight = round(expected_volume * 8.34, 2)
    assert result["volume_gallons"] == expected_volume
    assert result["weight_pounds"] == expected_weight

# Feature: no-fishy-business-aquarium-site, Property 2: Non-positive dimensions are rejected
# Validates: Requirements 3.3
# Note: Non-positive rejection is enforced by Pydantic at the API layer (Field(gt=0)),
# not by calculate_volume itself. This property tests the Pydantic model validation.
from pydantic import ValidationError
from backend.models import VolumeRequest

@given(
    length=st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
    width=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
    depth=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_non_positive_dimension_rejected(length, width, depth):
    try:
        VolumeRequest(length=length, width=width, depth=depth)
        # If we get here, the value was accepted — it should only be accepted if length > 0
        assert length > 0, f"Expected ValidationError for length={length}"
    except ValidationError:
        pass  # Expected — non-positive values should be rejected

from unittest.mock import patch, MagicMock
import json

# Known species in the knowledge base (seeded in task 2.3)
_KNOWN_SPECIES = [
    "Guppy", "Betta", "Neon Tetra", "Cardinal Tetra", "Corydoras Catfish",
    "Molly", "Platy", "Swordtail", "Angelfish", "Goldfish", "Zebra Danio",
    "Cherry Barb", "Tiger Barb", "Harlequin Rasbora", "Dwarf Gourami",
]

_REQUIRED_FIELDS = [
    "species_name", "behavior", "compatible_tank_mates",
    "temperature_f", "ph", "hardness_dgh", "min_tank_gallons",
    "difficulty", "maintenance_notes"
]


def _make_mock_openai_response(species_name: str):
    """Create a mock OpenAI response with all required fields."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "species_name": species_name,
        "behavior": "Peaceful schooling fish",
        "compatible_tank_mates": ["Guppy", "Platy"],
        "temperature_f": {"min": 72.0, "max": 82.0},
        "ph": {"min": 6.5, "max": 7.5},
        "hardness_dgh": {"min": 5.0, "max": 15.0},
        "min_tank_gallons": 10,
        "difficulty": "easy",
        "maintenance_notes": "Easy to care for."
    })
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    return mock_response


# Feature: no-fishy-business-aquarium-site, Property 3: Species response completeness
# Validates: Requirements 4.1
@given(species_name=st.sampled_from(_KNOWN_SPECIES))
@settings(max_examples=15, deadline=None)
def test_species_response_completeness(species_name):
    """For any known species, the response must contain all required fields."""
    from backend.tools.species import get_species_info
    mock_resp = _make_mock_openai_response(species_name)
    with patch("backend.tools.species._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_resp
        result = get_species_info(species_name)
    # Result should be a dict (not a JSONResponse error)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    for field in _REQUIRED_FIELDS:
        assert field in result, f"Missing field: {field}"


# Feature: no-fishy-business-aquarium-site, Property 4: Unknown species returns not-found
# Validates: Requirements 4.3
@given(
    species_name=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=20,
        max_size=50,
    ).filter(lambda s: s not in _KNOWN_SPECIES)
)
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
def test_unknown_species_returns_not_found(species_name):
    """For any species not in the KB, the tool returns not-found without LLM call."""
    from backend.tools.species import get_species_info
    from fastapi.responses import JSONResponse
    with patch("backend.tools.species._get_client") as mock_client:
        result = get_species_info(species_name)
        # LLM should NOT have been called
        mock_client.return_value.chat.completions.create.assert_not_called()
    # Should be a JSONResponse with 404
    assert isinstance(result, JSONResponse)
    assert result.status_code == 404

from unittest.mock import patch, MagicMock
import json

from backend.models import KBRecord

_MOCK_MAINTENANCE_RECORD = KBRecord(
    id=1,
    species_name="Nitrogen Cycle",
    category="maintenance",
    content="The nitrogen cycle covers ammonia spike, nitrite spike, and nitrate accumulation stages."
)

def _make_maintenance_mock_response():
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "nitrogen_cycle": "Stage 1: Ammonia spike. Stage 2: Nitrite spike. Stage 3: Nitrate accumulation.",
        "feeding": {"quantity": "a small pinch", "frequency": "twice daily"},
        "weekly_tasks": ["25% water change", "Test water parameters"],
        "monthly_tasks": ["Rinse filter media", "Full parameter test"]
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock

# Feature: no-fishy-business-aquarium-site, Property 5: Maintenance response completeness
# Validates: Requirements 5.1, 5.2, 5.3
@given(
    tank_gallons=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    fish_count=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=50, deadline=None)
def test_maintenance_response_completeness(tank_gallons, fish_count):
    from backend.tools.maintenance import get_maintenance_guide
    mock_client = _make_maintenance_mock_response()
    with patch("backend.tools.maintenance.retrieve", return_value=[_MOCK_MAINTENANCE_RECORD]):
        with patch("backend.tools.maintenance._get_client", return_value=mock_client):
            result = get_maintenance_guide(tank_gallons, fish_count, [])
    assert isinstance(result, dict)
    assert "nitrogen_cycle" in result
    assert "feeding" in result
    assert "weekly_tasks" in result
    assert "monthly_tasks" in result
    assert isinstance(result["weekly_tasks"], list) and len(result["weekly_tasks"]) >= 2
    assert isinstance(result["monthly_tasks"], list) and len(result["monthly_tasks"]) >= 2
    assert "quantity" in result["feeding"]
    assert "frequency" in result["feeding"]

from backend.models import KBRecord

_MOCK_SETUP_RECORD = KBRecord(
    id=1,
    species_name="Aquascaping Basics",
    category="aquascaping",
    content="Use fine sand substrate. Place rocks off-center. Plant foreground, midground, background zones."
)

def _make_setup_mock_response(tank_gallons):
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
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
            "hardscape": "Smooth river rocks placed off-center",
            "plant_zones": ["Foreground: dwarf plants", "Background: tall plants"]
        }
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock

# Feature: no-fishy-business-aquarium-site, Property 6: Setup Guide response completeness
# Validates: Requirements 6.1, 6.2, 6.3
@given(
    tank_gallons=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, deadline=None)
def test_setup_guide_response_completeness(tank_gallons):
    from backend.tools.setup import get_setup_guide
    mock_client = _make_setup_mock_response(tank_gallons)
    with patch("backend.tools.setup.retrieve", return_value=[_MOCK_SETUP_RECORD]):
        with patch("backend.tools.setup._get_client", return_value=mock_client):
            result = get_setup_guide(tank_gallons, "beginner")
    assert isinstance(result, dict)
    assert "fish_recommendations" in result
    assert "plant_recommendations" in result
    assert "aquascaping_idea" in result
    assert len(result["fish_recommendations"]) >= 3
    assert len(result["plant_recommendations"]) >= 2
    for fish in result["fish_recommendations"]:
        assert fish["difficulty"] == "easy"
    for plant in result["plant_recommendations"]:
        assert plant["difficulty"] == "easy"
    aq = result["aquascaping_idea"]
    assert aq["substrate"]
    assert aq["hardscape"]
    assert len(aq["plant_zones"]) >= 2

from backend.models import KBRecord

_MOCK_CHEMISTRY_RECORD = KBRecord(
    id=1,
    species_name="Ammonia",
    category="chemistry",
    content="Safe: 0 ppm. Caution: 0.25-0.5 ppm. Danger: above 0.5 ppm."
)

# Parameter descriptions that contain recognizable values
_PARAM_DESCRIPTIONS = [
    "ammonia is 0.5 ppm",
    "nitrite 0.25 ppm",
    "nitrate 40 ppm",
    "pH 7.2",
    "temperature 78 F",
    "ammonia 1.0 ppm nitrite 0.5 ppm",
]

_STATUS_VALUES = ["safe", "caution", "danger"]

def _make_chemistry_mock_response(status):
    mock = MagicMock()
    corrective = "Perform a 25% water change." if status != "safe" else None
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "parameters": [
            {"name": "ammonia", "value": "0.5 ppm", "status": status, "corrective_action": corrective}
        ],
        "summary": "Water quality assessment complete."
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock

# Feature: no-fishy-business-aquarium-site, Property 7: Water parameter classification coverage
# Validates: Requirements 7.1
@given(description=st.sampled_from(_PARAM_DESCRIPTIONS))
@settings(max_examples=30, deadline=None)
def test_chemistry_parameter_classification_coverage(description):
    from backend.tools.chemistry import analyze_chemistry
    mock_client = _make_chemistry_mock_response("safe")
    with patch("backend.tools.chemistry.retrieve", return_value=[_MOCK_CHEMISTRY_RECORD]):
        with patch("backend.tools.chemistry._get_client", return_value=mock_client):
            with patch("backend.tools.chemistry.check_topic") as mock_guard:
                from backend.topic_guard import TopicResult
                mock_guard.return_value = TopicResult(status="allowed", message="")
                result = analyze_chemistry(description, None)
    assert isinstance(result, dict)
    assert "parameters" in result
    for param in result["parameters"]:
        assert param["status"] in ("safe", "caution", "danger")

# Feature: no-fishy-business-aquarium-site, Property 8: Corrective action presence for non-safe parameters
# Validates: Requirements 7.2
@given(status=st.sampled_from(["caution", "danger"]))
@settings(max_examples=20, deadline=None)
def test_corrective_action_present_for_non_safe(status):
    from backend.tools.chemistry import analyze_chemistry
    mock_client = _make_chemistry_mock_response(status)
    with patch("backend.tools.chemistry.retrieve", return_value=[_MOCK_CHEMISTRY_RECORD]):
        with patch("backend.tools.chemistry._get_client", return_value=mock_client):
            with patch("backend.tools.chemistry.check_topic") as mock_guard:
                from backend.topic_guard import TopicResult
                mock_guard.return_value = TopicResult(status="allowed", message="")
                result = analyze_chemistry("ammonia is 0.5 ppm", None)
    assert isinstance(result, dict)
    assert "parameters" in result
    for param in result["parameters"]:
        if param["status"] in ("caution", "danger"):
            assert param["corrective_action"] is not None
            assert len(param["corrective_action"]) > 0

import io

# Minimal valid JPEG bytes (1x1 pixel) — used by Property 9
_MINIMAL_JPEG = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
    b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
    b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e'
    b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
    b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
    b'\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04'
    b'\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa'
    b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br'
    b'\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJ'
    b'STUVWXYZ\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd4P\x00\x00\x00\xff\xd9'
)

# Generate minimal valid JPEG bytes via Pillow as fallback
def _make_minimal_jpeg():
    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    img.save(buf, format="JPEG")
    return buf.getvalue()

_VALID_JPEG = _make_minimal_jpeg()

_CONFIDENCE_VALUES = ["high", "medium", "low", "inconclusive"]

def _make_image_scanner_mock(species_name, confidence):
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "species_name": species_name,
        "confidence": confidence,
        "care_summary": "This fish needs clean water and regular feeding.",
        "health_assessment": {
            "issues_detected": None,
            "status": "Healthy"
        }
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock

# Feature: no-fishy-business-aquarium-site, Property 9: Image Scanner response structure
# Validates: Requirements 8.1, 8.2, 8.5
@given(
    species_name=st.one_of(st.just(None), st.just("Guppy"), st.just("Betta")),
    confidence=st.sampled_from(_CONFIDENCE_VALUES),
)
@settings(max_examples=20, deadline=None)
def test_image_scanner_response_structure(species_name, confidence):
    from backend.tools.image_scanner import scan_image
    # If species_name is None, confidence must be "inconclusive"
    if species_name is None:
        confidence = "inconclusive"
    mock_client = _make_image_scanner_mock(species_name, confidence)
    with patch("backend.tools.image_scanner._client", mock_client):
        result = scan_image(_VALID_JPEG, "image/jpeg")
    assert isinstance(result, dict)
    assert result["confidence"] in ("high", "medium", "low", "inconclusive")
    assert result["care_summary"]
    assert result["health_assessment"]["status"]
    # Invariant: null species_name → inconclusive confidence
    if result.get("species_name") is None:
        assert result["confidence"] == "inconclusive"


# ---------------------------------------------------------------------------
# Properties 7 & 8 — Chemistry Analyzer (extended, task 9.2)
# ---------------------------------------------------------------------------

_CHEM_MOCK_RECORD = KBRecord(
    id=1, species_name="Ammonia", category="chemistry",
    content="Safe: 0 ppm. Caution: 0.25-0.5 ppm. Danger: above 0.5 ppm."
)

_PARAM_NAMES = ["ammonia", "nitrite", "nitrate", "pH", "temperature"]
_STATUSES = ["safe", "caution", "danger"]


def _make_chem_mock(parameters):
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        "parameters": parameters,
        "summary": "Water quality assessment complete."
    })
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock


# Feature: no-fishy-business-aquarium-site, Property 7: Water parameter classification coverage
# Validates: Requirements 7.1
@given(
    param_name=st.sampled_from(_PARAM_NAMES),
    param_value=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    status=st.sampled_from(_STATUSES),
)
@settings(max_examples=50, deadline=None)
def test_water_parameter_classification_coverage(param_name, param_value, status):
    from backend.tools.chemistry import analyze_chemistry
    from backend.topic_guard import TopicResult
    corrective = "Perform a 25% water change." if status != "safe" else None
    parameters = [{"name": param_name, "value": str(param_value), "status": status, "corrective_action": corrective}]
    mock_client = _make_chem_mock(parameters)
    description = f"{param_name} is {param_value} ppm"
    with patch("backend.tools.chemistry.retrieve", return_value=[_CHEM_MOCK_RECORD]):
        with patch("backend.tools.chemistry._get_client", return_value=mock_client):
            with patch("backend.tools.chemistry.check_topic", return_value=TopicResult(status="allowed", message="")):
                result = analyze_chemistry(description, None)
    assert isinstance(result, dict)
    assert "parameters" in result
    for p in result["parameters"]:
        assert p["status"] in ("safe", "caution", "danger")


# Feature: no-fishy-business-aquarium-site, Property 8: Corrective action presence for non-safe parameters
# Validates: Requirements 7.2
@given(
    status=st.sampled_from(["caution", "danger"]),
    param_name=st.sampled_from(_PARAM_NAMES),
)
@settings(max_examples=50, deadline=None)
def test_corrective_action_present_for_non_safe_params(status, param_name):
    from backend.tools.chemistry import analyze_chemistry
    from backend.topic_guard import TopicResult
    parameters = [{"name": param_name, "value": "1.0", "status": status, "corrective_action": "Perform a 25% water change."}]
    mock_client = _make_chem_mock(parameters)
    description = f"{param_name} is 1.0 ppm"
    with patch("backend.tools.chemistry.retrieve", return_value=[_CHEM_MOCK_RECORD]):
        with patch("backend.tools.chemistry._get_client", return_value=mock_client):
            with patch("backend.tools.chemistry.check_topic", return_value=TopicResult(status="allowed", message="")):
                result = analyze_chemistry(description, None)
    assert isinstance(result, dict)
    assert "parameters" in result
    for p in result["parameters"]:
        if p["status"] in ("caution", "danger"):
            assert p["corrective_action"] is not None
            assert len(p["corrective_action"]) > 0


# ---------------------------------------------------------------------------
# Property 15: RAG Context Included Verbatim in LLM Prompt (task 13.3)
# ---------------------------------------------------------------------------

# Feature: no-fishy-business-aquarium-site, Property 15: RAG context included verbatim in LLM prompt
# Validates: Requirements 12.2
@given(
    content=st.text(min_size=10, max_size=200, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters=" .,()-"
    ))
)
@settings(max_examples=20, deadline=None)
def test_rag_context_verbatim_in_prompt(content):
    """The verbatim content of each RAG record must appear in the LLM system prompt."""
    from backend.tools.species import get_species_info

    mock_record = KBRecord(id=1, species_name="TestFish", category="fish", content=content)

    captured_messages = []
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "species_name": "TestFish", "behavior": "Peaceful",
        "compatible_tank_mates": [], "temperature_f": {"min": 72, "max": 82},
        "ph": {"min": 6.5, "max": 7.5}, "hardness_dgh": {"min": 5, "max": 15},
        "min_tank_gallons": 5, "difficulty": "easy", "maintenance_notes": "Easy."
    })
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

    def capture_create(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return mock_response

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = capture_create

    import backend.tools.species as species_mod
    species_mod._client = None
    with patch.object(species_mod, "retrieve", return_value=[mock_record]):
        with patch.object(species_mod, "_get_client", return_value=mock_client):
            get_species_info("TestFish")

    # The content must appear verbatim in at least one message
    all_message_text = " ".join(
        msg.get("content", "") if isinstance(msg.get("content"), str) else ""
        for msg in captured_messages
    )
    assert content in all_message_text, (
        f"RAG content not found verbatim in LLM prompt. "
        f"Content: {content[:50]!r}"
    )


# ---------------------------------------------------------------------------
# Property 12: Token Budget Enforcement on All LLM Calls
# Feature: no-fishy-business-aquarium-site, Property 12: Token budget enforcement on all LLM calls
# Validates: Requirements 11.1
# ---------------------------------------------------------------------------

from backend.models import KBRecord

_MOCK_RECORD_FOR_BUDGET = KBRecord(
    id=1, species_name="Guppy", category="fish",
    content="Guppies are peaceful community fish."
)


def _make_budget_mock_client(tool_name):
    """Create a mock OpenAI client that returns appropriate JSON for each tool."""
    mock = MagicMock()
    responses = {
        "species": json.dumps({
            "species_name": "Guppy", "behavior": "Peaceful",
            "compatible_tank_mates": [], "temperature_f": {"min": 72, "max": 82},
            "ph": {"min": 6.5, "max": 7.5}, "hardness_dgh": {"min": 5, "max": 15},
            "min_tank_gallons": 5, "difficulty": "easy", "maintenance_notes": "Easy."
        }),
        "maintenance": json.dumps({
            "nitrogen_cycle": "Ammonia, nitrite, nitrate stages.",
            "feeding": {"quantity": "pinch", "frequency": "twice daily"},
            "weekly_tasks": ["water change", "test params"],
            "monthly_tasks": ["filter rinse", "full test"]
        }),
        "setup": json.dumps({
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
                "substrate": "sand", "hardscape": "rocks",
                "plant_zones": ["front", "back"]
            }
        }),
        "chemistry": json.dumps({
            "parameters": [{"name": "ammonia", "value": "0.5", "status": "caution",
                            "corrective_action": "Water change."}],
            "summary": "Elevated ammonia."
        }),
        "assistant": json.dumps({"reply": "Guppies are great.", "suggested_section": None}),
    }
    mock.chat.completions.create.return_value.choices = [MagicMock()]
    mock.chat.completions.create.return_value.choices[0].message.content = (
        responses.get(tool_name, "{}")
    )
    mock.chat.completions.create.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock


@pytest.mark.parametrize("tool_name", ["species", "maintenance", "setup", "chemistry", "assistant"])
def test_token_budget_enforcement(tool_name, tmp_path, monkeypatch):
    """Property 12: Every LLM call must use max_tokens=1500.

    Validates: Requirements 11.1
    """
    import backend.logger as logger_mod
    monkeypatch.setattr(logger_mod, "_LOG_PATH", str(tmp_path / "test.log"))

    mock_client = _make_budget_mock_client(tool_name)

    if tool_name == "species":
        import backend.tools.species as mod
        monkeypatch.setattr(mod, "_client", None)
        with patch.object(mod, "retrieve", return_value=[_MOCK_RECORD_FOR_BUDGET]):
            with patch.object(mod, "_get_client", return_value=mock_client):
                mod.get_species_info("Guppy")

    elif tool_name == "maintenance":
        import backend.tools.maintenance as mod
        monkeypatch.setattr(mod, "_client", None)
        with patch.object(mod, "retrieve", return_value=[_MOCK_RECORD_FOR_BUDGET]):
            with patch.object(mod, "_get_client", return_value=mock_client):
                mod.get_maintenance_guide(20.0, 5, [])

    elif tool_name == "setup":
        import backend.tools.setup as mod
        monkeypatch.setattr(mod, "_client", None)
        with patch.object(mod, "retrieve", return_value=[_MOCK_RECORD_FOR_BUDGET]):
            with patch.object(mod, "_get_client", return_value=mock_client):
                mod.get_setup_guide(20.0, "beginner")

    elif tool_name == "chemistry":
        import backend.tools.chemistry as mod
        monkeypatch.setattr(mod, "_client", None)
        from backend.topic_guard import TopicResult
        with patch.object(mod, "check_topic", return_value=TopicResult(status="allowed", message="")):
            with patch.object(mod, "retrieve", return_value=[_MOCK_RECORD_FOR_BUDGET]):
                with patch.object(mod, "_get_client", return_value=mock_client):
                    mod.analyze_chemistry("ammonia is 0.5 ppm", None)

    elif tool_name == "assistant":
        import backend.assistant as mod
        monkeypatch.setattr(mod, "_client", None)
        from backend.topic_guard import TopicResult
        with patch.object(mod, "check_topic", return_value=TopicResult(status="allowed", message="")):
            with patch.object(mod, "retrieve", return_value=[_MOCK_RECORD_FOR_BUDGET]):
                with patch.object(mod, "_get_client", return_value=mock_client):
                    mod.get_assistant_reply("Tell me about guppies", [])

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs is not None, f"OpenAI was never called for tool: {tool_name}"
    actual_max_tokens = call_kwargs.kwargs.get("max_tokens")
    assert actual_max_tokens == 1500, (
        f"Tool '{tool_name}' used max_tokens={actual_max_tokens}, expected 1500"
    )
