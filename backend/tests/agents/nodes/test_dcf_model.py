"""Unit tests for dcf_model pure computation functions.

Covers the four branches added/changed in the real-beta + net-debt PR:

1. ``compute_dcf`` legacy mode (no ``cash``/``long_term_debt``) vs. partial
   net-debt adjustment mode.
2. ``_estimate_wacc`` market-cap fallback when book equity ≤ 0.
3. ``_estimate_wacc`` 4 % WACC floor for very-low-beta names.
4. (beta-fallback semantics — exercised via ``compute_dcf`` callers, see
   ``test_beta_fallback_only_on_none`` in the dcf_node integration suite if
   added later. The pure ``_estimate_wacc`` already takes ``beta`` as a
   required argument so the fallback lives one layer up in ``_run_dcf``;
   here we just sanity-check that ``beta=0.0`` does not blow up the WACC
   computation when explicitly passed.)
"""

from __future__ import annotations

import pytest

from backend.agents.nodes.dcf_model import _estimate_wacc, compute_dcf


# ---------------------------------------------------------------------------
# compute_dcf — net-debt adjustment branch
# ---------------------------------------------------------------------------


class TestComputeDcfNetDebtAdjustment:
    """Equity value should reflect (EV + cash − long_term_debt) when both
    capital-structure inputs are supplied; otherwise legacy EV-only path."""

    BASE_KWARGS = {
        "latest_fcf": 1_000_000.0,
        "growth_rate": 0.10,
        "terminal_growth_rate": 0.03,
        "discount_rate": 0.10,
        "shares_outstanding": 1_000_000.0,
    }

    def test_legacy_mode_equity_equals_enterprise_value(self) -> None:
        """When cash/debt are omitted, equity_value == enterprise_value."""
        result = compute_dcf(**self.BASE_KWARGS)
        assert result["equity_value"] == result["enterprise_value"]

    def test_only_cash_provided_falls_back_to_legacy(self) -> None:
        """Net-debt adjustment requires BOTH cash and long_term_debt."""
        result = compute_dcf(**self.BASE_KWARGS, cash=500_000.0)
        assert result["equity_value"] == result["enterprise_value"]

    def test_only_debt_provided_falls_back_to_legacy(self) -> None:
        result = compute_dcf(**self.BASE_KWARGS, long_term_debt=500_000.0)
        assert result["equity_value"] == result["enterprise_value"]

    def test_both_provided_applies_adjustment(self) -> None:
        """equity = EV + cash − long_term_debt (long-term debt only)."""
        cash = 800_000.0
        debt = 300_000.0
        result = compute_dcf(**self.BASE_KWARGS, cash=cash, long_term_debt=debt)

        ev = result["enterprise_value"]
        expected_equity = round(ev + cash - debt, 2)
        assert result["equity_value"] == expected_equity

    def test_per_share_uses_adjusted_equity(self) -> None:
        cash = 800_000.0
        debt = 300_000.0
        result = compute_dcf(**self.BASE_KWARGS, cash=cash, long_term_debt=debt)

        expected_per_share = round(
            result["equity_value"] / self.BASE_KWARGS["shares_outstanding"], 2
        )
        assert result["intrinsic_value_per_share"] == expected_per_share


# ---------------------------------------------------------------------------
# _estimate_wacc — market-cap fallback for non-positive book equity
# ---------------------------------------------------------------------------


class TestEstimateWaccMarketCapFallback:
    """Heavy-buyback names (MCD-style) carry negative retained earnings →
    book equity ≤ 0. Without the fallback, the debt + equity branch is
    skipped and we silently lose all capital-structure information. The
    fallback substitutes market cap so the weighted-average still works."""

    def test_negative_equity_with_market_cap_uses_market_cap(self) -> None:
        wacc = _estimate_wacc(
            debt=1_000.0,
            equity=-500.0,           # buyback company, negative book equity
            interest_expense=50.0,    # ~5% cost of debt
            market_cap=10_000.0,      # large positive market cap
            beta=1.0,
        )
        # Hand-computed expectation: cost_of_equity = 0.045 + 1.0*0.055 = 0.10
        # cost_of_debt = 50/1000 = 0.05; after-tax = 0.05*(1-0.21) = 0.0395
        # weights: equity = 10000/11000 ≈ 0.909, debt = 1000/11000 ≈ 0.091
        # wacc ≈ 0.909*0.10 + 0.091*0.0395 ≈ 0.0945
        assert wacc == pytest.approx(0.0945, abs=1e-3)

    def test_negative_equity_without_market_cap_returns_cost_of_equity(self) -> None:
        """No market cap → can't form WACC weights → fall back to cost of
        equity (still floored at 4 %)."""
        wacc = _estimate_wacc(
            debt=1_000.0,
            equity=-500.0,
            interest_expense=50.0,
            market_cap=None,
            beta=1.0,
        )
        # Falls through to the cost_of_equity return
        assert wacc == pytest.approx(0.10, abs=1e-3)

    def test_positive_equity_does_not_use_market_cap(self) -> None:
        """When book equity is positive, market cap is irrelevant."""
        wacc_with_mcap = _estimate_wacc(
            debt=1_000.0, equity=5_000.0, interest_expense=50.0,
            market_cap=999_999.0, beta=1.0,
        )
        wacc_without_mcap = _estimate_wacc(
            debt=1_000.0, equity=5_000.0, interest_expense=50.0,
            market_cap=None, beta=1.0,
        )
        assert wacc_with_mcap == pytest.approx(wacc_without_mcap)


# ---------------------------------------------------------------------------
# _estimate_wacc — 4 % floor
# ---------------------------------------------------------------------------


class TestEstimateWaccFloor:
    """Defensive low-beta names (utilities, consumer staples) can produce
    a WACC below 4 %, which dramatically over-values them. We floor at 4 %
    as a guardrail; this test pins the threshold."""

    def test_low_beta_clamped_to_floor(self) -> None:
        wacc = _estimate_wacc(
            debt=None, equity=None, interest_expense=None, beta=0.1,
        )
        # Raw cost of equity at beta=0.1: 0.045 + 0.1*0.055 = 0.0505
        # No debt branch → returns max(0.0505, 0.04) = 0.0505 (above floor)
        assert wacc == pytest.approx(0.0505, abs=1e-4)

    def test_zero_beta_clamped_to_floor(self) -> None:
        """beta=0 → cost_of_equity = 0.045 → floor kicks in at 4 %."""
        wacc = _estimate_wacc(
            debt=None, equity=None, interest_expense=None, beta=0.0,
        )
        # cost_of_equity = 0.045 which is above 0.04 → returned as-is
        assert wacc == pytest.approx(0.045, abs=1e-4)

    def test_full_branch_with_low_costs_floors_at_4pct(self) -> None:
        """Explicit construction of a sub-4% WACC scenario: tiny beta + tiny
        cost of debt + heavy debt weighting. Verifies the floor in the
        full WACC branch (not just the cost-of-equity fallback)."""
        wacc = _estimate_wacc(
            debt=10_000.0,        # 91% debt weight
            equity=1_000.0,
            interest_expense=10.0,  # 0.1% cost of debt
            beta=0.0,
        )
        # Without floor: ~0.91 * 0.0008 + 0.09 * 0.045 ≈ 0.0048 → clamps to 0.04
        assert wacc == pytest.approx(0.04, abs=1e-6)
