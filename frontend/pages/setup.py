# frontend/pages/setup.py
# ─────────────────────────────────────────────────────────────────────────────
# Setup Guide page.
# The user selects their tank size and experience level.
# The backend retrieves beginner-friendly fish, plants, and aquascaping ideas
# from the knowledge base and formats them with the LLM.
# Displays: fish recommendations, plant recommendations, and an aquascaping idea.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

# Add project root to path so frontend.app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post   # Shared POST helper

# ── Page title ────────────────────────────────────────────────────────────────
st.title("🌱 Setup Guide")
st.markdown("Get personalized recommendations for setting up your new aquarium.")

# ── Input form ────────────────────────────────────────────────────────────────
with st.form("setup_form"):
    # Tank size capped at 500 gallons (the backend validates this too)
    tank_gallons = st.number_input(
        "Tank Size (gallons)", min_value=1.0, max_value=500.0, value=20.0, step=1.0
    )

    # Dropdown for experience level — maps directly to the backend's validation pattern
    experience_level = st.selectbox(
        "Experience Level", ["beginner", "intermediate", "advanced"]
    )
    submitted = st.form_submit_button("Get Recommendations")

# ── Handle submission ─────────────────────────────────────────────────────────
if submitted:
    with st.spinner("Loading..."):
        # POST to /setup; backend returns fish_recommendations, plant_recommendations,
        # and aquascaping_idea
        result = backend_post("/setup", {
            "tank_gallons": tank_gallons,
            "experience_level": experience_level
        })

    if result:
        # If only a 'message' key is present, no matching records were found
        if "message" in result and len(result) == 1:
            st.info(result["message"])
        else:
            # ── Fish Recommendations ──────────────────────────────────────
            st.subheader("Fish Recommendations")
            # Each item is a dict: {name, difficulty, min_tank_gallons}
            for fish in result.get("fish_recommendations", []):
                st.markdown(
                    f"- **{fish['name']}** — "
                    f"Difficulty: {fish['difficulty']}, "
                    f"Min tank: {fish['min_tank_gallons']} gal"
                )

            # ── Plant Recommendations ─────────────────────────────────────
            st.subheader("Plant Recommendations")
            # Each item is a dict: {name, difficulty}
            for plant in result.get("plant_recommendations", []):
                st.markdown(f"- **{plant['name']}** — Difficulty: {plant['difficulty']}")

            # ── Aquascaping Idea ──────────────────────────────────────────
            st.subheader("Aquascaping Idea")
            aq = result.get("aquascaping_idea", {})   # Dict: substrate, hardscape, plant_zones
            st.markdown(f"**Substrate:** {aq.get('substrate', 'N/A')}")
            st.markdown(f"**Hardscape:** {aq.get('hardscape', 'N/A')}")
            st.markdown("**Plant Zones:**")
            for zone in aq.get("plant_zones", []):   # List of zone description strings
                st.markdown(f"  - {zone}")
