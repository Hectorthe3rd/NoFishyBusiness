# frontend/pages/species.py
# ─────────────────────────────────────────────────────────────────────────────
# Species Tool page.
# Supports partial names, misspellings, and abbreviations — the backend
# resolves them via an LLM name resolver before querying the knowledge base.
# Shows a "Did you mean X?" hint when the input was fuzzy-matched.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post

st.title("🐠 Species Tool")
st.markdown("Look up care information for any freshwater aquarium fish. Partial names and misspellings are OK.")

with st.form("species_form"):
    species_name = st.text_input(
        "Fish Species Name",
        placeholder="e.g., Guppy, Betta, neon, tetra, bata fish..."
    )
    submitted = st.form_submit_button("Look Up")

if submitted and species_name:
    with st.spinner("Looking up species..."):
        result = backend_post("/species", {"species_name": species_name})

    if result:
        # Show fuzzy-match hint if the backend resolved the name
        if result.get("did_you_mean"):
            st.info(
                f"💡 Did you mean **{result['did_you_mean']}**? "
                "Showing info for that species."
            )

        st.subheader(f"Care Sheet: {result.get('species_name', species_name)}")

        if result.get("scientific_name"):
            st.caption(f"*{result['scientific_name']}*")

        st.markdown(f"**Behavior:** {result.get('behavior', 'N/A')}")

        mates = result.get('compatible_tank_mates', [])
        st.markdown(f"**Compatible Tank Mates:** {', '.join(mates) if mates else 'N/A'}")

        temp = result.get('temperature_f', {})
        st.markdown(f"**Temperature:** {temp.get('min', 'N/A')}–{temp.get('max', 'N/A')} °F")

        ph = result.get('ph', {})
        st.markdown(f"**pH:** {ph.get('min', 'N/A')}–{ph.get('max', 'N/A')}")

        hardness = result.get('hardness_dgh', {})
        st.markdown(f"**Hardness:** {hardness.get('min', 'N/A')}–{hardness.get('max', 'N/A')} dGH")

        st.markdown(f"**Minimum Tank Size:** {result.get('min_tank_gallons', 'N/A')} gallons")
        st.markdown(f"**Difficulty:** {str(result.get('difficulty', 'N/A')).capitalize()}")
        st.markdown(f"**Maintenance Notes:** {result.get('maintenance_notes', 'N/A')}")
