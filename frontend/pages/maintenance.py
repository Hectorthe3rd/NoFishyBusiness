# frontend/pages/maintenance.py
# ─────────────────────────────────────────────────────────────────────────────
# Maintenance Guide page — with progressive section reveal.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post, reveal

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
            # Incompatibility warning — highest priority, shown first
            if result.get("incompatibility_warning"):
                reveal(lambda: st.error(result["incompatibility_warning"]), delay=0.05)

            # Bioload rating
            bioload = result.get("bioload_rating", "")
            if bioload:
                badge = {"low": "🟢 Low", "medium": "🟡 Medium", "high": "🔴 High"}.get(bioload, bioload)
                reveal(lambda: st.markdown(f"**Bioload Rating:** {badge}"), delay=0.08)
                if result.get("bioload_note"):
                    reveal(lambda: st.caption(result["bioload_note"]), delay=0.04)

            # Feeding schedule
            reveal(lambda: st.subheader("Feeding Schedule"), delay=0.10)
            feeding = result.get("feeding", {})
            reveal(lambda: st.markdown(f"**Quantity:** {feeding.get('quantity', 'N/A')}"), delay=0.08)
            reveal(lambda: st.markdown(f"**Frequency:** {feeding.get('frequency', 'N/A')}"), delay=0.06)

            # Weekly tasks — each task revealed individually
            reveal(lambda: st.subheader("Weekly Tasks"), delay=0.10)
            for task in result.get("weekly_tasks", []):
                t = task  # capture loop variable
                reveal(lambda t=t: st.markdown(f"- {t}"), delay=0.07)

            # Monthly tasks
            reveal(lambda: st.subheader("Monthly Tasks"), delay=0.10)
            for task in result.get("monthly_tasks", []):
                t = task
                reveal(lambda t=t: st.markdown(f"- {t}"), delay=0.07)

            # Additional advice
            if result.get("advice"):
                reveal(lambda: st.subheader("Additional Advice"), delay=0.10)
                reveal(lambda: st.markdown(result["advice"]), delay=0.08)
