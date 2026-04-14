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
    "long_term_debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
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
    """Try all XBRL tag candidates. Return the one with the most recent data."""
    best: list[AnnualMetric] = []
    best_latest_year = -1

    for tag in tag_candidates:
        if tag not in facts:
            continue

        result = _extract_for_tag(facts[tag], unit)
        if not result:
            continue

        latest_year = result[-1].calendar_year
        # Prefer tag with most recent data; break ties by count
        if latest_year > best_latest_year or (
            latest_year == best_latest_year and len(result) > len(best)
        ):
            best = result
            best_latest_year = latest_year

    return best


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

        return CompanyFinancials(
            cik=facts.cik,
            ticker=ticker,
            entity_name=facts.entityName,
            **data,
        )


sec_data_service = SECDataService()
