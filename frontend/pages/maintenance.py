# frontend/pages/maintenance.py
# ─────────────────────────────────────────────────────────────────────────────
# Maintenance Guide page.
# The user provides their tank size, fish count, and species list.
# The backend retrieves nitrogen cycle and maintenance data from the knowledge
# base and uses the LLM to generate a personalised schedule.
# Displays: nitrogen cycle explanation, feeding schedule, weekly tasks,
# and monthly tasks.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

# Add project root to path so frontend.app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post   # Shared POST helper

# ── Page title ────────────────────────────────────────────────────────────────
st.title("🔧 Maintenance Guide")
st.markdown("Get a personalized maintenance schedule for your aquarium.")

# ── Input form ────────────────────────────────────────────────────────────────
with st.form("maintenance_form"):
    # Tank size in gallons — minimum 1 gallon
    tank_gallons = st.number_input("Tank Size (gallons)", min_value=1.0, value=20.0, step=1.0)

    # Number of fish — can be 0 (empty tank planning)
    fish_count = st.number_input("Number of Fish", min_value=0, value=5, step=1)

    # Multi-line text area: one species name per line
    fish_species_input = st.text_area(
        "Fish Species (one per line)",
        placeholder="Guppy\nNeon Tetra\nCorydoras"
    )
    submitted = st.form_submit_button("Get Guide")

# ── Handle submission ─────────────────────────────────────────────────────────
if submitted:
    # Parse the text area into a list, stripping blank lines and whitespace
    fish_species = [s.strip() for s in fish_species_input.strip().split("\n") if s.strip()]

    with st.spinner("Loading..."):
        # POST to /maintenance; backend returns nitrogen_cycle, feeding, weekly_tasks, monthly_tasks
        result = backend_post("/maintenance", {
            "tank_gallons": tank_gallons,
            "fish_count": int(fish_count),   # cast to int (number_input returns float)
            "fish_species": fish_species
        })

    if result:
        # If the backend returned only a 'message' key, it means no data was found
        if "message" in result and len(result) == 1:
            st.info(result["message"])   # Show as an informational banner, not an error
        else:
            # ── Nitrogen Cycle ────────────────────────────────────────────
            #st.subheader("Nitrogen Cycle")
            #st.write(result.get("nitrogen_cycle", "N/A"))   # Long text block

            # ── Feeding Schedule ──────────────────────────────────────────
            st.subheader("Feeding Schedule")
            feeding = result.get("feeding", {})   # Dict with 'quantity' and 'frequency'
            st.markdown(f"**Quantity:** {feeding.get('quantity', 'N/A')}")
            st.markdown(f"**Frequency:** {feeding.get('frequency', 'N/A')}")

            # ── Weekly Tasks ──────────────────────────────────────────────
            st.subheader("Weekly Tasks")
            for task in result.get("weekly_tasks", []):   # Iterate the list of task strings
                st.markdown(f"- {task}")   # Render each as a bullet point

            # ── Monthly Tasks ─────────────────────────────────────────────
            st.subheader("Monthly Tasks")
            for task in result.get("monthly_tasks", []):
                st.markdown(f"- {task}")
