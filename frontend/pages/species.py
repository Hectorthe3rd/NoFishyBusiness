# frontend/pages/species.py
# ─────────────────────────────────────────────────────────────────────────────
# Species Tool page — with progressive section reveal.
# Each care sheet field appears with a short delay so the user sees the
# page building up rather than everything appearing at once.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post, reveal

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
        # Fuzzy-match hint
        if result.get("did_you_mean"):
            reveal(lambda: st.info(
                f"💡 Did you mean **{result['did_you_mean']}**? "
                "Showing info for that species."
            ))

        # Header
        reveal(lambda: st.subheader(f"Care Sheet: {result.get('species_name', species_name)}"))

        if result.get("scientific_name"):
            reveal(lambda: st.caption(f"*{result['scientific_name']}*"))

        reveal(lambda: st.markdown(f"**Behavior:** {result.get('behavior', 'N/A')}"))

        mates = result.get('compatible_tank_mates', [])
        reveal(lambda: st.markdown(
            f"**Compatible Tank Mates:** {', '.join(mates) if mates else 'N/A'}"
        ))

        temp = result.get('temperature_f', {})
        reveal(lambda: st.markdown(
            f"**Temperature:** {temp.get('min', 'N/A')}–{temp.get('max', 'N/A')} °F"
        ))

        ph = result.get('ph', {})
        reveal(lambda: st.markdown(f"**pH:** {ph.get('min', 'N/A')}–{ph.get('max', 'N/A')}"))

        hardness = result.get('hardness_dgh', {})
        reveal(lambda: st.markdown(
            f"**Hardness:** {hardness.get('min', 'N/A')}–{hardness.get('max', 'N/A')} dGH"
        ))

        reveal(lambda: st.markdown(
            f"**Minimum Tank Size:** {result.get('min_tank_gallons', 'N/A')} gallons"
        ))
        reveal(lambda: st.markdown(
            f"**Difficulty:** {str(result.get('difficulty', 'N/A')).capitalize()}"
        ))
        reveal(lambda: st.markdown(
            f"**Maintenance Notes:** {result.get('maintenance_notes', 'N/A')}"
        ))
