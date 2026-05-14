"""
Token budget utilities for the NoFishyBusiness backend.

Provides token counting and context truncation using tiktoken's cl100k_base
encoding (the encoding used by gpt-4o-mini).
"""

import tiktoken

# Load the encoding once at module level to avoid repeated initialisation cost.
_ENCODING_NAME = "cl100k_base"

try:
    _enc = tiktoken.get_encoding(_ENCODING_NAME)
except Exception:
    _enc = None


def count_tokens(text: str) -> int:
    """Return the number of tokens in *text* using cl100k_base encoding.

    Args:
        text: The string to count tokens for.

    Returns:
        Integer token count.  Returns 0 if the encoding is unavailable or
        *text* is empty.
    """
    if not text:
        return 0
    if _enc is None:
        return 0
    try:
        return len(_enc.encode(text))
    except Exception:
        return 0


def truncate_context(context: str, max_tokens: int = 2000) -> str:
    """Truncate *context* so that its token count does not exceed *max_tokens*.

    The function encodes the string to tokens, slices to *max_tokens*, then
    decodes back to a string.  It **never raises** — any error results in
    returning either the (possibly truncated) string or an empty string.

    Args:
        context:    The context string to truncate.
        max_tokens: Maximum number of tokens allowed (default 2000).

    Returns:
        A string whose token count is ≤ *max_tokens*.  Returns an empty string
        on any encoding/decoding error.
    """
    if not context:
        return ""
    try:
        enc = _enc
        if enc is None:
            # Fallback: re-acquire encoding; if still unavailable return empty.
            try:
                enc = tiktoken.get_encoding(_ENCODING_NAME)
            except Exception:
                return ""

        tokens = enc.encode(context)
        if len(tokens) <= max_tokens:
            return context

        truncated_tokens = tokens[:max_tokens]
        return enc.decode(truncated_tokens)
    except Exception:
        return ""
