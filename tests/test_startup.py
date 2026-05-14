"""
tests/test_startup.py

Unit tests for startup validation in backend/main.py.
Validates Requirements 1.6, 1.7 — startup checks for OPENAI_API_KEY and aquarium.db.
"""

import asyncio
import os
import sys

import pytest

# Ensure the project root is on the path so `backend` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_lifespan(monkeypatch, db_path_override=None):
    """Helper: run the lifespan context manager to completion (or until sys.exit).

    Patches backend.main._db_path to return db_path_override when provided,
    and patches topic_guard import to avoid loading the real DB during tests.
    """
    import backend.main as main_module
    from unittest.mock import patch, MagicMock

    patches = []

    if db_path_override is not None:
        patches.append(patch.object(main_module, "_db_path", return_value=db_path_override))

    # Prevent topic_guard from actually loading the real knowledge base
    fake_topic_guard = MagicMock()
    patches.append(patch.dict("sys.modules", {"backend.topic_guard": fake_topic_guard}))

    async def run():
        async with main_module.lifespan(main_module.app):
            pass

    with patches[0] if len(patches) > 0 else _noop_ctx():
        with patches[1] if len(patches) > 1 else _noop_ctx():
            asyncio.run(run())


class _noop_ctx:
    """A no-op context manager used as a placeholder."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Test: missing OPENAI_API_KEY causes sys.exit(1)
# ---------------------------------------------------------------------------

def test_missing_api_key_causes_exit(monkeypatch, tmp_path, capsys):
    """Missing OPENAI_API_KEY should cause sys.exit(1) with 'OPENAI_API_KEY' in output."""
    import backend.main as main_module
    from unittest.mock import patch, MagicMock

    # Create a valid DB file so only the API key check fails
    db_file = tmp_path / "aquarium.db"
    db_file.write_bytes(b"SQLite format 3\x00" + b"\x00" * 84)

    # Remove the API key from the environment
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Prevent load_dotenv from picking up a real .env file
    with patch("backend.main.load_dotenv"):
        with patch.object(main_module, "_db_path", return_value=str(db_file)):
            with patch.dict("sys.modules", {"backend.topic_guard": MagicMock()}):
                with pytest.raises(SystemExit) as exc_info:
                    asyncio.run(_lifespan_coro(main_module))

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.out


def test_empty_api_key_causes_exit(monkeypatch, tmp_path, capsys):
    """An empty OPENAI_API_KEY should also cause sys.exit(1) with 'OPENAI_API_KEY' in output."""
    import backend.main as main_module
    from unittest.mock import patch, MagicMock

    db_file = tmp_path / "aquarium.db"
    db_file.write_bytes(b"SQLite format 3\x00" + b"\x00" * 84)

    monkeypatch.setenv("OPENAI_API_KEY", "")

    with patch("backend.main.load_dotenv"):
        with patch.object(main_module, "_db_path", return_value=str(db_file)):
            with patch.dict("sys.modules", {"backend.topic_guard": MagicMock()}):
                with pytest.raises(SystemExit) as exc_info:
                    asyncio.run(_lifespan_coro(main_module))

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.out


# ---------------------------------------------------------------------------
# Test: missing aquarium.db causes sys.exit(1)
# ---------------------------------------------------------------------------

def test_missing_db_causes_exit(monkeypatch, tmp_path, capsys):
    """Missing aquarium.db should cause sys.exit(1)."""
    import backend.main as main_module
    from unittest.mock import patch, MagicMock

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-valid")

    # Point to a path that does not exist
    missing_db = str(tmp_path / "missing.db")

    with patch("backend.main.load_dotenv"):
        with patch.object(main_module, "_db_path", return_value=missing_db):
            with patch.dict("sys.modules", {"backend.topic_guard": MagicMock()}):
                with pytest.raises(SystemExit) as exc_info:
                    asyncio.run(_lifespan_coro(main_module))

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test: valid configuration does NOT cause sys.exit
# ---------------------------------------------------------------------------

def test_valid_config_does_not_exit(monkeypatch, tmp_path):
    """When OPENAI_API_KEY is set and aquarium.db exists, lifespan should not exit."""
    import backend.main as main_module
    from unittest.mock import patch, MagicMock

    db_file = tmp_path / "aquarium.db"
    db_file.write_bytes(b"SQLite format 3\x00" + b"\x00" * 84)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-valid")

    with patch("backend.main.load_dotenv"):
        with patch.object(main_module, "_db_path", return_value=str(db_file)):
            with patch.dict("sys.modules", {"backend.topic_guard": MagicMock()}):
                # Should complete without raising SystemExit
                asyncio.run(_lifespan_coro(main_module))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _lifespan_coro(main_module):
    """Run the lifespan context manager as a coroutine."""
    async with main_module.lifespan(main_module.app):
        pass
