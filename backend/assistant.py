"""
backend/assistant.py

AI Assistant for NoFishyBusiness — "The Aquatic Consultant"

Uses the PromptFactory to generate a contextual system prompt that adapts
its tone and depth to the user's experience level.

The topic guard is intentionally NOT used here — the LLM system prompt
handles scope. This allows greetings, site questions, small talk, and
typo-laden messages to flow through naturally while the LLM steers the
conversation back to aquariums when needed.

Provides two public functions:
  - get_assistant_reply()  — standard JSON response (used by /assistant)
  - stream_assistant_reply() — generator that yields text chunks (used by
    /assistant/stream for real-time word-by-word output)

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 10.4, 11.1, 11.2
"""

import json
import re as _re
from typing import Generator

import openai

from backend import logger, token_budget
from backend.models import UserContext
from backend.prompt_factory import PromptFactory
from backend.rag import RAGError, retrieve

# ---------------------------------------------------------------------------
# OpenAI client — lazy singleton (reads OPENAI_API_KEY from environment)
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    """Return the shared OpenAI client, creating it on first use."""
    global _client
    if _client is None:
        _client = openai.OpenAI()
    return _client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UNAVAILABLE_REPLY = (
    "The assistant is temporarily unavailable. Please try again later."
)

# Stop words filtered out before building the RAG query so FTS5 gets
# meaningful aquarium keywords rather than common English filler words.
_STOP_WORDS = {
    "tell", "me", "about", "what", "how", "is", "are", "the", "a", "an",
    "do", "does", "can", "could", "would", "should", "will", "my", "your",
    "for", "to", "in", "of", "and", "or", "with", "on", "at", "by",
    "good", "best", "need", "want", "like", "get", "have", "has", "had",
    "some", "any", "all", "this", "that", "these", "those", "it", "its",
    "please", "help", "give", "show", "explain", "describe", "list",
    "hi", "hey", "hello", "thanks", "thank", "ok", "okay", "sure", "yes",
    "no", "yeah", "yep", "nope", "alright", "sounds", "great", "cool",
    "nice", "awesome", "got", "just", "so", "up", "out", "if", "but",
    "not", "be", "was", "were", "been", "am", "im", "i",
}

