"""
backend/topic_guard.py

Aquarium topic classifier for NoFishyBusiness.

Classifies incoming queries as:
  - "allowed"   — query contains only aquarium-related terms
  - "refused"   — query contains no aquarium-related terms
  - "ambiguous" — query contains a mix of aquarium and off-topic terms

The vocabulary is loaded once at module import time from:
  1. A hardcoded seed list of common aquarium terms.
  2. The species_name and category fields of every record in kb_records.

If the database is unavailable at import time, _DB_AVAILABLE is set to False
and check_topic() returns an error TopicResult without forwarding to the LLM.
"""

import difflib
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Set

# ---------------------------------------------------------------------------
# TopicResult
# ---------------------------------------------------------------------------

@dataclass
class TopicResult:
    """Result returned by check_topic().

    Attributes:
        status:  "allowed" | "refused" | "ambiguous" | "error"
        message: Human-readable message (non-empty only for refused/error).
    """
    status: str   # "allowed" | "refused" | "ambiguous" | "error"
    message: str  # empty string when status is "allowed" or "ambiguous"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REFUSAL_MESSAGE = (
    "I can only answer aquarium-related questions. "
    "Please ask about fish, plants, water chemistry, or tank maintenance."
)

_ERROR_MESSAGE = (
    "The topic filter is currently unavailable. "
    "Please try again later."
)

# Hardcoded seed vocabulary — common aquarium terms that may not appear in
# every knowledge base deployment.
_SEED_TERMS: Set[str] = {
    "fish", "tank", "aquarium", "ph", "nitrate", "ammonia", "cichlid",
    "planted", "freshwater", "saltwater", "aquatic", "filter", "heater",
    "substrate", "hardscape", "nitrogen", "nitrite", "guppy", "betta",
    "tetra", "pleco", "corydoras", "molly", "platy", "swordtail",
    "angelfish", "discus", "oscar", "goldfish", "koi", "shrimp", "snail",
    "algae", "plant", "moss", "fern", "anubias", "java", "water", "gallon",
    "parameter", "chemistry", "disease", "treatment", "maintenance",
    "feeding", "species", "compatibility", "temperature", "hardness",
    "dgh", "ppm", "oxygen", "co2", "lighting", "aquascape",
}

# ---------------------------------------------------------------------------
# Vocabulary loading
# ---------------------------------------------------------------------------

_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "knowledge_base",
    "aquarium.db",
)

_DB_AVAILABLE: bool = False
_VOCABULARY: Set[str] = set()


def _tokenize(text: str) -> Set[str]:
    """Split *text* into lowercase word tokens, stripping punctuation."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _load_vocabulary() -> None:
    """Populate _VOCABULARY from the seed list and the knowledge base.

    Sets _DB_AVAILABLE to True on success, False on any database error.
    Called once at module import time.
    """
    global _DB_AVAILABLE, _VOCABULARY

    # Always include the hardcoded seed terms.
    vocab: Set[str] = set(_SEED_TERMS)

    db_path = os.path.normpath(_DB_PATH)
    if not os.path.isfile(db_path):
        # Database file does not exist yet — use seed terms only and mark
        # the DB as unavailable so check_topic() returns an error.
        _VOCABULARY = vocab
        _DB_AVAILABLE = False
        return

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT species_name, category FROM kb_records"
            ).fetchall()

        for species_name, category in rows:
            if species_name:
                vocab.update(_tokenize(species_name))
            if category:
                vocab.update(_tokenize(category))

        _VOCABULARY = vocab
        _DB_AVAILABLE = True

    except sqlite3.Error:
        # DB exists but is unreadable — fall back to seed terms only.
        _VOCABULARY = vocab
        _DB_AVAILABLE = False


# Load vocabulary when the module is first imported.
_load_vocabulary()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_topic(query: str) -> TopicResult:
    """Classify *query* as allowed, refused, ambiguous, or error.

    Args:
        query: The raw user query string.

    Returns:
        A TopicResult with:
          - status "error"     if the DB was unavailable at startup.
          - status "refused"   if no aquarium terms are found in the query.
          - status "allowed"   if every content word is an aquarium term.
          - status "ambiguous" if the query mixes aquarium and off-topic terms.
    """
    if not _DB_AVAILABLE:
        return TopicResult(status="error", message=_ERROR_MESSAGE)

    # Tokenize the query into individual lowercase words.
    query_tokens = _tokenize(query)

    # Remove very short tokens (single characters, digits alone) that are
    # not meaningful for topic classification.
    meaningful_tokens = {t for t in query_tokens if len(t) > 1}

    if not meaningful_tokens:
        # Empty or punctuation-only query — treat as refused.
        return TopicResult(status="refused", message=_REFUSAL_MESSAGE)

    # Check each token against the vocabulary, also trying common suffixes
    # (plurals, -ing, -ed) so "guppies" matches "guppy", "feeding" matches "feed", etc.
    def _is_aquarium_token(token: str) -> bool:
        if token in _VOCABULARY:
            return True
        # Try stripping common suffixes for plural/verb forms
        for suffix in ("ies", "es", "s", "ing", "ed", "er"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                stem = token[: -len(suffix)]
                if stem in _VOCABULARY:
                    return True
                # "ies" → "y" (guppies → guppy)
                if suffix == "ies" and (stem + "y") in _VOCABULARY:
                    return True
        # Fuzzy match — catches typos, transpositions, and misspellings
        # (e.g. "aquarim" → "aquarium", "fihs" → "fish", "bata" → "betta")
        # Only attempt fuzzy matching for tokens long enough to be meaningful.
        if len(token) >= 4:
            matches = difflib.get_close_matches(token, _VOCABULARY, n=1, cutoff=0.82)
            if matches:
                return True
        return False

    aquarium_tokens = {t for t in meaningful_tokens if _is_aquarium_token(t)}
    off_topic_tokens = meaningful_tokens - aquarium_tokens

    if not aquarium_tokens:
        # No aquarium terms at all → refuse.
        return TopicResult(status="refused", message=_REFUSAL_MESSAGE)

    if not off_topic_tokens:
        # Every meaningful word is an aquarium term → allow.
        return TopicResult(status="allowed", message="")

    # Mix of aquarium and off-topic terms → ambiguous.
    return TopicResult(status="ambiguous", message="")


def reload_vocabulary() -> None:
    """Re-load the vocabulary from the database.

    Useful after the knowledge base has been seeded or updated at runtime.
    Exposed primarily for testing and for the FastAPI lifespan startup hook.
    """
    _load_vocabulary()
