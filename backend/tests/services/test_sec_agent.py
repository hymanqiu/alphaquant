"""Unit tests for sec_agent XBRL extraction."""

from __future__ import annotations

from backend.models.sec import SECFact, SECFactEntry, SECFactUnits
from backend.services.sec_agent import _extract_annual_metrics


def _entry(year: int, val: float, *, filed: str | None = None) -> SECFactEntry:
    return SECFactEntry(
        end=f"{year}-12-31",
        val=val,
        accn=f"acc-{year}",
        fy=year,
        fp="FY",
        form="10-K",
        filed=filed or f"{year + 1}-02-01",
        frame=f"CY{year}",
    )


def _fact(*entries: SECFactEntry) -> SECFact:
    return SECFact(units=SECFactUnits(USD=list(entries)))


def test_merge_fresh_tag_with_legacy_history() -> None:
    """Preferred tag with only 2024 + legacy with 2020–2022 → merged contains all years."""
    facts = {
        "LongTermDebtAndCapitalLeaseObligations": _fact(_entry(2024, 42_400.0)),
        "LongTermDebt": _fact(
            _entry(2020, 30_000.0),
            _entry(2021, 32_000.0),
            _entry(2022, 35_000.0),
        ),
    }
    result = _extract_annual_metrics(
        facts,
        ["LongTermDebtAndCapitalLeaseObligations", "LongTermDebt", "LongTermDebtNoncurrent"],
    )
    assert [m.calendar_year for m in result] == [2020, 2021, 2022, 2024]
    assert result[-1].value == 42_400.0  # ASC 842 value preserved
    assert result[0].value == 30_000.0  # legacy 2020 preserved


def test_same_year_in_two_tags_earlier_candidate_wins() -> None:
    """If preferred and legacy share a year, the earlier-listed tag wins."""
    facts = {
        "LongTermDebtAndCapitalLeaseObligations": _fact(_entry(2022, 99.0)),
        "LongTermDebt": _fact(_entry(2022, 11.0), _entry(2021, 10.0)),
    }
    result = _extract_annual_metrics(
        facts,
        ["LongTermDebtAndCapitalLeaseObligations", "LongTermDebt"],
    )
    by_year = {m.calendar_year: m.value for m in result}
    assert by_year == {2021: 10.0, 2022: 99.0}


def test_only_legacy_tag_present_no_regression() -> None:
    """Tickers whose legacy series is already complete are unchanged."""
    legacy = _fact(_entry(2020, 1.0), _entry(2021, 2.0), _entry(2022, 3.0))
    facts = {"LongTermDebt": legacy}
    result = _extract_annual_metrics(
        facts, ["LongTermDebtAndCapitalLeaseObligations", "LongTermDebt"]
    )
    assert [(m.calendar_year, m.value) for m in result] == [(2020, 1.0), (2021, 2.0), (2022, 3.0)]


def test_no_matching_tags_returns_empty() -> None:
    assert _extract_annual_metrics({}, ["LongTermDebt"]) == []
    assert _extract_annual_metrics({"Other": _fact(_entry(2024, 1.0))}, ["LongTermDebt"]) == []


def test_quarterly_and_non_fy_entries_filtered() -> None:
    """Merge must not bypass _extract_for_tag's filters."""
    quarterly = SECFactEntry(
        end="2024-03-31",
        val=5.0,
        accn="acc-q",
        fy=2024,
        fp="Q1",
        form="10-Q",
        filed="2024-05-01",
        frame="CY2024Q1",
    )
    no_frame = SECFactEntry(
        end="2024-12-31",
        val=7.0,
        accn="acc-nf",
        fy=2024,
        fp="FY",
        form="10-K",
        filed="2025-02-01",
        frame=None,
    )
    facts = {
        "LongTermDebt": SECFact(
            units=SECFactUnits(USD=[quarterly, no_frame, _entry(2023, 100.0)])
        )
    }
    result = _extract_annual_metrics(facts, ["LongTermDebt"])
    assert [(m.calendar_year, m.value) for m in result] == [(2023, 100.0)]
