# frontend/pages/chemistry.py
# ─────────────────────────────────────────────────────────────────────────────
# Chemistry Analyzer page.
# The user describes their water test results in plain text (e.g.
# "ammonia 0.5 ppm, pH 7.2") and optionally uploads a photo of a test strip.
# The backend classifies each parameter as safe / caution / danger and
# suggests corrective actions where needed.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import base64   # Used to encode the uploaded image as a base64 string for the API
import sys, os

# Add project root to path so frontend.app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post   # Shared POST helper

# ── Page title ────────────────────────────────────────────────────────────────
st.title("🧪 Chemistry Analyzer")
st.markdown("Describe your water test results to get a danger assessment and corrective actions.")

# ── Input form ────────────────────────────────────────────────────────────────
with st.form("chemistry_form"):
    # Multi-line text area for the parameter description
    description = st.text_area(
        "Water Parameter Description",
        placeholder="e.g., ammonia is 0.5 ppm, nitrite 0.25 ppm, pH 7.2, temperature 78F"
    )

    # Optional image upload — accepts JPEG and PNG test strip photos
    image_file = st.file_uploader(
        "Upload Test Strip Image (optional)", type=["jpg", "jpeg", "png"]
    )
    submitted = st.form_submit_button("Analyze")

# ── Handle submission ─────────────────────────────────────────────────────────
if submitted:
    # Convert the uploaded image to a base64 string if one was provided
    image_base64 = None
    if image_file is not None:
        image_bytes = image_file.read()   # Read raw bytes from the uploaded file
        # Encode to base64 and decode to a plain string (JSON-serialisable)
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    with st.spinner("Loading..."):
        # POST description + optional image to /chemistry
        result = backend_post("/chemistry", {
            "description": description,
            "image_base64": image_base64   # None if no image was uploaded
        })

    if result:
        # The backend may return an error_type for soft errors (no parameters found,
        # off-topic query) without using an HTTP error code
        if "error_type" in result:
            st.warning(result.get("message", "An error occurred."))
        else:
            # ── Parameter Analysis ────────────────────────────────────────
            st.subheader("Parameter Analysis")
            parameters = result.get("parameters", [])   # List of parameter dicts
            if parameters:
                for param in parameters:
                    status = param.get("status", "unknown")

                    # Map status to a colour-coded emoji for quick visual scanning
                    color = {"safe": "🟢", "caution": "🟡", "danger": "🔴"}.get(status, "⚪")

                    # One line per parameter: icon + name + value + status label
                    st.markdown(
                        f"{color} **{param.get('name', 'N/A')}**: "
                        f"{param.get('value', 'N/A')} — {status.capitalize()}"
                    )

                    # Show corrective action indented below if one was provided
                    if param.get("corrective_action"):
                        st.markdown(f"  → *{param['corrective_action']}*")

            # ── Summary ───────────────────────────────────────────────────
            st.subheader("Summary")
            st.write(result.get("summary", "N/A"))   # Overall assessment paragraph
