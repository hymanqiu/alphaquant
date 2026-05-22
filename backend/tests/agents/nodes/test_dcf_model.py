"""Unit tests for dcf_model pure computation functions.

Covers the four branches added/changed in the real-beta + net-debt PR:

1. ``compute_dcf`` legacy mode (no ``cash``/``total_debt``) vs. net-debt
   adjustment mode.
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

from backend.agents.nodes.dcf_model import _estimate_wacc, _run_dcf, compute_dcf
from backend.models.financial import AnnualMetric, CompanyFinancials


# ---------------------------------------------------------------------------
# compute_dcf — net-debt adjustment branch
# ---------------------------------------------------------------------------


class TestComputeDcfNetDebtAdjustment:
    """Equity value should reflect (EV + cash − total_debt) when both
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
        """Net-debt adjustment requires BOTH cash and total_debt."""
        result = compute_dcf(**self.BASE_KWARGS, cash=500_000.0)
        assert result["equity_value"] == result["enterprise_value"]

    def test_only_debt_provided_falls_back_to_legacy(self) -> None:
        result = compute_dcf(**self.BASE_KWARGS, total_debt=500_000.0)
        assert result["equity_value"] == result["enterprise_value"]

    def test_both_provided_applies_adjustment(self) -> None:
        """equity = EV + cash − total_debt (LT + ST + current portion of LTD)."""
        cash = 800_000.0
        debt = 300_000.0
        result = compute_dcf(**self.BASE_KWARGS, cash=cash, total_debt=debt)

        ev = result["enterprise_value"]
        expected_equity = round(ev + cash - debt, 2)
        assert result["equity_value"] == expected_equity

    def test_per_share_uses_adjusted_equity(self) -> None:
        cash = 800_000.0
        debt = 300_000.0
        result = compute_dcf(**self.BASE_KWARGS, cash=cash, total_debt=debt)

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

    def test_low_beta_returns_raw_cost_of_equity(self) -> None:
        """beta=0.1 lands at 0.0505, already above the 4 % floor — verifies
        the no-debt branch returns cost-of-equity unchanged when it does not
        need clamping. (Renamed from ``test_low_beta_clamped_to_floor`` —
        the previous name over-promised: the floor never actually engages
        here.)"""
        wacc = _estimate_wacc(
            debt=None, equity=None, interest_expense=None, beta=0.1,
        )
        # Raw cost of equity at beta=0.1: 0.045 + 0.1*0.055 = 0.0505
        # No debt branch → returns max(0.0505, 0.04) = 0.0505 (above floor)
        assert wacc == pytest.approx(0.0505, abs=1e-4)

    def test_zero_beta_returns_raw_cost_of_equity(self) -> None:
        """beta=0 → cost_of_equity = risk_free_rate = 0.045, above floor.
        Verifies the no-debt branch handles the beta=0 corner without
        crashing or rewriting to 1.2. (Renamed from
        ``test_zero_beta_clamped_to_floor`` — at 0.045 the floor doesn't
        actually engage; clamp behavior is covered by the next test.)"""
        wacc = _estimate_wacc(
            debt=None, equity=None, interest_expense=None, beta=0.0,
        )
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


# ---------------------------------------------------------------------------
# _run_dcf — beta fallback semantics (regression guard)
# ---------------------------------------------------------------------------


def _annual(value: float, year: int = 2024) -> AnnualMetric:
    return AnnualMetric(
        calendar_year=year,
        value=value,
        fiscal_year=year,
        filing_date=f"{year}-12-31",
        sec_accession="0000000000-00-000000",
        form="10-K",
    )


def _minimal_financials() -> CompanyFinancials:
    """Just enough state for ``_run_dcf`` to succeed end-to-end."""
    fcf_series = [_annual(1_000_000.0, y) for y in (2020, 2021, 2022, 2023, 2024)]
    return CompanyFinancials(
        cik=1,
        ticker="TEST",
        entity_name="Test Co",
        free_cash_flow=fcf_series,
        diluted_shares=[_annual(1_000_000.0)],
        total_debt=[_annual(500_000.0)],
        stockholders_equity=[_annual(2_000_000.0)],
        interest_expense=[_annual(25_000.0)],
        cash_and_equivalents=[_annual(800_000.0)],
    )


class TestRunDcfBetaFallback:
    """Regression guard for the ``profile.get('beta') or 1.2`` →
    ``if beta is None: beta = 1.2`` change. The unit test for
    ``_estimate_wacc(beta=0.0)`` alone is not enough — the bug lives one
    layer up in ``_run_dcf`` where the fallback is applied. If someone
    reverts that line to the ``or`` form, this test should fail."""

    def test_explicit_zero_beta_is_preserved(self) -> None:
        """A real beta of 0.0 from FMP must not silently become 1.2."""
        captured: dict[str, float] = {}

        def fake_writer(event: dict) -> None:
            # Reasoning steps surface beta — capture it from the WACC
            # message the node emits.
            pass

        result = _run_dcf(
            _minimal_financials(),
            fake_writer,
            market_profile={"beta": 0.0, "market_cap": 5_000_000.0},
        )
        # WACC reasoning string contains the beta we used. Pull it out and
        # confirm it's 0.00, not 1.20 (which is what `or 1.2` would have
        # produced).
        wacc_step = next(
            (s for s in result["reasoning_steps"] if "beta=" in s), None,
        )
        assert wacc_step is not None
        assert "beta=0.00" in wacc_step
        captured["dr"] = result["dcf_result"]["assumptions"]["discount_rate"]
        # With beta=0 + the floor, WACC should be well below the legacy
        # beta=1.2 outcome (~10.6 %). Anything ≤ 6 % proves the 0.0 was
        # honored rather than rewritten.
        assert captured["dr"] <= 6.0

    def test_missing_beta_falls_back_to_legacy_default(self) -> None:
        """When FMP omits beta entirely, fallback to 1.2 still works."""
        result = _run_dcf(
            _minimal_financials(),
            lambda _e: None,
            market_profile={},  # no beta key
        )
        wacc_step = next(
            (s for s in result["reasoning_steps"] if "beta=" in s), None,
        )
        assert wacc_step is not None
        assert "beta=1.20" in wacc_step
