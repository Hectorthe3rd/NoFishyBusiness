# frontend/pages/image_scanner.py
# ─────────────────────────────────────────────────────────────────────────────
# Image Scanner page.
# The user uploads a JPEG or PNG photo of a fish or plant.
# The backend sends it to the OpenAI vision API (gpt-4o-mini) which identifies
# the species and assesses visible health indicators.
# Displays: species name, confidence level, care summary, health assessment.
#
# Note: this page uses requests.post directly (not backend_post) because the
# image must be sent as multipart/form-data, not JSON.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import requests   # Used directly for multipart file upload
import sys, os

# Add project root to path so frontend.app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import BACKEND_URL   # Base URL constant (http://localhost:8000)

# ── Page title ────────────────────────────────────────────────────────────────
st.title("📷 Image Scanner")
st.markdown("Upload a photo of a fish or plant to identify the species and assess its health.")

# ── File uploader ─────────────────────────────────────────────────────────────
# Accepts JPEG and PNG; the backend enforces the 10 MB size limit
uploaded_file = st.file_uploader(
    "Upload Image (JPEG or PNG, max 10 MB)", type=["jpg", "jpeg", "png"]
)

# Only show the scan button once a file has been selected
if uploaded_file is not None:
    # Preview the uploaded image in the UI before scanning
    st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

    if st.button("Scan Image"):
        with st.spinner("Loading..."):
            try:
                # Read the raw bytes from the uploaded file object
                file_bytes = uploaded_file.getvalue()

                # Build a multipart/form-data payload — the backend expects a
                # field named "file" with the filename and MIME type
                files = {"file": (uploaded_file.name, file_bytes, uploaded_file.type)}

                # POST to /image-scan with a longer timeout (vision API can be slow)
                resp = requests.post(f"{BACKEND_URL}/image-scan", files=files, timeout=60)

                if resp.ok:
                    result = resp.json()   # Parse the JSON response body

                    # ── Identification Results ────────────────────────────
                    st.subheader("Identification Results")
                    species    = result.get("species_name")   # May be None if inconclusive
                    confidence = result.get("confidence", "inconclusive")

                    if species:
                        # Species was identified — show name and confidence
                        st.markdown(f"**Species:** {species}")
                        st.markdown(f"**Confidence:** {confidence.capitalize()}")
                    else:
                        # Vision API couldn't identify the species
                        st.markdown("**Species:** Could not be identified (inconclusive)")

                    # ── Care Summary ──────────────────────────────────────
                    st.subheader("Care Summary")
                    st.write(result.get("care_summary", "N/A"))

                    # ── Health Assessment ─────────────────────────────────
                    st.subheader("Health Assessment")
                    health = result.get("health_assessment", {})
                    st.markdown(f"**Status:** {health.get('status', 'N/A')}")

                    issues = health.get("issues_detected")   # List or None
                    if issues:
                        st.markdown("**Issues Detected:**")
                        for issue in issues:
                            st.markdown(f"- {issue}")
                    else:
                        st.markdown("**Issues Detected:** None")

                else:
                    # HTTP error — try to show the backend's message field
                    try:
                        err = resp.json()
                        st.error(f"Error: {err.get('message', 'Unknown error')}")
                    except Exception:
                        st.error("An unexpected error occurred. Please try again.")

            except requests.RequestException:
                # Backend is not reachable
                st.error("Could not reach the backend. Please ensure it is running.")
            except Exception:
                # Catch-all for unexpected rendering errors
                st.error("The result could not be displayed. Please retry.")
