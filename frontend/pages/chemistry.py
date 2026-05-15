# frontend/pages/chemistry.py
# ─────────────────────────────────────────────────────────────────────────────
# Chemistry Analyzer page — with progressive section reveal.
# Image bytes are cached in session_state (outside the form) to survive
# the Streamlit rerun on form submit.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import base64
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post, reveal

st.title("🧪 Chemistry Analyzer")
st.markdown(
    "Describe your water test results **or** upload a test strip image — or both. "
    "Natural language is fine: *'my water is cloudy and pH seems high'*."
)

# ── Session state for image bytes ─────────────────────────────────────────────
if "chem_image_bytes" not in st.session_state:
    st.session_state.chem_image_bytes = None
if "chem_image_name" not in st.session_state:
    st.session_state.chem_image_name = None

# ── Image uploader — OUTSIDE the form ────────────────────────────────────────
image_file = st.file_uploader(
    "Upload Test Strip Image (optional)", type=["jpg", "jpeg", "png"],
    key="chem_uploader",
)

if image_file is not None:
    st.session_state.chem_image_bytes = image_file.read()
    st.session_state.chem_image_name  = image_file.name
    st.image(st.session_state.chem_image_bytes, caption=f"📸 {image_file.name}", use_column_width=True)
elif st.session_state.chem_image_bytes is not None:
    st.image(st.session_state.chem_image_bytes,
             caption=f"📸 {st.session_state.chem_image_name} (cached)", use_column_width=True)

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

if st.session_state.chem_image_bytes is not None:
    if st.button("🗑️ Clear Image"):
        st.session_state.chem_image_bytes = None
        st.session_state.chem_image_name  = None
        st.rerun()

if submitted:
    has_text  = bool(description.strip())
    has_image = st.session_state.chem_image_bytes is not None

    if not has_text and not has_image:
        st.warning("Please enter a water description or upload a test strip image.")
    else:
        image_base64 = None
        if has_image:
            image_base64 = base64.b64encode(st.session_state.chem_image_bytes).decode("utf-8")

        with st.spinner("Analyzing water chemistry..."):
            result = backend_post("/chemistry", {
                "description":  description,
                "image_base64": image_base64,
            })

        if result:
            if "error_type" in result:
                st.warning(result.get("message", "An error occurred."))
            else:
                reveal(lambda: st.subheader("Parameter Analysis"), delay=0.08)

                for param in result.get("parameters", []):
                    p = param
                    status = p.get("status", "unknown")
                    color  = {"safe": "🟢", "caution": "🟡", "danger": "🔴"}.get(status, "⚪")

                    reveal(
                        lambda p=p, color=color, status=status: st.markdown(
                            f"{color} **{p.get('name', 'N/A')}**: "
                            f"{p.get('value', 'N/A')} — {status.capitalize()}"
                        ),
                        delay=0.09,
                    )
                    if p.get("science"):
                        reveal(lambda p=p: st.markdown(f"  *{p['science']}*"), delay=0.05)
                    if p.get("corrective_action"):
                        reveal(
                            lambda p=p: st.markdown(f"  → **Action:** {p['corrective_action']}"),
                            delay=0.05,
                        )

                if result.get("critical_interactions"):
                    reveal(
                        lambda: st.error(f"⚠️ **Critical Interaction:** {result['critical_interactions']}"),
                        delay=0.08,
                    )

                reveal(lambda: st.subheader("Summary"), delay=0.10)
                reveal(lambda: st.markdown(result.get("summary", "N/A")), delay=0.08)
