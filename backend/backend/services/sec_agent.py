"""SEC data normalization layer.

Transforms raw XBRL company facts into standardized CompanyFinancials.
Handles tag fallback chains and frame-based deduplication.
"""

from __future__ import annotations

import re

from backend.models.financial import AnnualMetric, CompanyFinancials
from backend.models.sec import SECCompanyFacts, SECFact, SECFactEntry
from backend.services.sec_client import sec_client
from backend.services.ticker_resolver import ticker_resolver

# XBRL tag -> normalized field mapping with fallback chains.
# First match wins. Different companies use different tags for the same concept.
TAG_MAP: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "net_income": ["NetIncomeLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capital_expenditure": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "interest_expense": ["InterestExpense", "InterestExpenseDebt"],
    "long_term_debt": [
        # ASC 842 (post-2019) consolidates long-term debt + finance lease obligations
        # under this tag. Many large filers (KO, MCD, AAPL, etc.) only populate the
        # legacy LongTermDebt tag for older filings, so the lease-inclusive tag is
        # required for fresh data.
        "LongTermDebtAndCapitalLeaseObligations",
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ],
    "short_term_debt": [
        # Short-term borrowings reported under current liabilities. Companies
        # use a mix of these tags — commercial paper specifically when CP is
        # the dominant funding mode, ShortTermBorrowings as a generic catch-all,
        # NotesPayableCurrent for older filings.
        "ShortTermBorrowings",
        "CommercialPaper",
        "NotesPayableCurrent",
    ],
    "long_term_debt_current": [
        # Current portion of long-term debt — the slice maturing within 12mo
        # carved out from total long-term debt. KO and MCD both report
        # multi-billion values here, materially affecting net-debt math.
        "LongTermDebtCurrent",
    ],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "diluted_eps": ["EarningsPerShareDiluted"],
    "diluted_shares": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "CommonStockSharesOutstanding",
    ],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "depreciation_and_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
}

# Which unit to use for each metric
UNIT_MAP: dict[str, str] = {
    "diluted_eps": "USD/shares",
    "diluted_shares": "shares",
}


def _parse_calendar_year(frame: str) -> int | None:
    """Extract calendar year from frame string like 'CY2024' or 'CY2024Q4I'."""
    match = re.match(r"CY(\d{4})", frame)
    return int(match.group(1)) if match else None


def _extract_for_tag(
    fact: SECFact,
    unit: str,
) -> list[AnnualMetric]:
    """Extract annual metrics from a single XBRL fact."""
    entries: list[SECFactEntry] = []

    if unit == "USD/shares" and fact.units.USD_per_shares:
        entries = fact.units.USD_per_shares
    elif unit == "shares" and fact.units.shares:
        entries = fact.units.shares
    elif unit == "USD" and fact.units.USD:
        entries = fact.units.USD
    elif unit == "pure" and fact.units.pure:
        entries = fact.units.pure
    else:
        return []

    # Filter: 10-K annual filings with frame field (canonical entries)
    annual: dict[int, AnnualMetric] = {}
    for e in entries:
        if e.form != "10-K" or e.fp != "FY":
            continue
        if e.frame is None:
            continue

        cy = _parse_calendar_year(e.frame)
        if cy is None:
            continue

        # Skip quarterly period frames (CY2024Q1-Q4) but keep instant
        # frames (CY2024Q4I) which are balance sheet point-in-time values
        if re.search(r"Q\d$", e.frame):
            continue

        # Keep latest filing if duplicate calendar year
        if cy in annual and e.filed <= annual[cy].filing_date:
            continue

        annual[cy] = AnnualMetric(
            calendar_year=cy,
            value=float(e.val),
            fiscal_year=e.fy,
            filing_date=e.filed,
            sec_accession=e.accn,
            form=e.form,
        )

    return sorted(annual.values(), key=lambda m: m.calendar_year)


def _extract_annual_metrics(
    facts: dict[str, SECFact],
    tag_candidates: list[str],
    unit: str = "USD",
) -> list[AnnualMetric]:
    """Merge candidate XBRL tags by calendar year.

    Earlier tags in tag_candidates win for any given year (TAG_MAP encodes
    preference — modern lease-inclusive tags are listed first). Later legacy
    tags fill in years the preferred tag does not cover, preserving deep
    history for relative-valuation use.
    """
    merged: dict[int, AnnualMetric] = {}
    for tag in tag_candidates:
        if tag not in facts:
            continue
        for metric in _extract_for_tag(facts[tag], unit):
            merged.setdefault(metric.calendar_year, metric)
    return sorted(merged.values(), key=lambda m: m.calendar_year)


