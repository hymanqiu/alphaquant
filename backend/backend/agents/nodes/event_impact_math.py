"""Pure computation functions for event impact analysis.

No I/O — all functions are deterministic and testable.
Maps news events to DCF parameter adjustments and triggers recalculation.
"""

from __future__ import annotations

from typing import Any

from .dcf_model import compute_dcf


# ---------------------------------------------------------------------------
# Parameter registry
# ---------------------------------------------------------------------------

PARAMETER_REGISTRY: dict[str, dict[str, Any]] = {
    "growth_rate": {
        "display_name": "FCF Growth Rate",
        "unit": "%",
        "min": -10.0,
        "max": 30.0,
        "consumers": ["dcf"],
    },
    "terminal_growth_rate": {
        "display_name": "Terminal Growth Rate",
        "unit": "%",
        "min": 0.0,
        "max": 5.0,
        "consumers": ["dcf"],
    },
    "discount_rate": {
        "display_name": "Discount Rate (WACC)",
        "unit": "%",
        "min": 5.0,
        "max": 20.0,
        "consumers": ["dcf"],
    },
    "risk_adjustment": {
        "display_name": "Risk Adjustment",
        "unit": "%",
        "min": -5.0,
        "max": 10.0,
        "consumers": ["dcf"],
    },
    "revenue_adjustment": {
        "display_name": "Revenue Adjustment",
        "unit": "multiplier",
        "min": 0.5,
        "max": 1.5,
        "consumers": ["dcf"],
    },
    "margin_adjustment": {
        "display_name": "Margin Adjustment",
        "unit": "%",
        "min": -10.0,
        "max": 10.0,
        "consumers": ["dcf"],
    },
    "fcf_one_time_adjust": {
        "display_name": "FCF One-time Adjustment",
        "unit": "$",
        "min": None,
        "max": None,
        "consumers": ["dcf"],
    },
}


# ---------------------------------------------------------------------------
# Core pure functions
# ---------------------------------------------------------------------------


def apply_parameter_adjustment(
    original_value: float,
    adjustment: dict[str, Any],
    param_name: str,
) -> float:
    """Apply a single parameter adjustment to an original value.

    Adjustment types:
    - "delta": original + value
    - "multiplier": original * value
    - "absolute": value (replaces original)

    The result is clamped to the registry min/max for the parameter.
    """
    adj_type = adjustment.get("type", "delta")
    value = adjustment.get("value", 0)

    if adj_type == "delta":
        result = original_value + value
    elif adj_type == "multiplier":
        result = original_value * value
    elif adj_type == "absolute":
        result = value
    else:
        return original_value

    # Clamp to registry bounds
    reg = PARAMETER_REGISTRY.get(param_name, {})
    min_val = reg.get("min")
    max_val = reg.get("max")
    if min_val is not None:
        result = max(min_val, result)
    if max_val is not None:
        result = min(max_val, result)

    return result


def apply_all_adjustments(
    original_assumptions: dict[str, float],
    parameter_adjustments: dict[str, dict[str, Any] | None],
) -> dict[str, float]:
    """Apply all parameter adjustments to original DCF assumptions.

    Direct adjustments: growth_rate, terminal_growth_rate, discount_rate
    Mapped adjustments:
      - risk_adjustment → added to discount_rate
      - revenue_adjustment → multiplied into growth_rate
      - margin_adjustment → 0.5x weight added to growth_rate
      - fcf_one_time_adjust → replaces latest_fcf

    Returns a new dict with adjusted values. Does not mutate input.
    """
    result = dict(original_assumptions)

    # --- Direct parameter adjustments ---
    for direct_key in ("growth_rate", "terminal_growth_rate", "discount_rate"):
        adj = parameter_adjustments.get(direct_key)
        if adj is None:
            continue
        if direct_key in result:
            result[direct_key] = apply_parameter_adjustment(
                result[direct_key], adj, direct_key,
            )

    # --- Mapped adjustments ---
    # risk_adjustment → accumulate into discount_rate
    risk_adj = parameter_adjustments.get("risk_adjustment")
    if risk_adj and "discount_rate" in result:
        risk_value = risk_adj.get("value", 0)
        result["discount_rate"] = apply_parameter_adjustment(
            result["discount_rate"], {"type": "delta", "value": risk_value},
            "discount_rate",
        )

    # revenue_adjustment → multiply growth_rate
    rev_adj = parameter_adjustments.get("revenue_adjustment")
    if rev_adj and "growth_rate" in result:
        rev_value = rev_adj.get("value", 1.0)
        result["growth_rate"] = apply_parameter_adjustment(
            result["growth_rate"], {"type": "multiplier", "value": rev_value},
            "growth_rate",
        )

    # margin_adjustment → 0.5x weight added to growth_rate
    margin_adj = parameter_adjustments.get("margin_adjustment")
    if margin_adj and "growth_rate" in result:
        margin_value = margin_adj.get("value", 0) * 0.5
        result["growth_rate"] = apply_parameter_adjustment(
            result["growth_rate"], {"type": "delta", "value": margin_value},
            "growth_rate",
        )

    # fcf_one_time_adjust → replace latest_fcf
    fcf_adj = parameter_adjustments.get("fcf_one_time_adjust")
    if fcf_adj and "latest_fcf" in result:
        result["latest_fcf"] = apply_parameter_adjustment(
            result["latest_fcf"], {"type": "absolute", "value": fcf_adj.get("value", 0)},
            "fcf_one_time_adjust",
        )

    return result


