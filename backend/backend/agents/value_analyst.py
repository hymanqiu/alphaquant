"""LangGraph value analyst workflow.

Orchestrates: fetch_sec_data -> financial_health_scan -> dynamic_dcf -> relative_valuation -> strategy -> logic_trace
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import StreamWriter

from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    AnalysisCompleteEvent,
    ComponentEvent,
    ErrorEvent,
    StepCompleteEvent,
)
from backend.services.sec_agent import sec_data_service
from backend.services.ticker_resolver import TickerNotFoundError

from .nodes.dcf_model import dcf_node
from .nodes.financial_health import financial_health_node
from .nodes.logic_trace import logic_trace_node
from .nodes.relative_valuation import relative_valuation_node
from .nodes.strategy import strategy_node


async def fetch_sec_data_node(
    state: AnalysisState, writer: StreamWriter
) -> dict[str, Any]:
    """Fetch and normalize SEC EDGAR data for the given ticker."""
    ticker = state["ticker"]

    writer(AgentThinkingEvent(
        node="fetch_sec_data",
        content=f"Fetching SEC EDGAR filing data for {ticker}...",
    ).model_dump())

    try:
        financials = await sec_data_service.get_financials(ticker)
    except TickerNotFoundError:
        writer(ErrorEvent(
            message=f"Ticker '{ticker}' not found in SEC database.",
            recoverable=False,
        ).model_dump())
        writer(AnalysisCompleteEvent(
            verdict=f"Analysis failed: ticker '{ticker}' not found in SEC database.",
            ticker=ticker,
        ).model_dump())
        return {
            "financials": None,
            "fetch_errors": [f"Ticker not found: {ticker}"],
            "reasoning_steps": [f"ERROR: Ticker '{ticker}' not found"],
        }
    except Exception as e:
        writer(ErrorEvent(
            message=f"Failed to fetch SEC data: {str(e)}",
            recoverable=False,
        ).model_dump())
        writer(AnalysisCompleteEvent(
            verdict=f"Analysis failed: could not fetch SEC data for {ticker}.",
            ticker=ticker,
        ).model_dump())
        return {
            "financials": None,
            "fetch_errors": [str(e)],
            "reasoning_steps": [f"ERROR: SEC fetch failed - {e}"],
        }

    writer(AgentThinkingEvent(
        node="fetch_sec_data",
        content=f"Successfully loaded data for {financials.entity_name} (CIK: {financials.cik})",
    ).model_dump())

    # Emit initial metric table
    metrics_summary = []
    if financials.revenue:
        r = financials.revenue[-1]
        metrics_summary.append({
            "label": "Latest Revenue",
            "value": f"${r.value:,.0f}",
            "year": r.calendar_year,
            "source": r.sec_accession,
        })
    if financials.net_income:
        ni = financials.net_income[-1]
        metrics_summary.append({
            "label": "Latest Net Income",
            "value": f"${ni.value:,.0f}",
            "year": ni.calendar_year,
            "source": ni.sec_accession,
        })
    if financials.free_cash_flow:
        fcf = financials.free_cash_flow[-1]
        metrics_summary.append({
            "label": "Latest Free Cash Flow",
            "value": f"${fcf.value:,.0f}",
            "year": fcf.calendar_year,
            "source": fcf.sec_accession,
        })
    if financials.total_assets:
        ta = financials.total_assets[-1]
        metrics_summary.append({
            "label": "Total Assets",
            "value": f"${ta.value:,.0f}",
            "year": ta.calendar_year,
            "source": ta.sec_accession,
        })
    if financials.diluted_eps:
        eps = financials.diluted_eps[-1]
        metrics_summary.append({
            "label": "Diluted EPS",
            "value": f"${eps.value:.2f}",
            "year": eps.calendar_year,
            "source": eps.sec_accession,
        })

    if metrics_summary:
        writer(ComponentEvent(
            component_type="metric_table",
            props={
                "title": f"{financials.entity_name} - Key Financial Metrics",
                "metrics": metrics_summary,
            },
        ).model_dump())

    # Count available data series
    available = sum(
        1
        for field in [
            financials.revenue, financials.net_income, financials.operating_income,
            financials.free_cash_flow, financials.total_assets,
        ]
        if field
    )
    missing_fields = []
    if not financials.revenue:
        missing_fields.append("Revenue")
    if not financials.free_cash_flow:
        missing_fields.append("Free Cash Flow")

    if missing_fields:
        writer(AgentThinkingEvent(
            node="fetch_sec_data",
            content=f"Warning: Missing data for {', '.join(missing_fields)}",
        ).model_dump())

    writer(StepCompleteEvent(
        node="fetch_sec_data",
        summary=f"Loaded {available} financial data series for {financials.entity_name}",
    ).model_dump())

    return {
        "financials": financials,
        "fetch_errors": [],
        "reasoning_steps": [
            f"Fetched SEC data for {financials.entity_name}",
            f"Available data series: {available}",
        ],
    }


def _should_continue(state: AnalysisState) -> str:
    if state["financials"] is None:
        return "error"
    return "continue"


def build_value_analyst_graph() -> StateGraph:
    """Build and return the value analyst LangGraph StateGraph."""
    graph = StateGraph(AnalysisState)

    graph.add_node("fetch_sec_data", fetch_sec_data_node)
    graph.add_node("financial_health_scan", financial_health_node)
    graph.add_node("dynamic_dcf", dcf_node)
    graph.add_node("relative_valuation", relative_valuation_node)
    graph.add_node("strategy", strategy_node)
    graph.add_node("logic_trace", logic_trace_node)

    graph.add_edge(START, "fetch_sec_data")
    graph.add_conditional_edges(
        "fetch_sec_data",
        _should_continue,
        {"continue": "financial_health_scan", "error": END},
    )
    graph.add_edge("financial_health_scan", "dynamic_dcf")
    graph.add_edge("dynamic_dcf", "relative_valuation")
    graph.add_edge("relative_valuation", "strategy")
    graph.add_edge("strategy", "logic_trace")
    graph.add_edge("logic_trace", END)

    return graph
