"""
backend/rag.py

RAG (Retrieval-Augmented Generation) pipeline for NoFishyBusiness.

Provides a single public function:

    retrieve(query, top_k=3) -> list[KBRecord]

which runs an FTS5 full-text search against the local SQLite knowledge base
and returns up to *top_k* matching records.

Requirements: 12.1, 12.2, 12.3, 12.7
"""

import os
import re
import sqlite3

from backend.models import KBRecord

# ---------------------------------------------------------------------------
# Stop words — common English words that don't exist in the knowledge base
# and cause FTS5 to return zero results when included in a query.
# ---------------------------------------------------------------------------
_STOP_WORDS = {
    "tell", "me", "about", "what", "how", "is", "are", "the", "a", "an",
    "do", "does", "can", "could", "would", "should", "will", "my", "your",
    "for", "to", "in", "of", "and", "or", "with", "on", "at", "by", "its",
    "good", "best", "need", "want", "like", "get", "have", "has", "had",
    "some", "any", "all", "this", "that", "these", "those", "it", "was",
    "please", "help", "give", "show", "explain", "describe", "list", "im",
    "i", "we", "they", "he", "she", "you", "our", "their", "his", "her",
    "dangerous", "safe", "bad", "good", "okay", "ok", "just", "also",
    "very", "really", "quite", "too", "so", "if", "then", "when", "where",
    "why", "which", "who", "there", "here", "up", "down", "out", "into",
    "from", "as", "but", "not", "no", "yes", "be", "been", "being",
}


def sanitize_query(text: str) -> str:
    """Convert a free-form user sentence into a safe FTS5 keyword query.

    Steps:
    1. Lowercase and strip punctuation that FTS5 treats as operators
        (periods, question marks, exclamation marks, commas, colons, etc.)
    2. Remove stop words that don't appear in the knowledge base.
    3. Return the remaining keywords joined by spaces.
    4. If nothing survives, return the original text with only punctuation
        stripped (so FTS5 at least gets something to work with).

    Examples:
        "Tell me about guppies!"          → "guppies"
        "ammonia is at 0.25ppm. Shrimp?"  → "ammonia 0 25ppm shrimp"
        "nitrogen cycle maintenance"      → "nitrogen cycle maintenance"
    """
    # Step 1: replace punctuation that breaks FTS5 with spaces
    # Keep alphanumeric characters and spaces; strip everything else
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())

    # Step 2: tokenise and remove stop words; keep tokens longer than 1 char
    tokens = [t for t in cleaned.split() if t not in _STOP_WORDS and len(t) > 1]

    if tokens:
        return " ".join(tokens)

    # Fallback: just strip punctuation from the original, keep all words
    return re.sub(r"[^\w\s]", " ", text).strip()

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class RAGError(Exception):
    """Raised when the RAG pipeline encounters a database error.

    Callers should treat this as a 503-level failure: the knowledge base is
    unavailable and no LLM call should be made.
    """


# ---------------------------------------------------------------------------
# DB path helper
# ---------------------------------------------------------------------------

def _db_path() -> str:
    """Return the absolute path to knowledge_base/aquarium.db.

    Resolved relative to the project root (one level above backend/) so the
    path is correct regardless of the working directory used to launch the
    server.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "knowledge_base", "aquarium.db")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def retrieve(query: str, top_k: int = 3) -> list[KBRecord]:
    """Run FTS5 full-text search against the knowledge base.

    Accepts any free-form user text — sentences, questions, species names, etc.
    The query is sanitized (punctuation stripped, stop words removed) before
    being passed to FTS5. If the sanitized query returns no results, individual
    keywords are tried one at a time and the best match is returned.

    Args:
        query:  Any user-provided text (sentence, keyword, species name, etc.)
        top_k:  Maximum number of records to return (default 3).

    Returns:
        A list of up to *top_k* :class:`~backend.models.KBRecord` objects.
        Returns an empty list when no records match the query.

    Raises:
        RAGError: On any :class:`sqlite3.Error`, including a missing database
                  file.
    """
    db = _db_path()

    if not os.path.isfile(db):
        raise RAGError(
            f"Knowledge base not found at '{db}'. "
            "Run 'python knowledge_base/seed.py' to create and populate it."
        )

    # Sanitize the raw query into safe FTS5 keywords
    clean = sanitize_query(query)

    def _run_fts(conn, fts_query: str) -> list:
        """Execute one FTS5 MATCH query and return rows."""
        try:
            cursor = conn.execute(
                "SELECT rowid, species_name, category, content "
                "FROM kb_fts "
                "WHERE kb_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?",
                (fts_query, top_k),
            )
            return cursor.fetchall()
        except sqlite3.OperationalError:
            # FTS5 syntax error — this specific query form failed
            return []

    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row

            # Attempt 1: full sanitized query (e.g. "guppies nitrogen cycle")
            rows = _run_fts(conn, clean)

            # Attempt 2: try each keyword individually and merge results
            if not rows:
                seen_ids = set()
                rows = []
                for keyword in clean.split():
                    if len(keyword) < 3:
                        continue
                    kw_rows = _run_fts(conn, keyword)
                    for r in kw_rows:
                        if r["rowid"] not in seen_ids:
                            seen_ids.add(r["rowid"])
                            rows.append(r)
                        if len(rows) >= top_k:
                            break
                    if len(rows) >= top_k:
                        break

    except sqlite3.Error as exc:
        raise RAGError(f"Database error during FTS5 retrieval: {exc}") from exc

    return [
        KBRecord(
            id=row["rowid"],
            species_name=row["species_name"],
            category=row["category"],
            content=row["content"],
        )
        for row in rows
    ]
