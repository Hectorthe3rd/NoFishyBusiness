# frontend/pages/assistant.py
# ─────────────────────────────────────────────────────────────────────────────
# AI Assistant page — real-time streaming chat.
#
# Uses the /assistant/stream endpoint which returns a text/plain streaming
# response. st.write_stream() consumes the chunks and renders them word-by-word
# as they arrive from the OpenAI API, giving the user live feedback that the
# system is working.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import requests
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import BACKEND_URL

st.title("🤖 AI Assistant")
st.markdown("Ask any aquarium-related question and get AI-powered answers grounded in the knowledge base.")

# ── Session state ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ── Render existing conversation ──────────────────────────────────────────────
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────────────
user_message = st.chat_input("Ask an aquarium question...")

# ── Handle new message ────────────────────────────────────────────────────────
if user_message:
    # Show user message immediately
    with st.chat_message("user"):
        st.markdown(user_message)

    st.session_state.history.append({"role": "user", "content": user_message})

    # Stream the assistant reply word-by-word
    with st.chat_message("assistant"):
        reply_placeholder = st.empty()
        full_reply = ""

        try:
            with requests.post(
                f"{BACKEND_URL}/assistant/stream",
                json={
                    "message": user_message,
                    "history": st.session_state.history[-10:],
                },
                stream=True,
                timeout=60,
            ) as resp:
                if resp.ok:
                    for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
                        if chunk:
                            full_reply += chunk
                            # Update the placeholder with accumulated text + cursor
                            reply_placeholder.markdown(full_reply + "▌")

                    # Final render without cursor
                    reply_placeholder.markdown(full_reply)
                else:
                    try:
                        err = resp.json()
                        reply_placeholder.error(f"Error: {err.get('message', 'Unknown error')}")
                    except Exception:
                        reply_placeholder.error("An unexpected error occurred. Please try again.")
                    full_reply = ""

        except requests.RequestException:
            reply_placeholder.error("Could not reach the backend. Please ensure it is running.")
            full_reply = ""
        except Exception:
            reply_placeholder.error("The result could not be displayed. Please retry.")
            full_reply = ""

    # Save to history and trim
    if full_reply:
        st.session_state.history.append({"role": "assistant", "content": full_reply})
        st.session_state.history = st.session_state.history[-10:]
