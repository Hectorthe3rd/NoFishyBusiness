# frontend/pages/maintenance.py
# ─────────────────────────────────────────────────────────────────────────────
# Maintenance Guide page.
# Shows a HIGH-PRIORITY WARNING banner if incompatible species are detected
# (e.g. Goldfish + Neon Tetra temperature mismatch).
# Displays species-specific monthly tasks injected by the backend.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post

st.title("🔧 Maintenance Guide")
st.markdown("Get a personalized maintenance schedule for your aquarium.")

with st.form("maintenance_form"):
    tank_gallons = st.number_input("Tank Size (gallons)", min_value=1.0, value=20.0, step=1.0)
    fish_count   = st.number_input("Number of Fish", min_value=0, value=5, step=1)
    fish_species_input = st.text_area(
        "Fish Species (one per line)",
        placeholder="Guppy\nNeon Tetra\nCorydoras"
    )
    submitted = st.form_submit_button("Get Guide")

if submitted:
    fish_species = [s.strip() for s in fish_species_input.strip().split("\n") if s.strip()]

    with st.spinner("Generating maintenance guide..."):
        result = backend_post("/maintenance", {
            "tank_gallons": tank_gallons,
            "fish_count":   int(fish_count),
            "fish_species": fish_species,
        })

    if result:
        if "message" in result and len(result) == 1:
            st.info(result["message"])
        else:
            # ── Incompatibility Warning ───────────────────────────────────
            # Shown first and prominently — this is a HIGH-PRIORITY alert
            if result.get("incompatibility_warning"):
                st.error(result["incompatibility_warning"])

            # ── Bioload Rating ────────────────────────────────────────────
            bioload = result.get("bioload_rating", "")
            if bioload:
                badge = {"low": "🟢 Low", "medium": "🟡 Medium", "high": "🔴 High"}.get(bioload, bioload)
                st.markdown(f"**Bioload Rating:** {badge}")
                if result.get("bioload_note"):
                    st.caption(result["bioload_note"])

            # ── Feeding Schedule ──────────────────────────────────────────
            st.subheader("Feeding Schedule")
            feeding = result.get("feeding", {})
            st.markdown(f"**Quantity:** {feeding.get('quantity', 'N/A')}")
            st.markdown(f"**Frequency:** {feeding.get('frequency', 'N/A')}")

            # ── Weekly Tasks ──────────────────────────────────────────────
            st.subheader("Weekly Tasks")
            for task in result.get("weekly_tasks", []):
                st.markdown(f"- {task}")

            # ── Monthly Tasks ─────────────────────────────────────────────
            st.subheader("Monthly Tasks")
            for task in result.get("monthly_tasks", []):
                st.markdown(f"- {task}")

            # ── General Advice ────────────────────────────────────────────
            if result.get("advice"):
                st.subheader("Additional Advice")
                st.markdown(result["advice"])
