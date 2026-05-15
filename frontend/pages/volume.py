# frontend/pages/volume.py
# ─────────────────────────────────────────────────────────────────────────────
# Volume Calculator page.
# Supports multiple input units: inches, cm, feet, meters.
# Renders an isometric SVG tank diagram that scales to fit a fixed display
# box, fills the water portion in semi-transparent blue, and labels the
# length / width / height axes with the actual input measurements.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from frontend.app import backend_post, reveal


# ─────────────────────────────────────────────────────────────────────────────
# SVG Tank Visualizer
# ─────────────────────────────────────────────────────────────────────────────

def _build_tank_svg(length: float, width: float, depth: float, unit: str) -> str:
    """
    Generate an isometric SVG of a rectangular tank with a water fill.

    The tank is drawn using a cabinet-projection isometric style:
      - Front face: rectangle (length × height)
      - Top face:   parallelogram (length × width, skewed up-right)
      - Right face: parallelogram (width × height, skewed up-right)

    The water fill covers the depth portion of the front and right faces,
    plus the full top face of the water surface.

    The diagram is normalised to fit inside a 480 × 340 px canvas regardless
    of the actual dimensions (handles extreme ratios like 100 × 12 × 12).

    Args:
        length: Tank length in the user's chosen unit.
        width:  Tank width in the user's chosen unit.
        depth:  Water depth in the user's chosen unit.
        unit:   Label string for the axis annotations.

    Returns:
        An SVG string ready to embed in st.components.v1.html().
    """
    # ── Canvas and projection constants ──────────────────────────────────
    CANVAS_W = 480
    CANVAS_H = 340
    MARGIN   = 60   # px padding around the tank for labels

    # Isometric skew: the top/right faces are drawn at a 30° angle.
    # iso_x and iso_y are the pixel offsets per unit of "depth" dimension.
    # We use a simple cabinet projection: depth goes up-right at 45°, scaled.
    ISO_ANGLE_X =  0.6   # horizontal component of the depth axis (per unit)
    ISO_ANGLE_Y = -0.4   # vertical component of the depth axis (per unit)

    # ── Normalise dimensions to fit the canvas ────────────────────────────
    # The bounding box of the isometric drawing is approximately:
    #   total_w = L_px + W_px * ISO_ANGLE_X
    #   total_h = H_px + W_px * abs(ISO_ANGLE_Y)
    # We scale all three dimensions by the same factor so the tank fits.

    available_w = CANVAS_W - 2 * MARGIN
    available_h = CANVAS_H - 2 * MARGIN

    # Start with a 1:1 mapping and find the scale factor
    # that makes the drawing fit in the available area.
    # We try a base scale and then clamp.
    base_scale = min(available_w / (length + width * abs(ISO_ANGLE_X)),
                     available_h / (depth  + width * abs(ISO_ANGLE_Y)))

    # Cap scale so very small tanks don't become tiny
    scale = max(base_scale, 1.0)

    L = length * scale   # pixel length (horizontal, front face)
    W = width  * scale   # pixel width  (depth axis)
    H = depth  * scale   # pixel height (vertical, front face)

    # ── Origin: bottom-left corner of the front face ──────────────────────
    # Place it so the whole drawing is centred in the canvas.
    total_draw_w = L + W * ISO_ANGLE_X
    total_draw_h = H + W * abs(ISO_ANGLE_Y)

    ox = (CANVAS_W - total_draw_w) / 2
    oy = (CANVAS_H + total_draw_h) / 2   # SVG y increases downward

    # ── Key corner points ─────────────────────────────────────────────────
    # Front face corners (bottom-left origin, going clockwise)
    A = (ox,       oy)           # front bottom-left
    B = (ox + L,   oy)           # front bottom-right
    C = (ox + L,   oy - H)       # front top-right
    D = (ox,       oy - H)       # front top-left

    # Back face corners (offset by the isometric depth vector)
    dx = W * ISO_ANGLE_X
    dy = W * ISO_ANGLE_Y   # negative = upward in SVG

    E = (A[0] + dx, A[1] + dy)   # back bottom-left  (hidden, not drawn)
    F = (B[0] + dx, B[1] + dy)   # back bottom-right
    G = (C[0] + dx, C[1] + dy)   # back top-right
    H_ = (D[0] + dx, D[1] + dy)  # back top-left

    # ── Water surface corners ─────────────────────────────────────────────
    # Water fills from the bottom up to `depth` (which equals H in pixels
    # since we used depth as the height dimension).
    # The water surface is at the same height as the top face (full fill).
    # If depth < tank height we'd need a separate tank_height input — since
    # the spec uses "water depth" as the only height input, the tank is
    # always filled to the top. We show the full fill in blue.
    Aw = A   # water bottom-left  = tank bottom-left
    Bw = B   # water bottom-right = tank bottom-right
    Cw = C   # water top-right    = tank top-right (full fill)
    Dw = D   # water top-left     = tank top-left

    def pt(p):
        return f"{p[0]:.1f},{p[1]:.1f}"

    def poly(*points, fill, stroke, stroke_w=1.5, opacity=1.0):
        pts = " ".join(pt(p) for p in points)
        return (
            f'<polygon points="{pts}" '
            f'fill="{fill}" fill-opacity="{opacity}" '
            f'stroke="{stroke}" stroke-width="{stroke_w}" />'
        )

    def line(p1, p2, color="#333", width=1.5, dash=""):
        dash_attr = f'stroke-dasharray="{dash}"' if dash else ""
        return (
            f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" '
            f'x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" '
            f'stroke="{color}" stroke-width="{width}" {dash_attr} />'
        )

    def text(x, y, msg, anchor="middle", size=12, color="#ddd", bold=False):
        weight = "bold" if bold else "normal"
        return (
            f'<text x="{x:.1f}" y="{y:.1f}" '
            f'text-anchor="{anchor}" '
            f'font-size="{size}" font-weight="{weight}" '
            f'font-family="monospace" fill="{color}">{msg}</text>'
        )

    label = unit  # e.g. "inches", "cm"

    # ── Build SVG elements ────────────────────────────────────────────────
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{CANVAS_W}" height="{CANVAS_H}" '
        f'style="background:#1a1a2e; border-radius:8px;">',
    ]

    # --- Hidden back edges (dashed) ---
    parts.append(line(A, E, "#666", 1.0, "4 3"))   # bottom-left back edge
    parts.append(line(E, F, "#666", 1.0, "4 3"))   # back bottom edge
    parts.append(line(E, H_, "#666", 1.0, "4 3"))  # back left edge

    # --- Water fill ---
    # Right face water (parallelogram: B → F → G → C)
    parts.append(poly(B, F, G, C,
                      fill="#4fc3f7", stroke="#29b6f6", opacity=0.55))
    # Top face water (parallelogram: D → C → G → H_)
    parts.append(poly(D, C, G, H_,
                      fill="#81d4fa", stroke="#29b6f6", opacity=0.45))
    # Front face water (rectangle: A → B → C → D)
    parts.append(poly(A, B, C, D,
                      fill="#4fc3f7", stroke="#29b6f6", opacity=0.50))

    # --- Tank frame (solid edges on top of water) ---
    # Front face outline
    parts.append(poly(A, B, C, D,
                      fill="none", stroke="#e0e0e0", stroke_w=2.0))
    # Right face outline
    parts.append(poly(B, F, G, C,
                      fill="none", stroke="#e0e0e0", stroke_w=2.0))
    # Top face outline
    parts.append(poly(D, C, G, H_,
                      fill="none", stroke="#e0e0e0", stroke_w=2.0))
    # Remaining visible edges
    parts.append(line(H_, G, "#e0e0e0", 2.0))   # back top edge (right)
    parts.append(line(F, G, "#e0e0e0", 2.0))    # back right edge

    # ── Dimension labels ──────────────────────────────────────────────────
    # Length label — below the front bottom edge, centred
    lx = (A[0] + B[0]) / 2
    ly = A[1] + 28
    parts.append(line((A[0], A[1] + 8), (B[0], B[1] + 8), "#aaa", 1.0))
    parts.append(text(lx, ly + 4, f"length: {length:g} {label}", size=11, color="#ccc"))

    # Height label — to the right of the front right edge, centred
    hx = C[0] + 14
    hy = (B[1] + C[1]) / 2
    parts.append(line((C[0] + 6, C[1]), (C[0] + 6, B[1]), "#aaa", 1.0))
    parts.append(text(hx + 2, hy + 4, f"depth: {depth:g} {label}",
                      anchor="start", size=11, color="#ccc"))

    # Width label — along the top-right isometric edge, offset outward
    # Midpoint of the B→F edge
    wx = (B[0] + F[0]) / 2 + 10
    wy = (B[1] + F[1]) / 2 + 18
    parts.append(text(wx, wy, f"width: {width:g} {label}",
                      anchor="start", size=11, color="#ccc"))

    parts.append("</svg>")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────

