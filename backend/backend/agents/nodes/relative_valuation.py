"""Node: Relative valuation — market multiples vs history and peers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langgraph.types import StreamWriter

from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    StepCompleteEvent,
)
from backend.services.market_data import market_data_client
from backend.agents.nodes.industry_mapping import (
    recommended_multiples,
    static_explainer,
)
from backend.agents.nodes.relative_valuation_math import (
    compute_current_multiples,
    compute_historical_multiples,
    median,
    percentile_rank,
)

logger = logging.getLogger(__name__)


async def _fetch_peer_data(
    ticker: str, writer: StreamWriter,
) -> dict[str, Any] | None:
    """Fetch peer tickers and their key metrics via FMP."""
    writer(AgentThinkingEvent(
        node="relative_valuation",
        content=f"Fetching peer companies for {ticker}...",
    ).model_dump())

    peers = await market_data_client.get_peers(ticker)
    if not peers:
        writer(AgentThinkingEvent(
            node="relative_valuation",
            content="No peer data available. Skipping peer comparison.",
        ).model_dump())
        return {"peer_data_available": False}

    writer(AgentThinkingEvent(
        node="relative_valuation",
        content=f"Found {len(peers)} peers: {', '.join(peers[:5])}{'...' if len(peers) > 5 else ''}. Fetching metrics...",
    ).model_dump())

    peer_metrics = await market_data_client.get_batch_peer_metrics(peers)

    metric_keys = [
        "peRatio", "pbRatio", "priceToSalesRatio",
        "evToRevenue", "evToFreeCashFlow", "pegRatio",
    ]
    peer_medians: dict[str, float | None] = {}
    for key in metric_keys:
        values = [
            v[key]
            for v in peer_metrics.values()
            if v.get(key) is not None
        ]
        peer_medians[key] = round(median(values), 2) if values else None

    peer_table: list[dict[str, Any]] = []
    for peer, metrics in peer_metrics.items():
        row: dict[str, Any] = {"ticker": peer}
        for key in metric_keys:
            val = metrics.get(key)
            row[key] = round(val, 2) if val is not None else None
        peer_table.append(row)

    return {
        "peer_data_available": True,
        "peers": peers,
        "peer_medians": peer_medians,
        "peer_table": peer_table,
    }


async def relative_valuation_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    """Compute relative valuation: current multiples, historical percentiles, peer comparison."""
    financials = state["financials"]
    if financials is None:
        return {
            "relative_valuation_result": None,
            "reasoning_steps": ["Relative valuation: skipped — no financial data"],
        }

    try:
        return await _run_relative_valuation(financials, writer)
    except Exception:
        logger.exception("Relative valuation failed for %s", financials.ticker)
        writer(AgentThinkingEvent(
            node="relative_valuation",
            content="Relative valuation encountered an internal error.",
        ).model_dump())
        return {
            "relative_valuation_result": None,
            "reasoning_steps": ["Relative valuation: error — analysis interrupted"],
        }


async def _run_relative_valuation(
    financials: Any, writer: StreamWriter,
) -> dict[str, Any]:
    ticker = financials.ticker
    reasoning: list[str] = []

    # --- Fetch price and company profile in parallel ---
    # /stable/quote is premium-gated for some tickers on the FMP free tier,
    # while /stable/profile returns a price field that works for all symbols.
    # Use quote first and fall back to profile.price.
    current_price, profile = await asyncio.gather(
        market_data_client.get_current_price(ticker),
        market_data_client.get_company_profile(ticker),
    )
    if current_price is None or current_price <= 0:
        current_price = profile.get("price")
    sector = profile.get("sector")
    industry = profile.get("industry")
    last_dividend = profile.get("last_dividend")

    sector_label = f" ({sector}{' / ' + industry if industry else ''})" if sector else ""
    writer(AgentThinkingEvent(
        node="relative_valuation",
        content=f"Computing relative valuation for {financials.entity_name}{sector_label}...",
    ).model_dump())

    if current_price is None or current_price <= 0:
        writer(AgentThinkingEvent(
            node="relative_valuation",
            content="Market price unavailable (FMP API key not set or request failed). Multiples requiring price data will be skipped.",
        ).model_dump())
        result: dict[str, Any] = {
            "price_available": False,
            "peer_data_available": False,
            "sector": sector,
            "industry": industry,
            "current_multiples": {},
            "historical_stats": {},
            "percentiles": {},
            "peer_comparison": None,
        }
        return {
            "relative_valuation_result": result,
            "reasoning_steps": ["Relative valuation: market price unavailable"],
        }

    # --- Industry-based recommendation ---
    recommendation = recommended_multiples(sector, industry)
    industry_explanation = static_explainer(sector, industry, {})
    if sector:
        reasoning.append(
            f"Industry: {sector}"
            + (f" / {industry}" if industry else "")
            + f" — recommended multiples: {', '.join(recommendation['recommended'])}"
        )

    # --- Current multiples ---
    current = compute_current_multiples(financials, current_price, last_dividend=last_dividend)
    current_multiples = current.get("multiples", {})
    reasoning.append(f"Market cap: ${current.get('market_cap', 0):,.0f}")
    reasoning.append(f"Enterprise value: ${current.get('enterprise_value', 0):,.0f}")

    writer(AgentThinkingEvent(
        node="relative_valuation",
        content=(
            f"Market cap: ${current.get('market_cap', 0):,.0f} | "
            f"EV: ${current.get('enterprise_value', 0):,.0f} | "
            f"P/E: {current_multiples.get('pe', 'N/A')} | "
            f"P/B: {current_multiples.get('pb', 'N/A')} | "
            f"P/S: {current_multiples.get('ps', 'N/A')}"
        ),
    ).model_dump())

    # --- Historical multiples ---
    annual_prices = await market_data_client.get_annual_closing_prices(ticker, years=10)
    historical_stats: dict[str, Any] = {}
    percentiles: dict[str, float | None] = {}

    if annual_prices:
        historical_stats = compute_historical_multiples(financials, annual_prices)

        multiple_key_map = {
            "pe": "pe", "pb": "pb", "ps": "ps",
            "ev_to_revenue": "ev_to_revenue", "ev_to_ebit": "ev_to_ebit",
            "p_ffo": "p_ffo",
        }
        for hist_key, current_key in multiple_key_map.items():
            hist_stat = historical_stats.get(hist_key, {})
            series_values = [e["value"] for e in hist_stat.get("series", [])]
            current_val = current_multiples.get(current_key)
            if current_val is not None and series_values:
                percentiles[current_key] = percentile_rank(current_val, series_values)
            else:
                percentiles[current_key] = None

        if percentiles.get("pe") is not None:
            reasoning.append(f"P/E at {percentiles['pe']:.0f}th historical percentile")

        writer(AgentThinkingEvent(
            node="relative_valuation",
            content=f"Historical multiples computed over {len(annual_prices)} years of price data.",
        ).model_dump())
    else:
        writer(AgentThinkingEvent(
            node="relative_valuation",
            content="No historical price data available for historical multiples.",
        ).model_dump())

    # --- Peer comparison ---
    peer_comparison = await _fetch_peer_data(ticker, writer)

    deltas: dict[str, float | None] = {}
    if peer_comparison and peer_comparison.get("peer_data_available"):
        fmp_key_map = {
            "pe": "peRatio", "pb": "pbRatio",
            "ps": "priceToSalesRatio", "ev_to_revenue": "evToRevenue",
        }
        peer_medians = peer_comparison.get("peer_medians", {})
        for current_key, fmp_key in fmp_key_map.items():
            company_val = current_multiples.get(current_key)
            peer_med = peer_medians.get(fmp_key)
            if company_val is not None and peer_med is not None and peer_med != 0:
                deltas[current_key] = round(
                    (company_val - peer_med) / abs(peer_med) * 100, 1
                )
            else:
                deltas[current_key] = None

        peer_comparison = {**peer_comparison, "deltas": deltas}

        delta_desc = ", ".join(
            f"{k}: {v:+.0f}%" for k, v in deltas.items() if v is not None
        )
        if delta_desc:
            reasoning.append(f"vs peer median — {delta_desc}")
            writer(AgentThinkingEvent(
                node="relative_valuation",
                content=f"Peer comparison deltas: {delta_desc}",
            ).model_dump())

    # --- Build result ---
    result = {
        "price_available": True,
        "current_price": current_price,
        "annual_prices": annual_prices,
        "market_cap": current.get("market_cap"),
        "enterprise_value": current.get("enterprise_value"),
        "current_multiples": current_multiples,
        "historical_stats": historical_stats,
        "percentiles": percentiles,
        "peer_comparison": peer_comparison,
        "sector": sector,
        "industry": industry,
        "recommended_multiples": recommendation["recommended"],
        "industry_explanation": industry_explanation,
        "dividend_yield": current_multiples.get("dividend_yield"),
    }

    writer(ComponentEvent(
        component_type="relative_valuation_card",
        props={"entity_name": financials.entity_name, "ticker": ticker, **result},
    ).model_dump())

    writer(StepCompleteEvent(
        node="relative_valuation",
        summary=(
            f"Relative valuation complete. "
            f"P/E: {current_multiples.get('pe', 'N/A')}, "
            f"P/B: {current_multiples.get('pb', 'N/A')}, "
            f"P/S: {current_multiples.get('ps', 'N/A')}."
        ),
    ).model_dump())

    return {
        "relative_valuation_result": result,
        "reasoning_steps": reasoning,
    }
