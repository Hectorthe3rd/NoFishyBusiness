import os, sys, sqlite3
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base.seed import create_schema, insert_record, get_record_by_id

# Validates: Requirements 12.5 (Property 16)

def test_missing_species_name_is_skipped(tmp_path):
    db_path = str(tmp_path / "test.db")
    create_schema(db_path)
    result = insert_record(db_path, "", "fish", "Some content")
    assert result == -1

def test_missing_category_is_skipped(tmp_path):
    db_path = str(tmp_path / "test.db")
    create_schema(db_path)
    result = insert_record(db_path, "Guppy", "", "Some content")
    assert result == -1

def test_missing_content_is_skipped(tmp_path):
    db_path = str(tmp_path / "test.db")
    create_schema(db_path)
    result = insert_record(db_path, "Guppy", "fish", "")
    assert result == -1

def test_skipped_record_not_in_fts(tmp_path):
    """Skipped records should not appear in FTS5 search results."""
    db_path = str(tmp_path / "test.db")
    create_schema(db_path)
    insert_record(db_path, "", "fish", "Some content about guppies")

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT rowid FROM kb_fts WHERE kb_fts MATCH 'guppies'"
        ).fetchall()
    assert len(rows) == 0

def test_valid_record_is_inserted(tmp_path):
    """Valid records should be inserted and retrievable."""
    db_path = str(tmp_path / "test.db")
    create_schema(db_path)
    result = insert_record(db_path, "Guppy", "fish", "Guppies are great fish.")
    assert result != -1
    record = get_record_by_id(db_path, result)
    assert record is not None
    assert record.species_name == "Guppy"
