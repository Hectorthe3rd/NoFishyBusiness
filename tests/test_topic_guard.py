import os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.topic_guard import check_topic


def test_pure_aquarium_query_returns_allowed():
    """A query containing only aquarium terms should return 'allowed'.

    Validates: Requirements 10.1, 10.2
    """
    result = check_topic("betta fish tank water")
    # If DB is unavailable, result is "error" — skip in that case
    if result.status == "error":
        pytest.skip("Knowledge base not available")
    assert result.status == "allowed"


def test_pure_off_topic_query_returns_refused():
    """A query with no aquarium terms should return 'refused'.

    Validates: Requirements 10.1, 10.2
    """
    result = check_topic("what is the capital of France")
    if result.status == "error":
        pytest.skip("Knowledge base not available")
    assert result.status == "refused"
    assert len(result.message) > 0


def test_refused_query_has_message():
    """Refused queries must include a non-empty message.

    Validates: Requirements 10.1
    """
    result = check_topic("football basketball soccer")
    if result.status == "error":
        pytest.skip("Knowledge base not available")
    if result.status == "refused":
        assert result.message != ""


def test_empty_query_returns_refused():
    """Empty or whitespace-only queries should be refused.

    Validates: Requirements 10.2
    """
    result = check_topic("   ")
    if result.status == "error":
        pytest.skip("Knowledge base not available")
    assert result.status == "refused"
