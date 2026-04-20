"""Unit tests for pure math helpers in relative_valuation_math."""

from __future__ import annotations

from backend.agents.nodes.relative_valuation_math import (
    compute_dividend_yield,
    compute_ffo,
)


def test_compute_ffo_basic() -> None:
    assert compute_ffo(100.0, 30.0) == 130.0


def test_compute_ffo_negative_ni_ok() -> None:
    """FFO simply adds — it's the caller's job to gate by ffo > 0 for P/FFO."""
    assert compute_ffo(-20.0, 50.0) == 30.0


def test_compute_ffo_none_inputs() -> None:
    assert compute_ffo(None, 30.0) is None
    assert compute_ffo(100.0, None) is None
    assert compute_ffo(None, None) is None


def test_compute_dividend_yield_basic() -> None:
    # $3.00 / $100.00 = 3.0%
    assert compute_dividend_yield(3.0, 100.0) == 3.0


def test_compute_dividend_yield_rounding() -> None:
    # 2.5/78 ≈ 3.2051 → 3.21
    assert compute_dividend_yield(2.5, 78.0) == 3.21


def test_compute_dividend_yield_zero_price() -> None:
    assert compute_dividend_yield(3.0, 0.0) is None


def test_compute_dividend_yield_negative_price() -> None:
    assert compute_dividend_yield(3.0, -5.0) is None


def test_compute_dividend_yield_none_inputs() -> None:
    assert compute_dividend_yield(None, 100.0) is None
    assert compute_dividend_yield(3.0, None) is None
    assert compute_dividend_yield(0.0, 100.0) is None  # zero dividend → None
