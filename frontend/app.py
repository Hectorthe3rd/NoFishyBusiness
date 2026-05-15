# frontend/app.py
# ─────────────────────────────────────────────────────────────────────────────
# Entry point for the Streamlit frontend.
# Defines shared helpers used by every tool page, sets up the sidebar
# navigation, and renders the home/welcome screen.
# ─────────────────────────────────────────────────────────────────────────────

import time   # used by the progressive reveal helper

import streamlit as st   # Streamlit — the UI framework that renders the web app
import requests          # HTTP library used to call the FastAPI backend

# Base URL of the FastAPI backend. All tool pages POST to endpoints under this.
BACKEND_URL = "http://localhost:8000"


# ─────────────────────────────────────────────────────────────────────────────
# Shared error-handling helpers
# ─────────────────────────────────────────────────────────────────────────────

def handle_backend_response(resp):
    """
    Inspect an HTTP response from the backend and return its JSON body,
    or display an error message and return None.

    - If the response is 2xx (ok), parse and return the JSON dict.
    - If the response is 4xx/5xx, try to read the 'message' field from the
      JSON body and show it as a red error banner.
    - If the body can't be parsed at all, show a generic fallback message.
    """
    if resp.ok:
        # Success — parse the JSON and hand it back to the caller
        return resp.json()
    else:
        try:
            # Try to extract the structured error message the backend sends
            err = resp.json()
            st.error(f"Error: {err['message']}")   # Show the human-readable message
        except Exception:
            # Body wasn't valid JSON — show a generic message instead
            st.error("An unexpected error occurred. Please try again.")
        return None   # Signal to the caller that there's no usable data


def backend_post(endpoint, payload):
    """
    POST JSON data to a backend endpoint and return the parsed response.

    Wraps handle_backend_response and adds two extra error layers:
    - requests.RequestException: the backend server isn't reachable at all
      (e.g. it hasn't been started yet).
    - Any other Exception: something went wrong rendering the result.

    Args:
        endpoint: URL path, e.g. "/species"
        payload:  Python dict that will be serialised to JSON

    Returns:
        Parsed JSON dict on success, or None on any error.
    """
    try:
        # Send the POST request with a 30-second timeout
        resp = requests.post(
            f"{BACKEND_URL}{endpoint}", json=payload, timeout=30
        )
        # Delegate success/error handling to the helper above
        return handle_backend_response(resp)
    except requests.RequestException:
        # Backend is not running or network is unavailable
        st.error("Could not reach the backend. Please ensure it is running.")
        return None
    except Exception:
        # Catch-all for unexpected rendering errors
        st.error("The result could not be displayed. Please retry.")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Page-level configuration
# ─────────────────────────────────────────────────────────────────────────────

# Configure the browser tab title, favicon, and layout width
st.set_page_config(page_title="NoFishyBusiness", page_icon="🐟", layout="wide")


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar navigation
# ─────────────────────────────────────────────────────────────────────────────

# App name displayed at the top of the sidebar
st.sidebar.title("🐟 NoFishyBusiness")
st.sidebar.markdown("---")   # Horizontal divider line

# Each page_link creates a clickable nav item that loads the corresponding page
# without a full browser reload (Streamlit's built-in SPA routing)
st.sidebar.page_link("pages/volume.py",        label="📐 Volume Calculator")
st.sidebar.page_link("pages/species.py",       label="🐠 Species Tool")
st.sidebar.page_link("pages/maintenance.py",   label="🔧 Maintenance Guide")
st.sidebar.page_link("pages/setup.py",         label="🌱 Setup Guide")
st.sidebar.page_link("pages/chemistry.py",     label="🧪 Chemistry Analyzer")
st.sidebar.page_link("pages/image_scanner.py", label="📷 Image Scanner")
st.sidebar.page_link("pages/assistant.py",     label="🤖 AI Assistant")


# ─────────────────────────────────────────────────────────────────────────────
# Home page content
# ─────────────────────────────────────────────────────────────────────────────

# Main heading shown when the user first opens the app
st.title("Welcome to NoFishyBusiness 🐟")

# Brief description and tool list rendered as Markdown
st.markdown("""
Your AI-powered aquarium companion. Select a tool from the sidebar to get started.

**Available Tools:**
- **Volume Calculator** — Compute tank water volume and weight
- **Species Tool** — Look up fish care sheets
- **Maintenance Guide** — Get nitrogen cycle and maintenance advice
- **Setup Guide** — Get beginner-friendly tank setup recommendations
- **Chemistry Analyzer** — Analyze water test results
- **Image Scanner** — Identify fish and plants from photos
- **AI Assistant** — Ask free-form aquarium questions
""")


# ─────────────────────────────────────────────────────────────────────────────
# Progressive reveal helper
# ─────────────────────────────────────────────────────────────────────────────

def reveal(render_fn, delay: float = 0.06):
    """
    Call render_fn() after a short delay so sections appear one at a time.

    Used by structured-data pages (Species, Maintenance, Setup, Chemistry,
    Image Scanner) to progressively reveal each section rather than having
    everything pop up simultaneously.

    Args:
        render_fn: A zero-argument callable that renders one UI section.
        delay:     Seconds to wait before rendering. Default 0.06s (60 ms).
    """
    time.sleep(delay)
    render_fn()
