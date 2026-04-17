"""Node 2: Dynamic DCF modeling.

2-stage DCF: high-growth phase (years 1-5) declining to terminal growth (years 6-10).
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.types import StreamWriter

from backend.models.agent_state import AnalysisState
from backend.models.events import AgentThinkingEvent, ComponentEvent, ErrorEvent, StepCompleteEvent
from backend.models.financial import AnnualMetric

logger = logging.getLogger(__name__)


def _fcf_cagr(fcf: list[AnnualMetric], years: int = 3) -> float | None:
    """Compute FCF CAGR over the last N years. Returns as decimal (0.15 = 15%)."""
    if len(fcf) < years + 1:
        return None
    start = fcf[-(years + 1)].value
    end = fcf[-1].value
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _estimate_wacc(
    debt: float | None,
    equity: float | None,
    interest_expense: float | None,
    risk_free_rate: float = 0.045,
    equity_risk_premium: float = 0.055,
    beta: float = 1.2,
    tax_rate: float = 0.21,
) -> float:
    """Estimate WACC from available data. Falls back to reasonable defaults."""
    cost_of_equity = risk_free_rate + beta * equity_risk_premium

    if debt and equity and interest_expense and debt > 0:
        cost_of_debt = abs(interest_expense) / debt
        total_capital = debt + equity
        wacc = (
            (equity / total_capital) * cost_of_equity
            + (debt / total_capital) * cost_of_debt * (1 - tax_rate)
        )
        return max(wacc, 0.06)  # floor at 6%

    return cost_of_equity  # fallback: all-equity


def compute_dcf(
    latest_fcf: float,
    growth_rate: float,
    terminal_growth_rate: float,
    discount_rate: float,
    projection_years: int = 10,
    shares_outstanding: float | None = None,
) -> dict[str, Any]:
    """Run the 2-stage DCF model."""
    projected_fcf: list[dict[str, Any]] = []
    high_growth_years = projection_years // 2

    for year in range(1, projection_years + 1):
        if year <= high_growth_years:
            rate = growth_rate
        else:
            # Linear decline from growth_rate to terminal_growth_rate
            fade_progress = (year - high_growth_years) / (
                projection_years - high_growth_years
            )
            rate = growth_rate + (terminal_growth_rate - growth_rate) * fade_progress

        if year == 1:
            fcf = latest_fcf * (1 + rate)
        else:
            fcf = projected_fcf[-1]["fcf"] * (1 + rate)

        discount_factor = 1 / (1 + discount_rate) ** year
        projected_fcf.append({
            "year": year,
            "fcf": round(fcf, 2),
            "growth_rate": round(rate * 100, 2),
            "discount_factor": round(discount_factor, 6),
            "present_value": round(fcf * discount_factor, 2),
        })

    # Terminal value
    terminal_fcf = projected_fcf[-1]["fcf"] * (1 + terminal_growth_rate)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
    terminal_pv = terminal_value / (1 + discount_rate) ** projection_years

    # Enterprise value
    pv_fcf_sum = sum(p["present_value"] for p in projected_fcf)
    enterprise_value = pv_fcf_sum + terminal_pv

    result = {
        "projected_fcf": projected_fcf,
        "terminal_value": round(terminal_value, 2),
        "terminal_pv": round(terminal_pv, 2),
        "pv_fcf_sum": round(pv_fcf_sum, 2),
        "enterprise_value": round(enterprise_value, 2),
        "intrinsic_value_per_share": None,
        "assumptions": {
            "growth_rate": round(growth_rate * 100, 2),
            "terminal_growth_rate": round(terminal_growth_rate * 100, 2),
            "discount_rate": round(discount_rate * 100, 2),
            "projection_years": projection_years,
            "latest_fcf": round(latest_fcf, 2),
        },
    }

    if shares_outstanding and shares_outstanding > 0:
        result["intrinsic_value_per_share"] = round(
            enterprise_value / shares_outstanding, 2
        )

    return result


async def dcf_node(
    state: AnalysisState, writer: StreamWriter
) -> dict[str, Any]:
    financials = state["financials"]
    if financials is None:
        writer(ErrorEvent(
            message="DCF modeling skipped: no financial data available.",
            recoverable=False,
        ).model_dump())
        return {"dcf_result": None, "reasoning_steps": ["ERROR: No financial data for DCF"]}

    try:
        return _run_dcf(financials, writer)
    except Exception as e:
        logger.exception("DCF modeling failed for %s", financials.ticker)
        writer(ErrorEvent(
            message="DCF modeling encountered an internal error.",
            recoverable=False,
        ).model_dump())
        return {"dcf_result": None, "reasoning_steps": [f"ERROR: DCF failed - {e}"]}


def _run_dcf(financials: Any, writer: StreamWriter) -> dict[str, Any]:
    writer(AgentThinkingEvent(
        node="dynamic_dcf",
        content="Building DCF model from historical free cash flow...",
    ).model_dump())

    reasoning: list[str] = []
    fcf = financials.free_cash_flow

    if not fcf:
        writer(AgentThinkingEvent(
            node="dynamic_dcf",
            content="Warning: No free cash flow data available. Cannot build DCF model.",
        ).model_dump())
        return {
            "dcf_result": None,
            "reasoning_steps": ["DCF: insufficient FCF data"],
        }

    latest_fcf = fcf[-1].value
    reasoning.append(f"Latest FCF: ${latest_fcf:,.0f}")

    # Determine growth rate from historical CAGR
    growth_3yr = _fcf_cagr(fcf, 3)
    growth_5yr = _fcf_cagr(fcf, 5)

    if growth_3yr is not None and growth_5yr is not None:
        raw_growth = growth_3yr * 0.6 + growth_5yr * 0.4  # weight recent more
    elif growth_3yr is not None:
        raw_growth = growth_3yr
    elif growth_5yr is not None:
        raw_growth = growth_5yr
    else:
        raw_growth = 0.10  # fallback 10%

    # Cap growth rate at 30%
    growth_rate = min(max(raw_growth, 0.02), 0.30)
    reasoning.append(f"Estimated growth rate: {growth_rate * 100:.1f}% (capped at 30%)")

    writer(AgentThinkingEvent(
        node="dynamic_dcf",
        content=f"FCF growth rate: {growth_rate * 100:.1f}% (3yr CAGR: {growth_3yr * 100:.1f}% weighted with 5yr)" if growth_3yr else f"FCF growth rate: {growth_rate * 100:.1f}%",
    ).model_dump())

    # Estimate WACC
    debt = financials.long_term_debt[-1].value if financials.long_term_debt else None
    equity = financials.stockholders_equity[-1].value if financials.stockholders_equity else None
    interest = financials.interest_expense[-1].value if financials.interest_expense else None

    discount_rate = _estimate_wacc(debt, equity, interest)
    terminal_growth = 0.03

    reasoning.append(f"WACC (discount rate): {discount_rate * 100:.1f}%")

    writer(AgentThinkingEvent(
        node="dynamic_dcf",
        content=f"Estimated WACC: {discount_rate * 100:.1f}%. Terminal growth: {terminal_growth * 100:.1f}%.",
    ).model_dump())

    # Shares outstanding
    shares = financials.diluted_shares[-1].value if financials.diluted_shares else None

    # Run DCF
    dcf_result = compute_dcf(
        latest_fcf=latest_fcf,
        growth_rate=growth_rate,
        terminal_growth_rate=terminal_growth,
        discount_rate=discount_rate,
        shares_outstanding=shares,
    )

    if dcf_result["intrinsic_value_per_share"]:
        reasoning.append(
            f"Intrinsic value per share: ${dcf_result['intrinsic_value_per_share']:,.2f}"
        )
        writer(AgentThinkingEvent(
            node="dynamic_dcf",
            content=f"DCF intrinsic value: ${dcf_result['intrinsic_value_per_share']:,.2f} per share",
        ).model_dump())

    # Emit FCF chart
    historical_fcf = [
        {"year": m.calendar_year, "fcf": m.value, "type": "historical"}
        for m in fcf
    ]
    projected_fcf = [
        {
            "year": fcf[-1].calendar_year + p["year"],
            "fcf": p["fcf"],
            "type": "projected",
        }
        for p in dcf_result["projected_fcf"]
    ]
    writer(ComponentEvent(
        component_type="fcf_chart",
        props={
            "entity_name": financials.entity_name,
            "data": historical_fcf + projected_fcf,
        },
    ).model_dump())

    # Emit DCF result card
    writer(ComponentEvent(
        component_type="dcf_result_card",
        props={
            "entity_name": financials.entity_name,
            "intrinsic_value_per_share": dcf_result["intrinsic_value_per_share"],
            "enterprise_value": dcf_result["enterprise_value"],
            "terminal_value": dcf_result["terminal_value"],
            "pv_fcf_sum": dcf_result["pv_fcf_sum"],
            "assumptions": dcf_result["assumptions"],
        },
    ).model_dump())

    # Emit valuation gauge
    if dcf_result["intrinsic_value_per_share"]:
        writer(ComponentEvent(
            component_type="valuation_gauge",
            props={
                "intrinsic_value": dcf_result["intrinsic_value_per_share"],
                "entity_name": financials.entity_name,
            },
        ).model_dump())

    # Emit assumption slider for interactive recalculation
    writer(ComponentEvent(
        component_type="assumption_slider",
        props={
            "ticker": financials.ticker,
            "growth_rate": dcf_result["assumptions"]["growth_rate"],
            "terminal_growth_rate": dcf_result["assumptions"]["terminal_growth_rate"],
            "discount_rate": dcf_result["assumptions"]["discount_rate"],
        },
    ).model_dump())

    writer(StepCompleteEvent(
        node="dynamic_dcf",
        summary=f"DCF complete. Intrinsic value: ${dcf_result.get('intrinsic_value_per_share', 'N/A')} per share.",
    ).model_dump())

    return {
        "dcf_result": dcf_result,
        "reasoning_steps": reasoning,
    }
