# frontend/pages/setup.py
# ─────────────────────────────────────────────────────────────────────────────
# Setup Guide page — with progressive section reveal.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post, reveal

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

    if tank_size > 500 and unit == "gallons":
        st.info("🏞️ Tanks over 500 gallons will receive **Pond / Outdoor** recommendations.")
    elif tank_size > 1893 and unit == "liters":
        st.info("🏞️ Large volumes will receive **Pond / Outdoor** recommendations.")

    experience_level = st.selectbox(
        "Experience Level", ["beginner", "intermediate", "advanced"],
        help="Your overall fishkeeping experience.",
    )
    challenge_level = st.selectbox(
        "Challenge Level", ["basic", "intermediate", "advanced"], index=1,
        help="Basic = low-maintenance. Advanced = high-tech CO2, demanding species.",
    )
    submitted = st.form_submit_button("Get Recommendations")

if submitted:
    with st.spinner("Generating setup guide..."):
        result = backend_post("/setup", {
            "tank_gallons":     tank_size,
            "experience_level": experience_level,
            "unit":             unit,
            "challenge_level":  challenge_level,
        })

    if result:
        if "message" in result and len(result) == 1:
            st.info(result["message"])
        else:
            # Theme
            if result.get("theme"):
                reveal(lambda: st.markdown(f"### 🎨 Theme: {result['theme']}"), delay=0.08)

            # Fish recommendations
            reveal(lambda: st.subheader("Fish Recommendations"), delay=0.10)
            for fish in result.get("fish_recommendations", []):
                f = fish
                why = f" — *{f['why']}*" if f.get("why") else ""
                reveal(
                    lambda f=f, why=why: st.markdown(
                        f"- **{f['name']}** — Difficulty: {f['difficulty']}, "
                        f"Min tank: {f['min_tank_gallons']} gal{why}"
                    ),
                    delay=0.08,
                )

            # Plant recommendations
            reveal(lambda: st.subheader("Plant Recommendations"), delay=0.10)
            for plant in result.get("plant_recommendations", []):
                p = plant
                why = f" — *{p['why']}*" if p.get("why") else ""
                reveal(
                    lambda p=p, why=why: st.markdown(
                        f"- **{p['name']}** — Difficulty: {p['difficulty']}{why}"
                    ),
                    delay=0.08,
                )

            # Aquascaping idea
            reveal(lambda: st.subheader("Aquascaping Idea"), delay=0.10)
            aq = result.get("aquascaping_idea", {})
            reveal(lambda: st.markdown(f"**Substrate:** {aq.get('substrate', 'N/A')}"), delay=0.07)
            reveal(lambda: st.markdown(f"**Hardscape:** {aq.get('hardscape', 'N/A')}"), delay=0.07)

            plant_zones = aq.get("plant_zones", [])
            if plant_zones:
                reveal(lambda: st.markdown("**Plant Zones:**"), delay=0.07)
                for zone in plant_zones:
                    z = zone
                    if isinstance(z, dict):
                        reveal(
                            lambda z=z: st.markdown(
                                f"  - **{z.get('zone', '')}**: {z.get('plant', '')}"
                            ),
                            delay=0.07,
                        )
                        if z.get("reason"):
                            reveal(lambda z=z: st.caption(f"    💡 {z['reason']}"), delay=0.04)
                    else:
                        reveal(lambda z=z: st.markdown(f"  - {z}"), delay=0.07)

            if aq.get("pro_tip"):
                reveal(lambda: st.info(f"💡 **Pro Tip:** {aq['pro_tip']}"), delay=0.08)
