"""Node: Strategy analysis — margin of safety, P/E percentile, entry signal."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.types import StreamWriter

from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    ErrorEvent,
    StepCompleteEvent,
)
from backend.services.market_data import market_data_client

logger = logging.getLogger(__name__)


def _determine_signal(margin_of_safety_pct: float) -> str:
    if margin_of_safety_pct > 25:
        return "Deep Value"
    if margin_of_safety_pct > 10:
        return "Undervalued"
    if margin_of_safety_pct > -10:
        return "Fair Value"
    return "Overvalued"


async def strategy_node(
    state: AnalysisState, writer: StreamWriter
) -> dict[str, Any]:
    financials = state["financials"]
    dcf = state["dcf_result"]

    if not financials or not dcf or not dcf.get("intrinsic_value_per_share"):
        writer(AgentThinkingEvent(
            node="strategy",
            content="Strategy analysis requires a valid DCF intrinsic value. Skipping.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="strategy",
            summary="Strategy skipped: no intrinsic value available.",
        ).model_dump())
        return {
            "strategy_result": None,
            "reasoning_steps": ["Strategy: skipped — no intrinsic value"],
        }

    try:
        rel_val = state.get("relative_valuation_result")
        sentiment_result = state.get("event_sentiment_result")
        event_impact_result = state.get("event_impact_result")
        return await _run_strategy(financials, dcf, rel_val, sentiment_result, event_impact_result, writer)
    except Exception as e:
        logger.exception("Strategy analysis failed for %s", financials.ticker if financials else "unknown")
        writer(ErrorEvent(
            message="Strategy analysis encountered an internal error.",
            recoverable=True,
        ).model_dump())
        writer(StepCompleteEvent(
            node="strategy",
            summary="Strategy analysis encountered an error.",
        ).model_dump())
        return {
            "strategy_result": None,
            "reasoning_steps": ["Strategy: error — analysis interrupted"],
        }


async def _run_strategy(
    financials: Any, dcf: dict[str, Any],
    relative_valuation_result: dict[str, Any] | None,
    event_sentiment_result: dict[str, Any] | None,
    event_impact_result: dict[str, Any] | None,
    writer: StreamWriter,
) -> dict[str, Any]:
    # Use recalculated DCF intrinsic value if available
    intrinsic: float = dcf["intrinsic_value_per_share"]
    ticker = financials.ticker
    reasoning: list[str] = []

    if (
        event_impact_result
        and event_impact_result.get("recalculated_dcf", {}).get("intrinsic_value_per_share")
    ):
        intrinsic = event_impact_result["recalculated_dcf"]["intrinsic_value_per_share"]
        reasoning.append("Using event-impact-adjusted DCF intrinsic value")

    # --- Get current market price (reuse from relative_valuation if available) ---
    writer(AgentThinkingEvent(
        node="strategy",
        content=f"Fetching current market price for {ticker}...",
    ).model_dump())

    current_price: float | None = None
    if relative_valuation_result and relative_valuation_result.get("price_available"):
        current_price = relative_valuation_result.get("current_price")
    if current_price is None or current_price <= 0:
        current_price = await market_data_client.get_current_price(ticker)

    if current_price is None or current_price <= 0:
        writer(AgentThinkingEvent(
            node="strategy",
            content="Could not fetch market price. Strategy analysis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="strategy",
            summary="Strategy skipped: market data unavailable.",
        ).model_dump())
        return {
            "strategy_result": None,
            "reasoning_steps": ["Strategy: skipped — market data unavailable"],
        }

    reasoning.append(f"Current market price: ${current_price:.2f}")

    # --- Margin of Safety ---
    mos_pct = (intrinsic - current_price) / intrinsic * 100
    suggested_entry = round(intrinsic * 0.85, 2)
    upside_pct = (intrinsic - current_price) / current_price * 100
    signal = _determine_signal(mos_pct)

    reasoning.append(f"Margin of safety: {mos_pct:.1f}%")
    reasoning.append(f"Signal: {signal}")

    writer(AgentThinkingEvent(
        node="strategy",
        content=(
            f"Price ${current_price:.2f} vs intrinsic ${intrinsic:.2f} — "
            f"margin of safety {mos_pct:.1f}%. Signal: {signal}"
        ),
    ).model_dump())

    # --- P/E Percentile ---
    writer(AgentThinkingEvent(
        node="strategy",
        content="Computing historical P/E percentile...",
    ).model_dump())

    annual_prices: dict[int, float] = {}
    if relative_valuation_result and relative_valuation_result.get("annual_prices"):
        annual_prices = relative_valuation_result["annual_prices"]
    if not annual_prices:
        annual_prices = await market_data_client.get_annual_closing_prices(ticker, years=10)
    eps_by_year = {m.calendar_year: m.value for m in financials.diluted_eps}

    historical_pe: list[dict[str, Any]] = []
    for year in sorted(set(annual_prices.keys()) & set(eps_by_year.keys())):
        eps = eps_by_year[year]
        if eps > 0:
            pe = annual_prices[year] / eps
            historical_pe.append({"year": year, "pe": round(pe, 1)})

    current_pe: float | None = None
    pe_percentile: float | None = None
    latest_eps = financials.diluted_eps[-1].value if financials.diluted_eps else None

    if latest_eps and latest_eps > 0:
        current_pe = round(current_price / latest_eps, 1)
        reasoning.append(f"Current P/E: {current_pe}")

        if len(historical_pe) >= 3:
            pe_values = sorted(h["pe"] for h in historical_pe)
            rank = sum(1 for v in pe_values if v <= current_pe)
            pe_percentile = round(rank / len(pe_values) * 100, 1)
            reasoning.append(
                f"P/E at {pe_percentile:.0f}th percentile over {len(pe_values)} years"
            )
            writer(AgentThinkingEvent(
                node="strategy",
                content=f"Current P/E {current_pe} at {pe_percentile:.0f}th percentile ({len(pe_values)} years of data)",
            ).model_dump())
        else:
            writer(AgentThinkingEvent(
                node="strategy",
                content=f"Current P/E: {current_pe}. Insufficient historical data for percentile.",
            ).model_dump())
    else:
        writer(AgentThinkingEvent(
            node="strategy",
            content="EPS is negative or unavailable — P/E percentile not computed.",
        ).model_dump())

    # --- Relative valuation cross-check ---
    relative_signal_note = ""
    if relative_valuation_result and relative_valuation_result.get("price_available"):
        peer_comp = relative_valuation_result.get("peer_comparison")
        deltas = peer_comp.get("deltas", {}) if peer_comp and peer_comp.get("peer_data_available") else {}
        pe_delta = deltas.get("pe")
        if pe_delta is not None:
            if pe_delta < -20:
                relative_signal_note = "P/E significantly below peers, supporting undervaluation thesis."
                reasoning.append(f"Relative valuation: {relative_signal_note}")
            elif pe_delta > 20:
                relative_signal_note = "P/E significantly above peers — valuation premium warrants caution."
                reasoning.append(f"Relative valuation: {relative_signal_note}")
            else:
                reasoning.append("Relative valuation: P/E roughly in line with peers.")

        if relative_signal_note:
            writer(AgentThinkingEvent(
                node="strategy",
                content=relative_signal_note,
            ).model_dump())

    # --- Sentiment adjustment ---
    sentiment_delta = 0.0
    sentiment_note = ""
    sentiment = event_sentiment_result
    if sentiment and sentiment.get("sentiment_adjustment"):
        adj = sentiment["sentiment_adjustment"]
        sentiment_delta = adj.get("margin_of_safety_pct_delta", 0)
        sentiment_note = adj.get("reasoning", "")
        if sentiment_delta != 0:
            adjusted_mos = mos_pct + sentiment_delta
            reasoning.append(
                f"Sentiment adjustment: {sentiment_note} (Δ{sentiment_delta:+.0f}%)"
            )
            writer(AgentThinkingEvent(
                node="strategy",
                content=(
                    f"Margin of safety adjusted by {sentiment_delta:+.0f}% "
                    f"due to sentiment ({sentiment.get('sentiment_label', 'N/A')}). "
                    f"Adjusted MoS: {adjusted_mos:.1f}%"
                ),
            ).model_dump())

    # --- Emit strategy dashboard ---
    strategy_result = {
        "current_price": current_price,
        "intrinsic_value": intrinsic,
        "margin_of_safety_pct": round(mos_pct, 1),
        "suggested_entry_price": suggested_entry,
        "upside_pct": round(upside_pct, 1),
        "signal": signal,
        "current_pe": current_pe,
        "pe_percentile": pe_percentile,
        "historical_pe": historical_pe if historical_pe else None,
        "sentiment_delta": sentiment_delta,
        "sentiment_note": sentiment_note,
    }

    writer(ComponentEvent(
        component_type="strategy_dashboard",
        props={
            "entity_name": financials.entity_name,
            "ticker": ticker,
            **strategy_result,
        },
    ).model_dump())

    writer(StepCompleteEvent(
        node="strategy",
        summary=f"Entry strategy: {signal}. Margin of safety: {mos_pct:.1f}%. Price: ${current_price:.2f} vs intrinsic: ${intrinsic:.2f}.",
    ).model_dump())

    return {
        "strategy_result": strategy_result,
        "reasoning_steps": reasoning,
    }
