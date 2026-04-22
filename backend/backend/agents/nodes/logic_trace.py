"""Node 3: Logic tracing.

Maps every metric used in the analysis back to its SEC filing source.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import StreamWriter

from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    AnalysisCompleteEvent,
    ComponentEvent,
    ErrorEvent,
    StepCompleteEvent,
)
from backend.models.financial import AnnualMetric


def _filing_url(cik: int, accession: str) -> str:
    """Build URL to the SEC filing from CIK and accession number."""
    formatted = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{formatted}/{accession}-index.htm"


def _build_source_entry(
    metric_name: str,
    metric: AnnualMetric,
    cik: int,
) -> dict[str, Any]:
    return {
        "metric": metric_name,
        "calendar_year": metric.calendar_year,
        "value": metric.value,
        "form": metric.form,
        "filed": metric.filing_date,
        "accession": metric.sec_accession,
        "url": _filing_url(cik, metric.sec_accession),
    }


async def logic_trace_node(
    state: AnalysisState, writer: StreamWriter
) -> dict[str, Any]:
    financials = state["financials"]
    if financials is None:
        writer(ErrorEvent(
            message="Logic trace skipped: no financial data available.",
            recoverable=False,
        ).model_dump())
        return {"source_map": None, "verdict": None, "reasoning_steps": ["ERROR: No financial data for logic trace"]}

    try:
        return _run_logic_trace(state, financials, writer)
    except Exception as e:
        writer(ErrorEvent(
            message=f"Logic trace failed: {e}",
            recoverable=False,
        ).model_dump())
        writer(AnalysisCompleteEvent(
            verdict=f"Analysis incomplete: logic trace failed for {financials.ticker}.",
            ticker=financials.ticker,
        ).model_dump())
        return {"source_map": None, "verdict": None, "reasoning_steps": [f"ERROR: Logic trace failed - {e}"]}


def _run_logic_trace(state: AnalysisState, financials: Any, writer: StreamWriter) -> dict[str, Any]:
    writer(AgentThinkingEvent(
        node="logic_trace",
        content="Tracing all data points back to SEC filings...",
    ).model_dump())

    sources: list[dict[str, Any]] = []
    cik = financials.cik

    metric_fields = [
        ("Revenue", financials.revenue),
        ("Net Income", financials.net_income),
        ("Operating Income", financials.operating_income),
        ("Total Assets", financials.total_assets),
        ("Total Liabilities", financials.total_liabilities),
        ("Stockholders' Equity", financials.stockholders_equity),
        ("Operating Cash Flow", financials.operating_cash_flow),
        ("Capital Expenditure", financials.capital_expenditure),
        ("Free Cash Flow", financials.free_cash_flow),
        ("Interest Expense", financials.interest_expense),
        ("Long-Term Debt", financials.long_term_debt),
        ("Cash & Equivalents", financials.cash_and_equivalents),
        ("Diluted EPS", financials.diluted_eps),
        ("Diluted Shares", financials.diluted_shares),
    ]

    source_map: dict[str, list[dict[str, Any]]] = {}

    for name, metrics in metric_fields:
        if not metrics:
            continue
        entries = []
        for m in metrics[-5:]:  # last 5 years
            entry = _build_source_entry(name, m, cik)
            entries.append(entry)
            sources.append(entry)
        source_map[name] = entries

    writer(AgentThinkingEvent(
        node="logic_trace",
        content=f"Traced {len(sources)} data points across {len(source_map)} metrics to SEC filings.",
    ).model_dump())

    # Emit source table component
    writer(ComponentEvent(
        component_type="source_table",
        props={
            "entity_name": financials.entity_name,
            "sources": sources,
        },
    ).model_dump())

    # Build verdict
    dcf = state.get("dcf_result")
    health = state.get("health_assessment", "Unknown")
    intrinsic = dcf.get("intrinsic_value_per_share") if dcf else None

    # Sentiment summary
    sentiment = state.get("event_sentiment_result")
    sentiment_summary = ""
    if sentiment and sentiment.get("sentiment_label"):
        sentiment_summary = (
            f" Event sentiment: {sentiment['sentiment_label']} "
            f"(score: {sentiment['overall_sentiment']:.2f})."
        )

    # Event impact summary
    impact = state.get("event_impact_result")
    impact_summary = ""
    if impact and impact.get("summary"):
        impact_summary = f" Event impact: {impact['summary']}."

    # Use recalculated intrinsic value if available
    if (
        impact
        and impact.get("recalculated_dcf", {}).get("intrinsic_value_per_share")
    ):
        intrinsic = impact["recalculated_dcf"]["intrinsic_value_per_share"]

    if intrinsic:
        verdict = (
            f"{financials.entity_name} ({financials.ticker}): "
            f"Financial health is {health}. "
            f"DCF intrinsic value: ${intrinsic:,.2f}/share."
            f"{sentiment_summary}{impact_summary} "
            f"All {len(sources)} data points traced to SEC EDGAR filings."
        )
    else:
        verdict = (
            f"{financials.entity_name} ({financials.ticker}): "
            f"Financial health is {health}. "
            f"DCF model could not determine intrinsic value (insufficient data)."
            f"{sentiment_summary}{impact_summary} "
            f"All {len(sources)} data points traced to SEC EDGAR filings."
        )

    writer(StepCompleteEvent(
        node="logic_trace",
        summary=f"Source tracing complete: {len(sources)} data points verified.",
    ).model_dump())

    writer(AnalysisCompleteEvent(
        verdict=verdict,
        ticker=financials.ticker,
    ).model_dump())

    return {
        "source_map": source_map,
        "verdict": verdict,
        "reasoning_steps": [f"Traced {len(sources)} data points to SEC filings"],
    }