def recalculate_dcf(
    adjusted_assumptions: dict[str, float],
    shares_outstanding: float | None,
) -> dict[str, Any]:
    """Run DCF model with adjusted assumptions.

    Converts percentage values to decimals before passing to compute_dcf.
    """
    growth_rate = adjusted_assumptions.get("growth_rate", 10.0) / 100
    terminal_growth = adjusted_assumptions.get("terminal_growth_rate", 3.0) / 100
    discount_rate = adjusted_assumptions.get("discount_rate", 10.0) / 100
    latest_fcf = adjusted_assumptions.get("latest_fcf", 0)

    return compute_dcf(
        latest_fcf=latest_fcf,
        growth_rate=growth_rate,
        terminal_growth_rate=terminal_growth,
        discount_rate=discount_rate,
        shares_outstanding=shares_outstanding,
    )


# ---------------------------------------------------------------------------
# LLM response validation
# ---------------------------------------------------------------------------


def validate_filter_response(result: Any) -> dict[str, Any] | None:
    """Validate LLM Call 1 response: impactful article indices.

    Expected: {"impactful_indices": [int, ...], "reasoning": str}
    """
    if not isinstance(result, dict):
        return None

    indices = result.get("impactful_indices")
    if not isinstance(indices, list):
        return None

    validated_indices = [int(i) for i in indices if isinstance(i, (int, float))]
    if not validated_indices:
        return None

    return {
        "impactful_indices": validated_indices,
        "reasoning": str(result.get("reasoning", "")),
    }


def validate_analysis_response(result: Any) -> dict[str, Any] | None:
    """Validate LLM Call 2 response: parameter adjustments.

    Expected:
    {
      "adjustments": {
        "growth_rate": {"type": "delta", "value": float, "reasoning": str} | null,
        ...
      },
      "summary": str,
      "confidence": float
    }
    """
    if not isinstance(result, dict):
        return None

    adjustments_raw = result.get("adjustments")
    if not isinstance(adjustments_raw, dict):
        return None

    # Validate each adjustment entry
    validated_adjustments: dict[str, dict[str, Any] | None] = {}
    valid_types = {"delta", "multiplier", "absolute"}

    for key, value in adjustments_raw.items():
        if key not in PARAMETER_REGISTRY:
            continue
        if value is None:
            validated_adjustments[key] = None
            continue
        if not isinstance(value, dict):
            continue

        adj_type = value.get("type", "")
        adj_value = value.get("value")

        if adj_type not in valid_types:
            continue
        if not isinstance(adj_value, (int, float)):
            continue

        validated_adjustments[key] = {
            "type": str(adj_type),
            "value": float(adj_value),
            "reasoning": str(value.get("reasoning", "")),
        }

    # Clamp confidence to [0, 1]
    confidence = result.get("confidence", 0.5)
    if isinstance(confidence, (int, float)):
        confidence = max(0.0, min(1.0, float(confidence)))
    else:
        confidence = 0.5

    return {
        "adjustments": validated_adjustments,
        "summary": str(result.get("summary", "")),
        "confidence": confidence,
    }
