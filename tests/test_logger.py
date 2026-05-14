"""
tests/test_logger.py

Unit tests for backend/logger.py.
Validates Requirements 11.4 — structured JSON logging for LLM calls and errors.
"""

import json
import os
import sys

import pytest

# Ensure the project root is on the path so `backend` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_log_llm_call_writes_correct_fields(tmp_path, monkeypatch):
    """log_llm_call appends a JSON line with the correct fields."""
    import backend.logger as logger_module

    log_file = tmp_path / "test.log"
    monkeypatch.setattr(logger_module, "_LOG_PATH", str(log_file))

    logger_module.log_llm_call(100, 50, 150)

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["event"] == "llm_call"
    assert entry["prompt_tokens"] == 100
    assert entry["completion_tokens"] == 50
    assert entry["total_tokens"] == 150
    assert "ts" in entry
    assert entry["ts"].endswith("Z")


def test_log_error_writes_correct_fields(tmp_path, monkeypatch):
    """log_error appends a JSON line with the correct fields."""
    import backend.logger as logger_module

    log_file = tmp_path / "test.log"
    monkeypatch.setattr(logger_module, "_LOG_PATH", str(log_file))

    logger_module.log_error("RateLimitError", "Rate limit exceeded")

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["event"] == "llm_error"
    assert entry["error_type"] == "RateLimitError"
    assert entry["detail"] == "Rate limit exceeded"
    assert "ts" in entry
    assert entry["ts"].endswith("Z")


def test_log_llm_call_appends_multiple_entries(tmp_path, monkeypatch):
    """Multiple log_llm_call invocations each produce a separate JSON line."""
    import backend.logger as logger_module

    log_file = tmp_path / "test.log"
    monkeypatch.setattr(logger_module, "_LOG_PATH", str(log_file))

    logger_module.log_llm_call(10, 5, 15)
    logger_module.log_llm_call(20, 10, 30)

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["prompt_tokens"] == 10
    assert second["prompt_tokens"] == 20


def test_log_error_appends_multiple_entries(tmp_path, monkeypatch):
    """Multiple log_error invocations each produce a separate JSON line."""
    import backend.logger as logger_module

    log_file = tmp_path / "test.log"
    monkeypatch.setattr(logger_module, "_LOG_PATH", str(log_file))

    logger_module.log_error("TimeoutError", "Request timed out")
    logger_module.log_error("AuthError", "Invalid API key")

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["error_type"] == "TimeoutError"
    assert second["error_type"] == "AuthError"


def test_log_llm_call_ts_format(tmp_path, monkeypatch):
    """The ts field in log_llm_call is a valid ISO 8601 UTC timestamp."""
    import backend.logger as logger_module
    from datetime import datetime

    log_file = tmp_path / "test.log"
    monkeypatch.setattr(logger_module, "_LOG_PATH", str(log_file))

    logger_module.log_llm_call(1, 1, 2)

    entry = json.loads(log_file.read_text(encoding="utf-8").strip())
    ts = entry["ts"]
    # Should parse without error as a UTC datetime
    parsed = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed is not None


def test_log_error_ts_format(tmp_path, monkeypatch):
    """The ts field in log_error is a valid ISO 8601 UTC timestamp."""
    import backend.logger as logger_module
    from datetime import datetime

    log_file = tmp_path / "test.log"
    monkeypatch.setattr(logger_module, "_LOG_PATH", str(log_file))

    logger_module.log_error("SomeError", "some detail")

    entry = json.loads(log_file.read_text(encoding="utf-8").strip())
    ts = entry["ts"]
    parsed = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed is not None
