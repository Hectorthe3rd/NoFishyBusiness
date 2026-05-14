# frontend/pages/species.py
# ─────────────────────────────────────────────────────────────────────────────
# Species Tool page.
# The user types a fish species name; the backend retrieves a care sheet
# from the knowledge base via RAG and formats it with the LLM.
# Displays: behavior, compatible tank mates, water parameters, tank size,
# difficulty, and maintenance notes.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

# Add project root to path so frontend.app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post   # Shared POST helper

# ── Page title ────────────────────────────────────────────────────────────────
st.title("🐠 Species Tool")
st.markdown("Look up care information for any freshwater aquarium fish.")

# ── Input form ────────────────────────────────────────────────────────────────
with st.form("species_form"):
    # Free-text input for the species name; placeholder shows example values
    species_name = st.text_input(
        "Fish Species Name",
        placeholder="e.g., Guppy, Betta, Neon Tetra"
    )
    submitted = st.form_submit_button("Look Up")

# ── Handle submission ─────────────────────────────────────────────────────────
# Only proceed if the form was submitted AND the user typed something
if submitted and species_name:
    with st.spinner("Loading..."):
        # POST the species name to /species; backend returns a structured care sheet
        result = backend_post("/species", {"species_name": species_name})

    if result:   # None means an error was already displayed by backend_post
        # Section heading uses the name returned by the LLM (may differ in casing)
        st.subheader(f"Care Sheet: {result.get('species_name', species_name)}")

        # Display each care sheet field with a bold label
        st.markdown(f"**Behavior:** {result.get('behavior', 'N/A')}")

        # compatible_tank_mates is a list — join it into a comma-separated string
        mates = result.get('compatible_tank_mates', [])
        st.markdown(f"**Compatible Tank Mates:** {', '.join(mates) if mates else 'N/A'}")

        # temperature_f, ph, hardness_dgh are dicts with 'min' and 'max' keys
        temp = result.get('temperature_f', {})
        st.markdown(f"**Temperature:** {temp.get('min', 'N/A')}–{temp.get('max', 'N/A')} °F")

        ph = result.get('ph', {})
        st.markdown(f"**pH:** {ph.get('min', 'N/A')}–{ph.get('max', 'N/A')}")

        hardness = result.get('hardness_dgh', {})
        st.markdown(f"**Hardness:** {hardness.get('min', 'N/A')}–{hardness.get('max', 'N/A')} dGH")

        # Scalar fields
        st.markdown(f"**Minimum Tank Size:** {result.get('min_tank_gallons', 'N/A')} gallons")
        st.markdown(f"**Difficulty:** {result.get('difficulty', 'N/A').capitalize()}")
        st.markdown(f"**Maintenance Notes:** {result.get('maintenance_notes', 'N/A')}")
