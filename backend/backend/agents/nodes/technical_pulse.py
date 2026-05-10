"""Technical Pulse node — node 13 of the value-analyst graph.

Produces a 1Y technical-indicator + market + sentiment snapshot, packaged for
the frontend's Pulse tab. Free-tier accessible (no LLM calls; the whole tab is
deterministic + rule-based, see ADR-013).

Concurrent data fetches: ticker OHLCV is awaited first (a hard prerequisite —
its failure short-circuits the node). Everything else (SPY history, company
profile, market quotes, insider txns, F&G index) is gathered in parallel.
The sector-ETF quote is sequential since the symbol depends on profile.sector.
All fetchers swallow httpx errors internally and return sentinel values, so
``asyncio.gather`` with default semantics is safe.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from langgraph.types import StreamWriter

from backend.config import settings
from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    ErrorEvent,
    StepCompleteEvent,
)
from backend.models.technicals import (
    MarketContext,
    SentimentSignals,
    TechnicalPulse,
)
from backend.services.market_data import market_data_client
from backend.services.technicals_data import (
    fetch_fear_greed,
    fetch_history,
    fetch_insider_net_90d,
    fetch_quote,
    sector_to_etf,
)

from .technical_pulse_math import (
    bullish_pct,
    build_indicator_grid,
    composite_score,
    detect_signals,
    signal_label,
    sma,
)

logger = logging.getLogger(__name__)


# Minimum bars before indicator math is meaningful (MA50 needs 50, but we
# allow most signals/indicators to silently no-op below their own thresholds).
_MIN_BARS = 50


async def technical_pulse_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    financials = state.get("financials")
    if financials is None or not getattr(financials, "ticker", None):
        writer(StepCompleteEvent(
            node="technical_pulse",
            summary="Pulse skipped: no ticker.",
        ).model_dump())
        return {
            "pulse_result": None,
            "reasoning_steps": ["Pulse: skipped — no ticker"],
        }

    if not settings.fmp_api_key:
        writer(AgentThinkingEvent(
            node="technical_pulse",
            content="FMP API key not configured. Technical Pulse skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="technical_pulse",
            summary="Pulse skipped: FMP API key not set.",
        ).model_dump())
        return {
            "pulse_result": None,
            "reasoning_steps": ["Pulse: skipped — no FMP API key"],
        }

    ticker = financials.ticker
    entity_name = financials.entity_name

    writer(AgentThinkingEvent(
        node="technical_pulse",
        content=f"Building technical pulse for {ticker} (1Y daily history)...",
    ).model_dump())

    fmp_client = httpx.AsyncClient(base_url=settings.fmp_base_url, timeout=15.0)
    finnhub_client = httpx.AsyncClient(
        base_url=settings.finnhub_base_url, timeout=15.0,
    )
    try:
        history = await fetch_history(fmp_client, ticker, n_days=370)
        if len(history) < _MIN_BARS:
            writer(AgentThinkingEvent(
                node="technical_pulse",
                content=(
                    f"Insufficient OHLCV history for {ticker} "
                    f"({len(history)} bars, need {_MIN_BARS}). Skipping."
                ),
            ).model_dump())
            writer(StepCompleteEvent(
                node="technical_pulse",
                summary="Pulse skipped: insufficient OHLCV history.",
            ).model_dump())
            return {
                "pulse_result": None,
                "reasoning_steps": [
                    f"Pulse: skipped — only {len(history)} bars of history"
                ],
            }

        # Phase 2: gather everything that doesn't depend on profile.sector.
        # Each fetcher swallows its own httpx errors and returns a sentinel
        # (empty list / (None, None) / None / {}), so plain gather is safe.
        (
            spy_history,
            profile,
            spy_quote,
            vix_quote,
            tnx_quote,
            dxy_quote,
            insider_net,
            fg,
        ) = await asyncio.gather(
            fetch_history(fmp_client, "SPY", n_days=370),
            market_data_client.get_company_profile(ticker),
            fetch_quote(fmp_client, "SPY"),
            fetch_quote(fmp_client, "^VIX"),
            fetch_quote(fmp_client, "^TNX"),
            fetch_quote(fmp_client, "^DXY"),
            fetch_insider_net_90d(finnhub_client, ticker),
            fetch_fear_greed(),
        )

        # Phase 3: sector ETF quote (depends on profile).
        sector_etf = sector_to_etf(profile.get("sector"))
        _, sector_chg = await fetch_quote(fmp_client, sector_etf)

        spy_price, spy_chg = spy_quote
        vix_price, _ = vix_quote
        tnx_price, _ = tnx_quote
        dxy_price, _ = dxy_quote

        # Phase 4: DXY fallback — try plain DXY only if ^DXY missed (rare).
        if dxy_price is None:
            dxy_price, _ = await fetch_quote(fmp_client, "DXY")

        # CBOE's raw ^TNX is yield × 10 (e.g. 42.5 == 4.25%); some providers
        # (incl. FMP /stable/quote at times) normalize it to percent already.
        # 10Y treasury yield realistically lives in [0, 15]%, so values > 20
        # are unambiguously the CBOE convention and need to be scaled down.
        tnx_yield: float | None = tnx_price
        if tnx_yield is not None and tnx_yield > 20:
            tnx_yield /= 10.0

        closes = [b.close for b in history]
        highs = [b.high for b in history]
        lows = [b.low for b in history]
        volumes = [float(b.volume) for b in history]
        spy_closes = [b.close for b in spy_history] if spy_history else None

        # Signals + score (pure functions)
        signals = detect_signals(closes, highs, lows, volumes, spy_closes)
        score = composite_score(signals)
        label = signal_label(score)
        bull_count = sum(1 for s in signals if s.direction == "bull")
        bear_count = sum(1 for s in signals if s.direction == "bear")
        bull_pct = bullish_pct(signals)
        indicators = build_indicator_grid(closes)
        ma20 = sma(closes, 20)

        writer(AgentThinkingEvent(
            node="technical_pulse",
            content=(
                f"Detected {len(signals)} active signal(s) "
                f"({bull_count} bull, {bear_count} bear). "
                f"Composite score = {score} ({label})."
            ),
        ).model_dump())

        market_ctx = MarketContext(
            spy_change_pct=spy_chg,
            vix=vix_price,
            treasury_10y_pct=tnx_yield,
            dxy=dxy_price,
            sector_etf_symbol=sector_etf,
            sector_change_pct=sector_chg,
        )

        sentiment = SentimentSignals(
            fear_greed_value=fg[0] if fg else None,
            fear_greed_label=fg[1] if fg else None,
            insider_net_usd_90d=insider_net,
        )

        pulse = TechnicalPulse(
            composite_score=score,
            signal_label=label,
            bull_signal_count=bull_count,
            bear_signal_count=bear_count,
            bullish_pct=bull_pct,
            indicators=indicators,
            active_signals=signals,
            market_context=market_ctx,
            sentiment=sentiment,
            ohlcv=history,
            ohlcv_ma20=ma20,
        )
    except Exception as e:  # noqa: BLE001 — graceful degrade per project convention
        logger.exception("technical_pulse crashed for %s", ticker)
        writer(ErrorEvent(
            message=f"Technical pulse failed: {e}",
            recoverable=True,
        ).model_dump())
        writer(StepCompleteEvent(
            node="technical_pulse",
            summary="Pulse skipped: unexpected error.",
        ).model_dump())
        return {
            "pulse_result": None,
            "reasoning_steps": [f"Pulse: skipped — error {e}"],
        }
    finally:
        await fmp_client.aclose()
        await finnhub_client.aclose()

    # Emit components (visual order: hero → chart → indicators → signals → market → sentiment)
    ohlcv_dicts = [b.model_dump() for b in history]

    writer(ComponentEvent(
        component_type="pulse_score_hero",
        props={
            "ticker": ticker,
            "entity_name": entity_name,
            "composite_score": score,
            "signal_label": label,
            "bull_signal_count": bull_count,
            "bear_signal_count": bear_count,
            "bullish_pct": bull_pct,
        },
    ).model_dump())

    writer(ComponentEvent(
        component_type="price_chart_card",
        props={
            "ticker": ticker,
            "ohlcv": ohlcv_dicts,
            "ma20": ma20,
        },
    ).model_dump())

    writer(ComponentEvent(
        component_type="indicator_grid_card",
        props={
            "ticker": ticker,
            "indicators": [i.model_dump() for i in indicators],
        },
    ).model_dump())

    writer(ComponentEvent(
        component_type="signal_chips_card",
        props={
            "ticker": ticker,
            "active_signals": [s.model_dump() for s in signals],
        },
    ).model_dump())

    writer(ComponentEvent(
        component_type="market_context_card",
        props={
            "ticker": ticker,
            **market_ctx.model_dump(),
        },
    ).model_dump())

    writer(ComponentEvent(
        component_type="sentiment_pulse_card",
        props={
            "ticker": ticker,
            **sentiment.model_dump(),
        },
    ).model_dump())

    writer(StepCompleteEvent(
        node="technical_pulse",
        summary=(
            f"Pulse: score {score} ({label}), {len(signals)} signal(s), "
            f"sector {sector_etf}."
        ),
    ).model_dump())

    return {
        "pulse_result": pulse.model_dump(),
        "reasoning_steps": [
            f"Technical Pulse: {score}/100 ({label}); "
            f"{bull_count} bull / {bear_count} bear signals."
        ],
    }
