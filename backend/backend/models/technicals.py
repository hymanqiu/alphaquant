"""Pulse tab data contract: technical indicators, signals, sentiment, market context.

Emitted by the ``technical_pulse`` node and rendered by the Pulse tab on the
frontend (six dedicated components). See ``docs/decisions/013-pulse-tab.md``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


SignalLabel = Literal["Strong Sell", "Sell", "Neutral", "Buy", "Strong Buy"]
Tone = Literal["bull", "bear", "neutral", "warning"]
Direction = Literal["bull", "bear"]
IndicatorId = Literal["rsi", "macd", "ma_stack", "wk52"]


class OHLCV(BaseModel):
    date: str  # ISO YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int


class TechnicalIndicator(BaseModel):
    """One mini-card in the 4-up Indicator Grid."""

    id: IndicatorId
    label: str         # e.g. "RSI 14"
    value: str         # e.g. "62" / "+0.42" / "20 > 50 > 200" / "89%"
    sub_label: str     # e.g. "Bullish · neutral zone"
    tone: Tone


class TechnicalSignal(BaseModel):
    """One bull/bear rule that fired against the price/volume series."""

    id: str
    label: str
    direction: Direction
    weight: float
    detail: str | None = None


class MarketContext(BaseModel):
    """One-line snapshot of the broader tape — all fields optional."""

    spy_change_pct: float | None = None
    vix: float | None = None
    treasury_10y_pct: float | None = None
    dxy: float | None = None
    sector_etf_symbol: str
    sector_change_pct: float | None = None


class SentimentSignals(BaseModel):
    """Crowd / positioning signals — all fields optional."""

    fear_greed_value: int | None = None      # 0–100
    fear_greed_label: str | None = None      # "Greed", "Fear", ...
    put_call_ratio: float | None = None
    insider_net_usd_90d: float | None = None
    short_interest_pct: float | None = None
    aaii_bull_minus_bear: float | None = None


class TechnicalPulse(BaseModel):
    """Top-level payload for the Pulse tab. Stored on AnalysisState as a dict."""

    composite_score: int                     # 0–100
    signal_label: SignalLabel
    bull_signal_count: int
    bear_signal_count: int
    bullish_pct: float                       # 0.0–1.0

    indicators: list[TechnicalIndicator]     # always length 4
    active_signals: list[TechnicalSignal]
    market_context: MarketContext
    sentiment: SentimentSignals
    ohlcv: list[OHLCV]                       # ~252 daily bars (1Y)
    ohlcv_ma20: list[float | None]           # same length as ohlcv; first 19 None
