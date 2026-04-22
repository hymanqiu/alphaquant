"""Unit tests for event_impact_math pure computation functions."""

from __future__ import annotations

import pytest

from backend.agents.nodes.event_impact_math import (
    PARAMETER_REGISTRY,
    apply_all_adjustments,
    apply_parameter_adjustment,
    recalculate_dcf,
    validate_analysis_response,
    validate_filter_response,
)


# ---------------------------------------------------------------------------
# apply_parameter_adjustment
# ---------------------------------------------------------------------------


class TestApplyParameterAdjustment:
    def test_delta_type(self) -> None:
        result = apply_parameter_adjustment(
            10.0, {"type": "delta", "value": 2.5}, "growth_rate",
        )
        assert result == 12.5

    def test_multiplier_type(self) -> None:
        result = apply_parameter_adjustment(
            10.0, {"type": "multiplier", "value": 0.95}, "growth_rate",
        )
        assert result == pytest.approx(9.5)

    def test_absolute_type(self) -> None:
        result = apply_parameter_adjustment(
            1000.0, {"type": "absolute", "value": 2000.0}, "fcf_one_time_adjust",
        )
        assert result == 2000.0

    def test_unknown_type_returns_original(self) -> None:
        result = apply_parameter_adjustment(
            10.0, {"type": "invalid", "value": 5.0}, "growth_rate",
        )
        assert result == 10.0

    def test_clamps_to_min(self) -> None:
        result = apply_parameter_adjustment(
            10.0, {"type": "delta", "value": -50.0}, "growth_rate",
        )
        # growth_rate min is -10.0
        assert result == -10.0

    def test_clamps_to_max(self) -> None:
        result = apply_parameter_adjustment(
            10.0, {"type": "delta", "value": 50.0}, "growth_rate",
        )
        # growth_rate max is 30.0
        assert result == 30.0

    def test_no_clamp_when_no_bounds(self) -> None:
        result = apply_parameter_adjustment(
            1000.0, {"type": "delta", "value": -500.0}, "fcf_one_time_adjust",
        )
        # fcf_one_time_adjust has min=None, max=None
        assert result == 500.0


# ---------------------------------------------------------------------------
# apply_all_adjustments
# ---------------------------------------------------------------------------


class TestApplyAllAdjustments:
    def _make_original(self) -> dict[str, float]:
        return {
            "growth_rate": 12.0,
            "terminal_growth_rate": 3.0,
            "discount_rate": 8.5,
            "latest_fcf": 1_000_000_000.0,
        }

    def test_no_adjustments_returns_original_values(self) -> None:
        original = self._make_original()
        result = apply_all_adjustments(original, {})
        assert result == original

    def test_direct_growth_rate_delta(self) -> None:
        original = self._make_original()
        result = apply_all_adjustments(original, {
            "growth_rate": {"type": "delta", "value": 2.0},
        })
        assert result["growth_rate"] == pytest.approx(14.0)
        assert result["discount_rate"] == original["discount_rate"]

    def test_direct_discount_rate_delta(self) -> None:
        original = self._make_original()
        result = apply_all_adjustments(original, {
            "discount_rate": {"type": "delta", "value": 0.5},
        })
        assert result["discount_rate"] == pytest.approx(9.0)

    def test_risk_adjustment_adds_to_discount_rate(self) -> None:
        original = self._make_original()
        result = apply_all_adjustments(original, {
            "risk_adjustment": {"type": "delta", "value": 1.0},
        })
        assert result["discount_rate"] == pytest.approx(9.5)

    def test_revenue_adjustment_multiplies_growth_rate(self) -> None:
        original = self._make_original()
        result = apply_all_adjustments(original, {
            "revenue_adjustment": {"type": "multiplier", "value": 0.9},
        })
        assert result["growth_rate"] == pytest.approx(10.8)

    def test_margin_adjustment_half_weight_to_growth(self) -> None:
        original = self._make_original()
        result = apply_all_adjustments(original, {
            "margin_adjustment": {"type": "delta", "value": 4.0},
        })
        # margin_adjustment * 0.5 = 2.0 added to growth_rate
        assert result["growth_rate"] == pytest.approx(14.0)

    def test_fcf_one_time_adjust_replaces_latest_fcf(self) -> None:
        original = self._make_original()
        result = apply_all_adjustments(original, {
            "fcf_one_time_adjust": {"type": "absolute", "value": 800_000_000.0},
        })
        assert result["latest_fcf"] == 800_000_000.0

    def test_combined_adjustments_stack(self) -> None:
        original = self._make_original()
        result = apply_all_adjustments(original, {
            "growth_rate": {"type": "delta", "value": 2.0},
            "risk_adjustment": {"type": "delta", "value": 1.0},
        })
        # growth_rate: 12.0 + 2.0 = 14.0
        # discount_rate: 8.5 + 1.0 = 9.5
        assert result["growth_rate"] == pytest.approx(14.0)
        assert result["discount_rate"] == pytest.approx(9.5)

    def test_does_not_mutate_original(self) -> None:
        original = self._make_original()
        original_copy = dict(original)
        apply_all_adjustments(original, {
            "growth_rate": {"type": "delta", "value": 5.0},
        })
        assert original == original_copy


# ---------------------------------------------------------------------------
# recalculate_dcf
# ---------------------------------------------------------------------------


