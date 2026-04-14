"""Node 1: Financial health scan.

Computes key financial ratios and emits health assessment components.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import StreamWriter

from backend.models.agent_state import AnalysisState
from backend.models.events import AgentThinkingEvent, ComponentEvent, ErrorEvent, StepCompleteEvent
from backend.models.financial import AnnualMetric


def _safe_divide(a: float, b: float) -> float | None:
    return a / b if b != 0 else None


def _cagr(start: float, end: float, years: int) -> float | None:
    if start <= 0 or end <= 0 or years <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _latest(metrics: list[AnnualMetric]) -> float | None:
    return metrics[-1].value if metrics else None


def _compute_margins(
    financials: Any,
) -> dict[str, list[dict[str, Any]]]:
    """Compute margin time series over available years."""
    revenue_by_year = {m.calendar_year: m.value for m in financials.revenue}
    margins: dict[str, list[dict[str, Any]]] = {
        "gross_margin": [],
        "operating_margin": [],
        "net_margin": [],
    }

    for m in financials.cost_of_revenue:
        rev = revenue_by_year.get(m.calendar_year)
        if rev and rev > 0:
            margins["gross_margin"].append({
                "year": m.calendar_year,
                "value": round((rev - m.value) / rev * 100, 2),
            })

    for m in financials.operating_income:
        rev = revenue_by_year.get(m.calendar_year)
        if rev and rev > 0:
            margins["operating_margin"].append({
                "year": m.calendar_year,
                "value": round(m.value / rev * 100, 2),
            })

    for m in financials.net_income:
        rev = revenue_by_year.get(m.calendar_year)
        if rev and rev > 0:
            margins["net_margin"].append({
                "year": m.calendar_year,
                "value": round(m.value / rev * 100, 2),
            })

    return margins


async def financial_health_node(
    state: AnalysisState, writer: StreamWriter
) -> dict[str, Any]:
    financials = state["financials"]
    if financials is None:
        writer(ErrorEvent(
            message="Financial health scan skipped: no financial data available.",
            recoverable=False,
        ).model_dump())
        return {"health_metrics": None, "health_assessment": None, "reasoning_steps": ["ERROR: No financial data for health scan"]}

    try:
        return _run_financial_health(financials, writer)
    except Exception as e:
        writer(ErrorEvent(
            message=f"Financial health scan failed: {e}",
            recoverable=False,
        ).model_dump())
        return {"health_metrics": None, "health_assessment": None, "reasoning_steps": [f"ERROR: Financial health scan failed - {e}"]}


def _run_financial_health(financials: Any, writer: StreamWriter) -> dict[str, Any]:
    writer(AgentThinkingEvent(
        node="financial_health_scan",
        content=f"Analyzing financial health for {financials.entity_name}...",
    ).model_dump())

    metrics: dict[str, Any] = {}
    reasoning: list[str] = []

    # Interest coverage ratio
    op_income = _latest(financials.operating_income)
    interest = _latest(financials.interest_expense)
    if op_income is not None and interest is not None:
        icr = _safe_divide(op_income, abs(interest))
        metrics["interest_coverage_ratio"] = round(icr, 2) if icr else None
        if icr:
            reasoning.append(
                f"Interest coverage ratio: {icr:.2f}x "
                f"({'Strong' if icr > 5 else 'Moderate' if icr > 2 else 'Weak'})"
            )
    else:
        metrics["interest_coverage_ratio"] = None
        reasoning.append("Interest coverage ratio: data unavailable")

    writer(AgentThinkingEvent(
        node="financial_health_scan",
        content=reasoning[-1],
    ).model_dump())

    # Debt to equity
    liabilities = _latest(financials.total_liabilities)
    equity = _latest(financials.stockholders_equity)
    if liabilities is not None and equity is not None:
        de = _safe_divide(liabilities, equity)
        metrics["debt_to_equity"] = round(de, 2) if de else None
        if de:
            reasoning.append(f"Debt-to-equity: {de:.2f} ({'Conservative' if de < 1 else 'Leveraged' if de < 2 else 'Highly leveraged'})")
    else:
        metrics["debt_to_equity"] = None

    # Margins
    margins = _compute_margins(financials)
    metrics["margins"] = margins
    if margins["net_margin"]:
        latest_nm = margins["net_margin"][-1]["value"]
        reasoning.append(f"Net margin: {latest_nm:.1f}%")
        writer(AgentThinkingEvent(
            node="financial_health_scan",
            content=f"Net margin: {latest_nm:.1f}%",
        ).model_dump())

    # Revenue CAGR (3yr and 5yr)
    rev = financials.revenue
    if len(rev) >= 4:
        cagr_3 = _cagr(rev[-4].value, rev[-1].value, 3)
        metrics["revenue_cagr_3yr"] = round(cagr_3 * 100, 2) if cagr_3 else None
        if cagr_3:
            reasoning.append(f"Revenue CAGR (3yr): {cagr_3 * 100:.1f}%")
    if len(rev) >= 6:
        cagr_5 = _cagr(rev[-6].value, rev[-1].value, 5)
        metrics["revenue_cagr_5yr"] = round(cagr_5 * 100, 2) if cagr_5 else None
        if cagr_5:
            reasoning.append(f"Revenue CAGR (5yr): {cagr_5 * 100:.1f}%")

    # ROE
    ni = _latest(financials.net_income)
    if ni is not None and equity is not None:
        roe = _safe_divide(ni, equity)
        metrics["roe"] = round(roe * 100, 2) if roe else None
        if roe:
            reasoning.append(f"ROE: {roe * 100:.1f}%")

    # Overall assessment
    assessment = "Strong"
    icr_val = metrics.get("interest_coverage_ratio")
    de_val = metrics.get("debt_to_equity")
    if icr_val is not None and icr_val < 2:
        assessment = "Weak"
    elif de_val is not None and de_val > 3:
        assessment = "Weak"
    elif icr_val is not None and icr_val < 5:
        assessment = "Moderate"

    writer(AgentThinkingEvent(
        node="financial_health_scan",
        content=f"Overall financial health assessment: {assessment}",
    ).model_dump())

    # Emit financial health card component
    writer(ComponentEvent(
        component_type="financial_health_card",
        props={
            "entity_name": financials.entity_name,
            "assessment": assessment,
            "interest_coverage_ratio": metrics.get("interest_coverage_ratio"),
            "debt_to_equity": metrics.get("debt_to_equity"),
            "roe": metrics.get("roe"),
            "revenue_cagr_3yr": metrics.get("revenue_cagr_3yr"),
            "revenue_cagr_5yr": metrics.get("revenue_cagr_5yr"),
            "margins": margins,
        },
    ).model_dump())

    # Emit revenue chart
    if financials.revenue:
        writer(ComponentEvent(
            component_type="revenue_chart",
            props={
                "entity_name": financials.entity_name,
                "data": [
                    {"year": m.calendar_year, "revenue": m.value}
                    for m in financials.revenue
                ],
            },
        ).model_dump())

    writer(StepCompleteEvent(
        node="financial_health_scan",
        summary=f"Financial health: {assessment}. " + "; ".join(reasoning[-3:]),
    ).model_dump())

    return {
        "health_metrics": metrics,
        "health_assessment": assessment,
        "reasoning_steps": reasoning,
    }
