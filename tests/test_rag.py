"""
tests/test_rag.py

Unit tests for the RAG pipeline (backend/rag.py).

Requirements: 12.3, 12.7
"""

import os
import sys
import sqlite3

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag import retrieve, RAGError
from knowledge_base.seed import create_schema


def test_empty_fts5_result_returns_empty_list(tmp_path, monkeypatch):
    """When FTS5 returns no records, retrieve() returns an empty list.

    Validates: Requirements 12.3
    """
    db_path = str(tmp_path / "test.db")
    create_schema(db_path)

    # Monkeypatch the DB path used by rag.py so it points to our temp DB
    import backend.rag as rag_module
    monkeypatch.setattr(rag_module, "_db_path", lambda: db_path)

    result = retrieve("nonexistent species xyz123")
    assert result == []


def test_database_error_raises_rag_error(tmp_path, monkeypatch):
    """When the database file is missing, retrieve() raises RAGError.

    Validates: Requirements 12.7
    """
    import backend.rag as rag_module

    # Point to a path that does not exist — rag.py checks os.path.isfile
    # and raises RAGError before even attempting a connection.
    monkeypatch.setattr(rag_module, "_db_path", lambda: str(tmp_path / "missing.db"))

    with pytest.raises(RAGError):
        retrieve("any query")