# HTML tags the LLM occasionally emits — stripped before returning to frontend.
_HTML_TAG_RE = _re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Convert common HTML tags to their Markdown equivalents, strip the rest."""
    # <strong>…</strong> / <b>…</b>  →  **…**
    text = _re.sub(r"<strong>(.*?)</strong>", r"**\1**", text, flags=_re.DOTALL)
    text = _re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=_re.DOTALL)
    # <em>…</em> / <i>…</i>  →  *…*
    text = _re.sub(r"<em>(.*?)</em>", r"*\1*", text, flags=_re.DOTALL)
    text = _re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=_re.DOTALL)
    # <br> / <br/>  →  newline
    text = _re.sub(r"<br\s*/?>", "\n", text, flags=_re.IGNORECASE)
    # <p>…</p>  →  paragraph break
    text = _re.sub(r"<p>(.*?)</p>", r"\1\n\n", text, flags=_re.DOTALL)
    # Strip any remaining tags
    text = _HTML_TAG_RE.sub("", text)
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_assistant_reply(message: str, history: list[dict]) -> dict:
    """Generate an AI assistant reply for the given message and conversation history.

    Flow:
    1. Build a RAG query from meaningful keywords in the message.
    2. Retrieve context from the knowledge base (best-effort — empty results
       are handled gracefully by the LLM prompt, not hard-refused).
    3. Truncate context to 2000 tokens.
    4. Build the system prompt via PromptFactory.
    5. Call OpenAI with max_tokens=1500.
    6. Strip any HTML the model emits, parse JSON, return reply.

    Args:
        message: The user's current message.
        history: Conversation history as a list of {"role": ..., "content": ...}
                 dicts. The backend uses the last 10 items (5 pairs).

    Returns:
        A dict with keys "reply" (str) and "suggested_section" (str | None).
    """
    # 1. Build RAG query from meaningful keywords ----------------------------
    words = _re.findall(r"[a-z0-9]+", message.lower())
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    rag_query = " ".join(keywords) if keywords else message

    # 2. RAG retrieval -------------------------------------------------------
    # Empty results are fine — the LLM prompt handles "no context" gracefully
    # by engaging conversationally and steering back to aquarium topics.
    context = ""
    try:
        records = retrieve(rag_query)
        if not records and rag_query != message:
            # Fallback: try the raw message if keyword extraction stripped too much
            records = retrieve(message)
        if records:
            raw_context = "\n\n".join(record.content for record in records)
            # 3. Truncate context to token budget ----------------------------
            context = token_budget.truncate_context(raw_context, 2000)
    except RAGError as exc:
        logger.log_error("RAGError", str(exc))
        # Don't hard-fail — proceed with empty context so the LLM can still
        # respond conversationally.

    # 4. Build system prompt -------------------------------------------------
    user_ctx = UserContext.guest()
    system_prompt = PromptFactory.get_prompt(
        feature_id="assistant",
        context=context,
        user=user_ctx,
    )

    # 5. Build messages array ------------------------------------------------
    recent_history = history[-10:] if len(history) > 10 else history

    messages = (
        recent_history
        + [{"role": "system", "content": system_prompt}]
        + [{"role": "user", "content": message}]
    )

    # 6. OpenAI call ---------------------------------------------------------
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=messages,
        )
    except openai.OpenAIError as exc:
        logger.log_error(type(exc).__name__, str(exc))
        return {"reply": _UNAVAILABLE_REPLY, "suggested_section": None}

    # 7. Log successful call -------------------------------------------------
    usage = response.usage
    if usage:
        logger.log_llm_call(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )

    # 8. Parse and return the response ---------------------------------------
    raw_text = response.choices[0].message.content or ""

    # Strip markdown code fences if the model wraps the JSON
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Drop the opening fence line (```json or ```)
        lines = lines[1:] if lines[0].startswith("```") else lines
        # Drop the closing fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        parsed = json.loads(stripped)
        reply_text = _strip_html(str(parsed.get("reply", "")))
        return {
            "reply": reply_text,
            "suggested_section": parsed.get("suggested_section") or None,
        }
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.log_error("JSONDecodeError", f"Failed to parse LLM response: {exc}")
        # Fall back to the raw text — still strip any HTML before returning
        return {"reply": _strip_html(raw_text.strip()), "suggested_section": None}


# ---------------------------------------------------------------------------
# Shared message builder (used by both streaming and non-streaming paths)
# ---------------------------------------------------------------------------

def _build_messages(message: str, history: list[dict]) -> tuple[list[dict], str]:
    """Build the OpenAI messages array and return (messages, system_prompt).

    Shared between get_assistant_reply() and stream_assistant_reply() so
    both paths use identical RAG retrieval and prompt construction.
    """
    # Build RAG query
    words = _re.findall(r"[a-z0-9]+", message.lower())
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    rag_query = " ".join(keywords) if keywords else message

    context = ""
    try:
        records = retrieve(rag_query)
        if not records and rag_query != message:
            records = retrieve(message)
        if records:
            raw_context = "\n\n".join(record.content for record in records)
            context = token_budget.truncate_context(raw_context, 2000)
    except RAGError as exc:
        logger.log_error("RAGError", str(exc))

    user_ctx = UserContext.guest()
    system_prompt = PromptFactory.get_prompt(
        feature_id="assistant",
        context=context,
        user=user_ctx,
    )

    recent_history = history[-10:] if len(history) > 10 else history
    messages = (
        recent_history
        + [{"role": "system", "content": system_prompt}]
        + [{"role": "user", "content": message}]
    )
    return messages, system_prompt


# ---------------------------------------------------------------------------
# Streaming public API
# ---------------------------------------------------------------------------

def stream_assistant_reply(
    message: str, history: list[dict]
) -> Generator[str, None, None]:
    """Stream the assistant reply token-by-token.

    Yields raw text chunks as they arrive from the OpenAI streaming API.
    The LLM is instructed to respond in plain Markdown (not JSON) when
    streaming, since we can't parse partial JSON mid-stream.

    The caller (FastAPI route) wraps this in a StreamingResponse.

    Args:
        message: The user's current message.
        history: Conversation history (last 10 items).

    Yields:
        str chunks of the reply as they arrive.
    """
    messages, _ = _build_messages(message, history)

    # For streaming we swap the format instruction to plain Markdown
    # (no JSON wrapper) so the frontend can render chunks directly.
    # We patch the last system message to remove the JSON requirement.
    for i, msg in enumerate(messages):
        if msg["role"] == "system":
            content = msg["content"]
            # Replace the JSON output rule with a plain Markdown instruction
            content = _re.sub(
                r"\*\*CRITICAL OUTPUT RULES\*\*.*",
                (
                    "**Output format**: Respond in plain Markdown. "
                    "Do NOT wrap your response in JSON. "
                    "Do NOT use HTML tags. "
                    "Use bold, bullets, and line breaks freely."
                ),
                content,
                flags=_re.DOTALL,
            )
            messages[i] = {**msg, "content": content}
            break

    try:
        stream = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=messages,
            stream=True,
        )
        full_text = ""
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                text = delta.content
                full_text += text
                yield text

        # Log after stream completes (usage not available mid-stream)
        logger.log_llm_call(
            prompt_tokens=0,   # not available in streaming mode
            completion_tokens=0,
            total_tokens=0,
        )

    except openai.OpenAIError as exc:
        logger.log_error(type(exc).__name__, str(exc))
        yield _UNAVAILABLE_REPLY