class TestRecalculateDCF:
    def test_produces_valid_dcf_result(self) -> None:
        assumptions = {
            "growth_rate": 12.0,
            "terminal_growth_rate": 3.0,
            "discount_rate": 8.5,
            "latest_fcf": 1_000_000_000.0,
        }
        result = recalculate_dcf(assumptions, shares_outstanding=1_000_000_000)
        assert result["intrinsic_value_per_share"] is not None
        assert result["intrinsic_value_per_share"] > 0
        assert "projected_fcf" in result
        assert "terminal_value" in result

    def test_no_shares_gives_null_per_share(self) -> None:
        assumptions = {
            "growth_rate": 12.0,
            "terminal_growth_rate": 3.0,
            "discount_rate": 8.5,
            "latest_fcf": 1_000_000_000.0,
        }
        result = recalculate_dcf(assumptions, shares_outstanding=None)
        assert result["intrinsic_value_per_share"] is None


# ---------------------------------------------------------------------------
# validate_filter_response
# ---------------------------------------------------------------------------


class TestValidateFilterResponse:
    def test_valid_response(self) -> None:
        result = validate_filter_response({
            "impactful_indices": [0, 3, 5],
            "reasoning": "Major events found",
        })
        assert result is not None
        assert result["impactful_indices"] == [0, 3, 5]
        assert result["reasoning"] == "Major events found"

    def test_empty_indices_returns_none(self) -> None:
        result = validate_filter_response({
            "impactful_indices": [],
            "reasoning": "Nothing impactful",
        })
        assert result is None

    def test_non_dict_returns_none(self) -> None:
        assert validate_filter_response("not a dict") is None
        assert validate_filter_response(None) is None

    def test_missing_indices_returns_none(self) -> None:
        result = validate_filter_response({"reasoning": "no indices"})
        assert result is None

    def test_float_indices_converted_to_int(self) -> None:
        result = validate_filter_response({
            "impactful_indices": [0.0, 2.0],
            "reasoning": "test",
        })
        assert result is not None
        assert result["impactful_indices"] == [0, 2]


# ---------------------------------------------------------------------------
# validate_analysis_response
# ---------------------------------------------------------------------------


class TestValidateAnalysisResponse:
    def test_full_valid_response(self) -> None:
        result = validate_analysis_response({
            "adjustments": {
                "growth_rate": {"type": "delta", "value": 2.0, "reasoning": "New contracts"},
                "discount_rate": {"type": "delta", "value": 0.5, "reasoning": "SEC probe"},
            },
            "summary": "Mixed signals",
            "confidence": 0.75,
        })
        assert result is not None
        assert result["confidence"] == 0.75
        assert "growth_rate" in result["adjustments"]
        assert result["adjustments"]["growth_rate"]["value"] == 2.0

    def test_partial_adjustments_rest_implicit_null(self) -> None:
        result = validate_analysis_response({
            "adjustments": {
                "growth_rate": {"type": "delta", "value": 1.0, "reasoning": "test"},
            },
            "summary": "test",
            "confidence": 0.5,
        })
        assert result is not None
        assert "growth_rate" in result["adjustments"]
        assert "terminal_growth_rate" not in result["adjustments"]

    def test_null_adjustments_preserved(self) -> None:
        result = validate_analysis_response({
            "adjustments": {
                "growth_rate": None,
                "discount_rate": {"type": "delta", "value": 0.5, "reasoning": "test"},
            },
            "summary": "test",
            "confidence": 0.6,
        })
        assert result is not None
        assert result["adjustments"]["growth_rate"] is None

    def test_confidence_clamped(self) -> None:
        result = validate_analysis_response({
            "adjustments": {},
            "summary": "test",
            "confidence": 1.5,
        })
        assert result is not None
        assert result["confidence"] == 1.0

    def test_confidence_clamped_negative(self) -> None:
        result = validate_analysis_response({
            "adjustments": {},
            "summary": "test",
            "confidence": -0.5,
        })
        assert result is not None
        assert result["confidence"] == 0.0

    def test_invalid_adjustment_type_skipped(self) -> None:
        result = validate_analysis_response({
            "adjustments": {
                "growth_rate": {"type": "invalid", "value": 2.0, "reasoning": "test"},
            },
            "summary": "test",
            "confidence": 0.5,
        })
        assert result is not None
        assert "growth_rate" not in result["adjustments"]

    def test_unknown_parameter_key_ignored(self) -> None:
        result = validate_analysis_response({
            "adjustments": {
                "unknown_param": {"type": "delta", "value": 2.0, "reasoning": "test"},
            },
            "summary": "test",
            "confidence": 0.5,
        })
        assert result is not None
        assert "unknown_param" not in result["adjustments"]

    def test_non_dict_returns_none(self) -> None:
        assert validate_analysis_response("string") is None
        assert validate_analysis_response(None) is None

    def test_missing_adjustments_returns_none(self) -> None:
        result = validate_analysis_response({"summary": "test", "confidence": 0.5})
        assert result is None

    def test_non_numeric_confidence_defaults(self) -> None:
        result = validate_analysis_response({
            "adjustments": {},
            "summary": "test",
            "confidence": "high",
        })
        assert result is not None
        assert result["confidence"] == 0.5
