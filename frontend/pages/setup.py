# frontend/pages/setup.py
# ─────────────────────────────────────────────────────────────────────────────
# Setup Guide page.
# Supports gallons and liters, tank sizes up to 2000 gallons (pond mode),
# and a challenge level dropdown.
# Plant zones now include educational tooltips explaining placement rationale.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post

st.title("🌱 Setup Guide")
st.markdown("Get personalized recommendations for setting up your new aquarium or pond.")

with st.form("setup_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        tank_size = st.number_input(
            "Tank / Pond Size", min_value=1.0, max_value=2000.0, value=20.0, step=1.0
        )
    with col2:
        unit = st.selectbox("Unit", ["gallons", "liters"], index=0)

    # Show pond hint when size is large
    if tank_size > 500 and unit == "gallons":
        st.info("🏞️ Tanks over 500 gallons will receive **Pond / Outdoor** recommendations.")
    elif tank_size > 1893 and unit == "liters":  # ~500 gal in liters
        st.info("🏞️ Large volumes will receive **Pond / Outdoor** recommendations.")

    experience_level = st.selectbox(
        "Experience Level",
        ["beginner", "intermediate", "advanced"],
        help="Your overall fishkeeping experience.",
    )

    challenge_level = st.selectbox(
        "Challenge Level",
        ["basic", "intermediate", "advanced"],
        index=1,
        help=(
            "Basic = low-maintenance / Zen setup. "
            "Advanced = high-tech CO2, demanding species. "
            "Mix with experience level for interesting combos!"
        ),
    )

    submitted = st.form_submit_button("Get Recommendations")

if submitted:
    with st.spinner("Generating setup guide..."):
        result = backend_post("/setup", {
            "tank_gallons":    tank_size,
            "experience_level": experience_level,
            "unit":            unit,
            "challenge_level": challenge_level,
        })

    if result:
        if "message" in result and len(result) == 1:
            st.info(result["message"])
        else:
            # Theme badge
            if result.get("theme"):
                st.markdown(f"### 🎨 Theme: {result['theme']}")

            # ── Fish Recommendations ──────────────────────────────────────
            st.subheader("Fish Recommendations")
            for fish in result.get("fish_recommendations", []):
                why = f" — *{fish['why']}*" if fish.get("why") else ""
                st.markdown(
                    f"- **{fish['name']}** — "
                    f"Difficulty: {fish['difficulty']}, "
                    f"Min tank: {fish['min_tank_gallons']} gal"
                    f"{why}"
                )

            # ── Plant Recommendations ─────────────────────────────────────
            st.subheader("Plant Recommendations")
            for plant in result.get("plant_recommendations", []):
                why = f" — *{plant['why']}*" if plant.get("why") else ""
                st.markdown(f"- **{plant['name']}** — Difficulty: {plant['difficulty']}{why}")

            # ── Aquascaping Idea ──────────────────────────────────────────
            st.subheader("Aquascaping Idea")
            aq = result.get("aquascaping_idea", {})
            st.markdown(f"**Substrate:** {aq.get('substrate', 'N/A')}")
            st.markdown(f"**Hardscape:** {aq.get('hardscape', 'N/A')}")

            # Plant zones with educational tooltips
            plant_zones = aq.get("plant_zones", [])
            if plant_zones:
                st.markdown("**Plant Zones:**")
                for zone in plant_zones:
                    if isinstance(zone, dict):
                        zone_label = zone.get("zone", "")
                        plant_name = zone.get("plant", "")
                        reason     = zone.get("reason", "")
                        st.markdown(f"  - **{zone_label}**: {plant_name}")
                        if reason:
                            st.caption(f"    💡 {reason}")
                    else:
                        # Fallback for plain string zones
                        st.markdown(f"  - {zone}")

            if aq.get("pro_tip"):
                st.info(f"💡 **Pro Tip:** {aq['pro_tip']}")
