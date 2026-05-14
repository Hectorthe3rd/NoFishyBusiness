# frontend/pages/assistant.py
# ─────────────────────────────────────────────────────────────────────────────
# AI Assistant page.
# A chat interface where the user can ask free-form aquarium questions.
# Conversation history is stored in Streamlit's session_state so the LLM
# has context from previous messages in the same browser session.
# The backend runs topic filtering, RAG retrieval, and the OpenAI call.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

# Add project root to path so frontend.app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post   # Shared POST helper

# ── Page title ────────────────────────────────────────────────────────────────
st.title("🤖 AI Assistant")
st.markdown("Ask any aquarium-related question and get AI-powered answers grounded in the knowledge base.")

# ── Session state initialisation ──────────────────────────────────────────────
# st.session_state persists across reruns within the same browser session.
# We use it to store the conversation history so the LLM has context.
if "history" not in st.session_state:
    st.session_state.history = []   # List of {"role": "user"|"assistant", "content": str}

# ── Render existing conversation ──────────────────────────────────────────────
# Loop through all previous messages and display them in chat bubbles
for msg in st.session_state.history:
    role    = msg.get("role", "user")
    content = msg.get("content", "")
    with st.chat_message(role):   # "user" shows on the right, "assistant" on the left
        st.markdown(content)

# ── Chat input ────────────────────────────────────────────────────────────────
# st.chat_input renders a sticky input bar at the bottom of the page.
# It returns the submitted text (or None if nothing was submitted yet).
user_message = st.chat_input("Ask an aquarium question...")

# ── Handle new message ────────────────────────────────────────────────────────
if user_message:
    # Immediately display the user's message in the chat UI
    with st.chat_message("user"):
        st.markdown(user_message)

    # Add the user message to history BEFORE calling the backend so it's
    # included in the history we send (the backend uses it for context)
    st.session_state.history.append({"role": "user", "content": user_message})

    with st.spinner("Loading..."):
        # POST to /assistant with the message and the last 10 history items
        # (10 items = 5 user/assistant pairs = the spec's session memory limit)
        result = backend_post("/assistant", {
            "message": user_message,
            "history": st.session_state.history[-10:]
        })

    if result:
        reply             = result.get("reply", "")
        suggested_section = result.get("suggested_section")   # Optional app section hint

        # Display the assistant's reply in a chat bubble
        with st.chat_message("assistant"):
            st.markdown(reply)

            # If the backend suggested a relevant app section, show it as a tip
            if suggested_section:
                st.info(f"💡 Tip: Try the **{suggested_section}** for more details.")

        # Add the assistant reply to history so future messages have context
        st.session_state.history.append({"role": "assistant", "content": reply})

        # Keep only the last 10 items (5 pairs) to stay within the token budget
        st.session_state.history = st.session_state.history[-10:]
