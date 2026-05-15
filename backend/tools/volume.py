"""
backend/tools/volume.py

Volume Calculator tool for NoFishyBusiness.

Computes aquarium water volume (in US gallons) and the corresponding water
weight (in pounds) from tank dimensions. Supports multiple input units:
inches, cm, feet, and meters — all converted to cubic inches before the
standard formula is applied.

Formulas
--------
- volume_gallons = round((length_in * width_in * depth_in) / 231.0, 2)
  (231 cubic inches = 1 US gallon)
- weight_pounds  = round(volume_gallons * 8.34, 2)
  (fresh water weighs approximately 8.34 lb per US gallon)
- weight_warning: if total weight (water + 15% for glass/substrate) exceeds
  a typical residential floor load threshold (~800 lbs for a 4 sq ft footprint),
  a warning is returned.
"""

import json

import openai

from backend import logger
from backend.models import UserContext
from backend.prompt_factory import PromptFactory

# ---------------------------------------------------------------------------
# Unit conversion factors → cubic inches
# ---------------------------------------------------------------------------

_TO_INCHES: dict[str, float] = {
    "inches": 1.0,
    "cm":     0.393701,   # 1 cm = 0.393701 inches
    "feet":   12.0,       # 1 foot = 12 inches
    "meters": 39.3701,    # 1 meter = 39.3701 inches
}

# Residential floor load guideline: ~40 lbs per sq ft.
# A 4 sq ft tank footprint (common for 20–55 gal) = 160 lbs structural limit.
# We warn when water weight + 15% (glass/substrate) exceeds 800 lbs total
# (roughly a 90-gallon tank), which is where floor reinforcement is often needed.
_WEIGHT_WARNING_THRESHOLD_LBS = 800.0

# ---------------------------------------------------------------------------
# OpenAI client — lazy singleton
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    """Return the shared OpenAI client, creating it on first use."""
    global _client
    if _client is None:
        _client = openai.OpenAI()
    return _client


def calculate_volume(
    length: float,
    width: float,
    depth: float,
    unit: str = "inches",
) -> dict:
    """
    Calculate aquarium water volume and weight from tank dimensions.

    Converts the input dimensions to inches first, then applies the standard
    formula. Adds a weight warning when the total load (water + 15% for
    glass/substrate) exceeds the residential floor load guideline.

    Also calls the LLM to generate a practical pro-tip about the weight.

    Args:
        length: Tank length in the specified unit (must be positive).
        width:  Tank width in the specified unit (must be positive).
        depth:  Water depth in the specified unit (must be positive).
        unit:   One of "inches", "cm", "feet", "meters". Defaults to "inches".

    Returns:
        A dict with keys:
          - ``volume_gallons`` (float): Water volume rounded to 2 decimal places.
          - ``weight_pounds``  (float): Water weight rounded to 2 decimal places.
          - ``weight_warning`` (str | None): Floor load warning if applicable.
          - ``pro_tip``        (str | None): Practical advice from LLM.
    """
    # ── Unit conversion ───────────────────────────────────────────────────
    factor = _TO_INCHES.get(unit, 1.0)
    length_in = length * factor
    width_in  = width  * factor
    depth_in  = depth  * factor

    # ── Pure math ─────────────────────────────────────────────────────────
    volume_gallons = round((length_in * width_in * depth_in) / 231.0, 2)
    weight_pounds  = round(volume_gallons * 8.34, 2)

    # ── Weight warning (water + 15% for glass/substrate) ──────────────────
    total_weight = weight_pounds * 1.15
    weight_warning: str | None = None
    if total_weight > _WEIGHT_WARNING_THRESHOLD_LBS:
        weight_warning = (
            f"⚠️ **Floor Load Warning**: This tank's estimated total weight "
            f"(water + glass/substrate) is approximately **{total_weight:.0f} lbs**. "
            f"Tanks over {_WEIGHT_WARNING_THRESHOLD_LBS:.0f} lbs may require "
            f"floor reinforcement. Place over a load-bearing wall or consult a "
            f"structural engineer before filling."
        )

    result = {
        "volume_gallons": volume_gallons,
        "weight_pounds":  weight_pounds,
        "weight_warning": weight_warning,
        "pro_tip":        None,
    }

    # ── LLM pro-tip enrichment ────────────────────────────────────────────
    try:
        system_prompt = PromptFactory.get_prompt(
            feature_id="volume",
            context="",
            user=UserContext.guest(),
        )

        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=200,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Tank dimensions: {length} × {width} × {depth} {unit}. "
                        f"Volume: {volume_gallons} gallons. "
                        f"Weight: {weight_pounds} lbs. "
                        "Provide a practical pro-tip about this tank weight."
                    ),
                },
            ],
        )

        usage = response.usage
        if usage:
            logger.log_llm_call(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

        raw = response.choices[0].message.content or ""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        parsed = json.loads(raw)
        result["pro_tip"] = parsed.get("pro_tip")

    except (openai.OpenAIError, json.JSONDecodeError, Exception) as exc:
        logger.log_error("VolumeTipError", str(exc))
        result["pro_tip"] = None

    return result