st.title("📐 Volume Calculator")
st.markdown("Enter your tank dimensions to calculate water volume and weight.")

with st.form("volume_form"):
    unit = st.selectbox(
        "Measurement Unit",
        ["inches", "cm", "feet", "meters"],
        index=0,
        help="All dimensions will be interpreted in this unit.",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        length = st.number_input(f"Length ({unit})", min_value=0.01, value=24.0, step=0.5)
    with col2:
        width  = st.number_input(f"Width ({unit})",  min_value=0.01, value=12.0, step=0.5)
    with col3:
        depth  = st.number_input(f"Water Depth ({unit})", min_value=0.01, value=12.0, step=0.5)

    submitted = st.form_submit_button("Calculate")

if submitted:
    with st.spinner("Calculating..."):
        result = backend_post("/volume", {
            "length": length,
            "width":  width,
            "depth":  depth,
            "unit":   unit,
        })

    if result:
        reveal(lambda: st.success("Calculation complete!"), delay=0.05)

        # ── Results + Tank Diagram side by side ───────────────────────────
        left, right = st.columns([1, 1])

        with left:
            reveal(lambda: st.metric("Volume", f"{result['volume_gallons']} gallons"), delay=0.08)
            reveal(lambda: st.metric("Weight", f"{result['weight_pounds']} lbs"), delay=0.08)

            if result.get("weight_warning"):
                reveal(lambda: st.warning(result["weight_warning"]), delay=0.08)

            if result.get("pro_tip"):
                reveal(lambda: st.info(f"💡 **Pro Tip:** {result['pro_tip']}"), delay=0.10)

        with right:
            reveal(lambda: None, delay=0.05)  # small pause before diagram appears
            import streamlit.components.v1 as components
            svg = _build_tank_svg(length, width, depth, unit)
            components.html(
                f'<div style="display:flex; justify-content:center;">{svg}</div>',
                height=360,
            )
