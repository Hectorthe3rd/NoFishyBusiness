# frontend/pages/volume.py
# ─────────────────────────────────────────────────────────────────────────────
# Volume Calculator page.
# Lets the user enter tank dimensions (length × width × depth in inches)
# and displays the water volume in US gallons and the total water weight.
# This is a pure math endpoint — no AI or database involved.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st   # UI framework
import sys, os

# Add the project root to sys.path so we can import from frontend/app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post   # Shared POST helper with error handling

# ── Page title ────────────────────────────────────────────────────────────────
st.title("📐 Volume Calculator")
st.markdown("Enter your tank dimensions to calculate water volume and weight.")

# ── Input form ────────────────────────────────────────────────────────────────
# st.form groups inputs so the backend is only called when the user clicks
# "Calculate", not on every keystroke.
with st.form("volume_form"):
    # Number inputs with a minimum of 0.01 to prevent zero/negative dimensions
    length = st.number_input("Length (inches)", min_value=0.01, value=24.0, step=0.5)
    width  = st.number_input("Width (inches)",  min_value=0.01, value=12.0, step=0.5)
    depth  = st.number_input("Water Depth (inches)", min_value=0.01, value=12.0, step=0.5)
    submitted = st.form_submit_button("Calculate")   # Triggers the block below

# ── Handle submission ─────────────────────────────────────────────────────────
if submitted:
    # Show a spinner while waiting for the backend response
    with st.spinner("Loading..."):
        # POST the three dimensions to /volume; backend returns volume_gallons + weight_pounds
        result = backend_post("/volume", {"length": length, "width": width, "depth": depth})

    if result:   # result is None if the backend returned an error
        st.success("Calculation complete!")

        # Display results side-by-side in two columns
        col1, col2 = st.columns(2)
        with col1:
            # st.metric renders a large labelled number — good for key results
            st.metric("Volume", f"{result['volume_gallons']} gallons")
        with col2:
            st.metric("Weight", f"{result['weight_pounds']} pounds")
