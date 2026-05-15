# frontend/pages/chemistry.py
# ─────────────────────────────────────────────────────────────────────────────
# Chemistry Analyzer page.
# Accepts natural language descriptions AND/OR a test strip image.
# Image-only mode: if no text is provided, the backend extracts parameters
# from the image automatically via vision LLM.
#
# Image handling note:
#   st.file_uploader inside st.form resets on submit, so we read the image
#   bytes immediately when the file is selected and cache them in session_state.
#   This ensures the bytes are available when the form is submitted.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import base64
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post

st.title("🧪 Chemistry Analyzer")
st.markdown(
    "Describe your water test results **or** upload a test strip image — or both. "
    "Natural language is fine: *'my water is cloudy and pH seems high'*."
)

# ── Session state for image bytes ─────────────────────────────────────────────
# We cache the raw bytes outside the form so they survive the submit rerun.
if "chem_image_bytes" not in st.session_state:
    st.session_state.chem_image_bytes = None
if "chem_image_name" not in st.session_state:
    st.session_state.chem_image_name = None

# ── Image uploader — OUTSIDE the form so bytes are readable on submit ─────────
image_file = st.file_uploader(
    "Upload Test Strip Image (optional)", type=["jpg", "jpeg", "png"],
    key="chem_uploader",
)

# Read and cache bytes immediately when a file is selected
if image_file is not None:
    st.session_state.chem_image_bytes = image_file.read()
    st.session_state.chem_image_name  = image_file.name
    # Live preview
    st.image(
        st.session_state.chem_image_bytes,
        caption=f"📸 {image_file.name}",
        use_column_width=True,
    )
elif image_file is None and st.session_state.chem_image_bytes is not None:
    # File was cleared — show the cached preview with a note
    st.image(
        st.session_state.chem_image_bytes,
        caption=f"📸 {st.session_state.chem_image_name} (cached)",
        use_column_width=True,
    )

# ── Input form ────────────────────────────────────────────────────────────────
with st.form("chemistry_form"):
    description = st.text_area(
        "Water Parameter Description (optional if uploading an image)",
        placeholder=(
            "e.g., 'ammonia is 0.5 ppm, nitrite 0.25 ppm, pH 7.2, temp 78°F'\n"
            "or just: 'my water looks cloudy and fish seem stressed'"
        ),
        height=120,
    )
    submitted = st.form_submit_button("Analyze")

# ── Clear image cache button ──────────────────────────────────────────────────
if st.session_state.chem_image_bytes is not None:
    if st.button("🗑️ Clear Image"):
        st.session_state.chem_image_bytes = None
        st.session_state.chem_image_name  = None
        st.rerun()

# ── Handle submission ─────────────────────────────────────────────────────────
if submitted:
    has_text  = bool(description.strip())
    has_image = st.session_state.chem_image_bytes is not None

    if not has_text and not has_image:
        st.warning("Please enter a water description or upload a test strip image.")
    else:
        image_base64 = None
        if has_image:
            image_base64 = base64.b64encode(
                st.session_state.chem_image_bytes
            ).decode("utf-8")

        with st.spinner("Analyzing water chemistry..."):
            result = backend_post("/chemistry", {
                "description":  description,
                "image_base64": image_base64,
            })

        if result:
            if "error_type" in result:
                st.warning(result.get("message", "An error occurred."))
            else:
                # ── Parameter Analysis ────────────────────────────────────
                st.subheader("Parameter Analysis")
                parameters = result.get("parameters", [])
                if parameters:
                    for param in parameters:
                        status = param.get("status", "unknown")
                        color  = {"safe": "🟢", "caution": "🟡", "danger": "🔴"}.get(status, "⚪")
                        st.markdown(
                            f"{color} **{param.get('name', 'N/A')}**: "
                            f"{param.get('value', 'N/A')} — {status.capitalize()}"
                        )
                        if param.get("science"):
                            st.markdown(f"  *{param['science']}*")
                        if param.get("corrective_action"):
                            st.markdown(f"  → **Action:** {param['corrective_action']}")

                # Critical interactions warning
                if result.get("critical_interactions"):
                    st.error(f"⚠️ **Critical Interaction:** {result['critical_interactions']}")

                # ── Summary ───────────────────────────────────────────────
                st.subheader("Summary")
                st.markdown(result.get("summary", "N/A"))
