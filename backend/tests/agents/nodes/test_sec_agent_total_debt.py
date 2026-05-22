"""Unit tests for ``sec_agent._compute_total_debt`` aggregation.

The function is the single source of truth for what "total debt" means in
this codebase. The test cases pin three properties that downstream DCF and
EV math rely on:

1. **Component-wise sum by year** — when multiple components have a value
   for the same calendar year, the aggregate is their sum.
2. **No phantom zeros** — a missing component for a year does NOT zero-fill;
   we sum only what we have. This protects against silently understating
   debt when, say, the SEC filing didn't report ``ShortTermBorrowings`` that
   year.
3. **Backward compatibility** — when only ``long_term_debt`` is populated
   (older filers, or sparse XBRL coverage) ``total_debt`` equals
   ``long_term_debt`` exactly, so the aggregation never regresses behavior
   relative to the pre-#9 partial-net-debt PR.
"""

from __future__ import annotations

from backend.models.financial import AnnualMetric
from backend.services.sec_agent import _compute_total_debt


def _m(year: int, value: float, *, filed: str = "2025-01-15") -> AnnualMetric:
    return AnnualMetric(
        calendar_year=year,
        value=value,
        fiscal_year=year,
        filing_date=filed,
        sec_accession="0000000000-00-000000",
        form="10-K",
    )


class TestComputeTotalDebt:
    def test_all_components_present_sums_per_year(self) -> None:
        """LTD + short-term + current portion all populate the same year."""
        ltd = [_m(2024, 30_000.0)]
        short = [_m(2024, 5_000.0)]
        curr = [_m(2024, 7_000.0)]

        result = _compute_total_debt([ltd, short, curr])

        assert len(result) == 1
        assert result[0].calendar_year == 2024
        assert result[0].value == 42_000.0

    def test_only_long_term_debt_passes_through_unchanged(self) -> None:
        """Backward compat: when components beyond LTD are empty, the
        aggregate equals the long-term debt series. Pre-#9 callers see no
        regression."""
        ltd = [_m(2022, 100.0), _m(2023, 110.0), _m(2024, 120.0)]

        result = _compute_total_debt([ltd, [], []])

        assert [m.value for m in result] == [100.0, 110.0, 120.0]
        assert [m.calendar_year for m in result] == [2022, 2023, 2024]

    def test_missing_components_skipped_not_zero_filled(self) -> None:
        """If 2023 has only LTD and 2024 has LTD + short, the 2023 value
        is NOT silently augmented with a zero for short-term — we only
        sum what's actually reported."""
        ltd = [_m(2023, 100.0), _m(2024, 100.0)]
        short = [_m(2024, 50.0)]  # only 2024

        result = _compute_total_debt([ltd, short, []])

        by_year = {m.calendar_year: m.value for m in result}
        assert by_year == {2023: 100.0, 2024: 150.0}

    def test_all_empty_returns_empty(self) -> None:
        """No data → no aggregate. Caller treats this as 'fall back to
        debt-free DCF', matching pre-existing behavior when
        ``long_term_debt`` was empty."""
        assert _compute_total_debt([[], [], []]) == []

    def test_metadata_anchored_to_most_recent_filing(self) -> None:
        """When components for the same year were filed at different times
        (e.g. a 10-K/A amendment landed for short-term debt), the aggregate
        row's filing_date / accession traces to the latest filing so audit
        trails point readers somewhere real."""
        ltd = [_m(2024, 100.0, filed="2025-01-15")]
        short = [_m(2024, 50.0, filed="2025-03-20")]  # later

        result = _compute_total_debt([ltd, short, []])

        assert len(result) == 1
        assert result[0].filing_date == "2025-03-20"
        assert result[0].value == 150.0

    def test_unsorted_input_yields_sorted_output(self) -> None:
        """Components arrive sorted from upstream extraction, but the
        aggregator should not assume so. Pin the ordering guarantee."""
        ltd = [_m(2024, 100.0), _m(2022, 80.0), _m(2023, 90.0)]

        result = _compute_total_debt([ltd, [], []])

        assert [m.calendar_year for m in result] == [2022, 2023, 2024]
