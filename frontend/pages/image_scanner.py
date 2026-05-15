# frontend/pages/image_scanner.py
# ─────────────────────────────────────────────────────────────────────────────
# Image Scanner page.
# Renders the full Biological Report returned by the backend as Markdown.
# The report includes: Identification Results, Reasoning, Species Description,
# Care Summary (with Requirements Table), Health Assessment, and Action Plan.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import requests
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import BACKEND_URL

st.title("📷 Image Scanner")
st.markdown("Upload a photo of a fish or plant to get a full biological report.")

uploaded_file = st.file_uploader(
    "Upload Image (JPEG or PNG, max 10 MB)", type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    # Live preview
    st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

    if st.button("Scan Image"):
        with st.spinner("Generating biological report..."):
            try:
                file_bytes = uploaded_file.getvalue()
                files = {"file": (uploaded_file.name, file_bytes, uploaded_file.type)}
                resp  = requests.post(f"{BACKEND_URL}/image-scan", files=files, timeout=60)

                if resp.ok:
                    result = resp.json()

                    # ── Full Biological Report (Markdown) ─────────────────
                    if result.get("report"):
                        st.markdown(result["report"])
                    else:
                        # Fallback to structured display if report field missing
                        st.subheader("Identification Results")
                        species    = result.get("species_name")
                        confidence = result.get("confidence", "inconclusive")
                        conf_pct   = result.get("confidence_pct")

                        if species:
                            conf_label = f"{confidence.capitalize()}"
                            if conf_pct is not None:
                                conf_label += f" ({conf_pct}%)"
                            st.markdown(f"**Species:** {species}")
                            if result.get("scientific_name"):
                                st.caption(f"*{result['scientific_name']}*")
                            st.markdown(f"**Confidence:** {conf_label}")
                        else:
                            st.markdown("**Species:** Could not be identified (inconclusive)")

                        st.subheader("Care Summary")
                        st.markdown(result.get("care_summary", "N/A"))

                        st.subheader("Health Assessment")
                        health = result.get("health_assessment", {})
                        st.markdown(f"**Status:** {health.get('status', 'N/A')}")
                        issues = health.get("issues_detected")
                        if issues:
                            st.markdown("**Issues Detected:**")
                            for issue in issues:
                                st.markdown(f"- {issue}")
                        else:
                            st.markdown("**Issues Detected:** None")

                        if health.get("recommended_action"):
                            st.markdown(f"**Recommended Action:** {health['recommended_action']}")

                    # Captivity note (shown as a warning if present)
                    if result.get("captivity_note"):
                        st.warning(f"⚠️ {result['captivity_note']}")

                else:
                    try:
                        err = resp.json()
                        st.error(f"Error: {err.get('message', 'Unknown error')}")
                    except Exception:
                        st.error("An unexpected error occurred. Please try again.")

            except requests.RequestException:
                st.error("Could not reach the backend. Please ensure it is running.")
            except Exception:
                st.error("The result could not be displayed. Please retry.")
