"""
backend/logger.py

Structured log writer for NoFishyBusiness.
Appends newline-delimited JSON entries to backend/app.log.
"""

import json
import os
from datetime import datetime, timezone

# Resolve log file path relative to this file's directory (backend/)
_LOG_PATH = os.path.join(os.path.dirname(__file__), "app.log")


def _utc_now() -> str:
    """Return current UTC time as an ISO 8601 string ending with 'Z'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_llm_call(prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
    """Append a JSON line to backend/app.log recording an LLM API call.

    Args:
        prompt_tokens:      Number of tokens in the prompt.
        completion_tokens:  Number of tokens in the completion.
        total_tokens:       Total tokens consumed by the call.
    """
    entry = {
        "event": "llm_call",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "ts": _utc_now(),
    }
    _append(entry)


def log_error(error_type: str, detail: str) -> None:
    """Append a JSON line to backend/app.log recording an error.

    Args:
        error_type: Short error class name (e.g. "RateLimitError").
        detail:     Human-readable description or exception message.
    """
    entry = {
        "event": "llm_error",
        "error_type": error_type,
        "detail": detail,
        "ts": _utc_now(),
    }
    _append(entry)


def _append(entry: dict) -> None:
    """Serialize *entry* as a JSON line and append it to the log file."""
    line = json.dumps(entry, ensure_ascii=False)
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
