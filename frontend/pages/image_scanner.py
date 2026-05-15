# frontend/pages/image_scanner.py
# ─────────────────────────────────────────────────────────────────────────────
# Image Scanner page — with progressive section reveal.
# The full Biological Report is rendered section-by-section with short delays.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import requests
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import BACKEND_URL, reveal

st.title("📷 Image Scanner")
st.markdown("Upload a photo of a fish or plant to get a full biological report.")

uploaded_file = st.file_uploader(
    "Upload Image (JPEG or PNG, max 10 MB)", type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

    if st.button("Scan Image"):
        with st.spinner("Generating biological report..."):
            try:
                file_bytes = uploaded_file.getvalue()
                files = {"file": (uploaded_file.name, file_bytes, uploaded_file.type)}
                resp  = requests.post(f"{BACKEND_URL}/image-scan", files=files, timeout=60)

                if resp.ok:
                    result = resp.json()

                    if result.get("report"):
                        # Split the Markdown report on section headers (##) and
                        # reveal each section progressively.
                        import re
                        sections = re.split(r"(?=^## )", result["report"], flags=re.MULTILINE)
                        for section in sections:
                            s = section.strip()
                            if s:
                                reveal(lambda s=s: st.markdown(s), delay=0.12)
                    else:
                        # Fallback structured display
                        species    = result.get("species_name")
                        confidence = result.get("confidence", "inconclusive")
                        conf_pct   = result.get("confidence_pct")

                        reveal(lambda: st.subheader("Identification Results"), delay=0.08)
                        if species:
                            conf_label = confidence.capitalize()
                            if conf_pct is not None:
                                conf_label += f" ({conf_pct}%)"
                            reveal(lambda: st.markdown(f"**Species:** {species}"), delay=0.07)
                            if result.get("scientific_name"):
                                reveal(lambda: st.caption(f"*{result['scientific_name']}*"), delay=0.04)
                            reveal(lambda: st.markdown(f"**Confidence:** {conf_label}"), delay=0.07)
                        else:
                            reveal(lambda: st.markdown("**Species:** Could not be identified"), delay=0.07)

                        reveal(lambda: st.subheader("Care Summary"), delay=0.10)
                        reveal(lambda: st.markdown(result.get("care_summary", "N/A")), delay=0.08)

                        reveal(lambda: st.subheader("Health Assessment"), delay=0.10)
                        health = result.get("health_assessment", {})
                        reveal(lambda: st.markdown(f"**Status:** {health.get('status', 'N/A')}"), delay=0.07)
                        issues = health.get("issues_detected")
                        if issues:
                            reveal(lambda: st.markdown("**Issues Detected:**"), delay=0.06)
                            for issue in issues:
                                i = issue
                                reveal(lambda i=i: st.markdown(f"- {i}"), delay=0.06)
                        else:
                            reveal(lambda: st.markdown("**Issues Detected:** None"), delay=0.06)

                        if health.get("recommended_action"):
                            reveal(
                                lambda: st.markdown(f"**Recommended Action:** {health['recommended_action']}"),
                                delay=0.07,
                            )

                    if result.get("captivity_note"):
                        reveal(lambda: st.warning(f"⚠️ {result['captivity_note']}"), delay=0.08)

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