def _compute_total_debt(
    components: list[list[AnnualMetric]],
) -> list[AnnualMetric]:
    """Sum debt components by calendar year.

    Each component (long-term debt, short-term debt, current portion of LTD)
    is a series ``list[AnnualMetric]`` keyed by ``calendar_year``. We
    aggregate per-year by summing whichever components have a value for
    that year — missing components are skipped, NOT zero-filled, so
    coverage gaps don't silently understate debt with phantom zeros.

    Metadata (filing_date, accession, form) for the aggregate row is taken
    from the most-recently-filed component for that year, which keeps
    ``total_debt[-1]`` traceable to a real filing in audit trails.

    Returns ``[]`` if no component has any data for any year — callers
    should treat empty ``total_debt`` as "fall back to a debt-free DCF",
    matching prior behavior when ``long_term_debt`` was empty.
    """
    if not any(components):
        return []

    by_year: dict[int, list[AnnualMetric]] = {}
    for series in components:
        for m in series:
            by_year.setdefault(m.calendar_year, []).append(m)

    result: list[AnnualMetric] = []
    for cy in sorted(by_year):
        rows = by_year[cy]
        total = sum(m.value for m in rows)
        # Most-recently-filed row provides the canonical metadata. Strings
        # sort lexicographically which is correct for ISO filing dates.
        anchor = max(rows, key=lambda m: m.filing_date)
        result.append(
            AnnualMetric(
                calendar_year=cy,
                value=total,
                fiscal_year=anchor.fiscal_year,
                filing_date=anchor.filing_date,
                sec_accession=anchor.sec_accession,
                form=anchor.form,
            )
        )
    return result


def _compute_free_cash_flow(
    ocf: list[AnnualMetric], capex: list[AnnualMetric]
) -> list[AnnualMetric]:
    """FCF = Operating Cash Flow - Capital Expenditure, matched by calendar year."""
    capex_by_year = {m.calendar_year: m for m in capex}
    result = []
    for o in ocf:
        if o.calendar_year in capex_by_year:
            c = capex_by_year[o.calendar_year]
            result.append(
                AnnualMetric(
                    calendar_year=o.calendar_year,
                    value=o.value - abs(c.value),  # CapEx is often reported as positive
                    fiscal_year=o.fiscal_year,
                    filing_date=o.filing_date,
                    sec_accession=o.sec_accession,
                    form=o.form,
                )
            )
    return result


class SECDataService:
    """Normalizes raw SEC XBRL data into CompanyFinancials."""

    async def get_financials(self, ticker: str) -> CompanyFinancials:
        cik, entity_name = await ticker_resolver.resolve(ticker)
        company_facts = await sec_client.get_company_facts(cik)
        return self._normalize(company_facts, ticker.upper())

    def _normalize(
        self, facts: SECCompanyFacts, ticker: str
    ) -> CompanyFinancials:
        gaap = facts.facts.get("us-gaap", {})

        data: dict[str, list[AnnualMetric]] = {}
        for field_name, tag_candidates in TAG_MAP.items():
            unit = UNIT_MAP.get(field_name, "USD")
            data[field_name] = _extract_annual_metrics(gaap, tag_candidates, unit)

        data["free_cash_flow"] = _compute_free_cash_flow(
            data["operating_cash_flow"], data["capital_expenditure"]
        )

        # Aggregate debt components into total_debt. Done after the per-tag
        # extraction so each component still lives as its own field on
        # CompanyFinancials (useful for audit / logic_trace), with total_debt
        # as the canonical input for DCF / EV math.
        data["total_debt"] = _compute_total_debt([
            data["long_term_debt"],
            data["short_term_debt"],
            data["long_term_debt_current"],
        ])

        return CompanyFinancials(
            cik=facts.cik,
            ticker=ticker,
            entity_name=facts.entityName,
            **data,
        )


sec_data_service = SECDataService()
