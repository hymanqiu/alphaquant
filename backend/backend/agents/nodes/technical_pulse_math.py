"""Pure helpers for the ``technical_pulse`` node — indicator math, signal rules,
composite score. No I/O, no LLM, no Pydantic state mutation. Everything here
takes plain ``list[float] | list[int]`` and returns either primitives or the
data-contract models from ``backend.models.technicals``.

Project convention (see ``CLAUDE.md`` "节点纯/不纯拆分"): unit tests cover this
file only; the wrapping node ``technical_pulse.py`` does the I/O.
"""

from __future__ import annotations

import math
from typing import Sequence

from backend.models.technicals import (
    SignalLabel,
    TechnicalIndicator,
    TechnicalSignal,
    Tone,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


SIGNAL_WEIGHTS: dict[str, float] = {
    # Bull
    "golden_cross": 1.5,
    "macd_bullish_crossover": 1.0,
    "higher_highs_lows": 1.2,
    "volume_confirms_trend": 0.8,
    "above_all_mas": 1.5,
    "relative_strength": 1.0,
    "breakout_base": 1.2,
    "above_vwap": 0.6,
    # Bear
    "rsi_overbought": 1.0,
    "rsi_bearish_divergence": 1.5,
    "distribution_days": 0.8,
}

SIGNAL_LABELS: dict[str, str] = {
    "golden_cross": "Golden cross (50/200)",
    "macd_bullish_crossover": "MACD bullish crossover",
    "higher_highs_lows": "Higher highs & higher lows (20d)",
    "volume_confirms_trend": "Volume confirms uptrend",
    "above_all_mas": "Price above MA20/50/200",
    "relative_strength": "Outperforming SPY (30d)",
    "breakout_base": "Breakout above 60d high",
    "above_vwap": "Holding above VWAP20 (5d)",
    "rsi_overbought": "RSI overbought (>70)",
    "rsi_bearish_divergence": "Bearish RSI divergence",
    "distribution_days": "Distribution days cluster (≥4 in 30d)",
}


# ---------------------------------------------------------------------------
# Indicator math
# ---------------------------------------------------------------------------


def sma(values: Sequence[float], n: int) -> list[float | None]:
    """Simple moving average. Output length == input length; first n-1 are None."""
    out: list[float | None] = [None] * len(values)
    if n <= 0 or len(values) < n:
        return out
    running = sum(values[:n])
    out[n - 1] = running / n
    for i in range(n, len(values)):
        running += values[i] - values[i - n]
        out[i] = running / n
    return out


def ema(values: Sequence[float], n: int) -> list[float | None]:
    """Exponential moving average, seeded with SMA(n). Output length == input."""
    out: list[float | None] = [None] * len(values)
    if n <= 0 or len(values) < n:
        return out
    seed = sum(values[:n]) / n
    out[n - 1] = seed
    k = 2.0 / (n + 1)
    prev = seed
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(closes: Sequence[float], n: int = 14) -> list[float | None]:
    """Wilder's RSI. Needs n+1 closes to produce the first value at index n."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, n + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / n
    avg_loss = losses / n
    out[n] = _rsi_from_avg(avg_gain, avg_loss)
    for i in range(n + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (n - 1) + gain) / n
        avg_loss = (avg_loss * (n - 1) + loss) / n
        out[i] = _rsi_from_avg(avg_gain, avg_loss)
    return out


def _rsi_from_avg(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Returns (macd_line, signal_line, histogram), each aligned to ``closes``."""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line: list[float | None] = [
        f - s if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow)
    ]
    # Signal line = EMA of macd_line over `signal` periods, but EMA() needs a
    # plain float sequence. Run it on the tail where macd_line is defined.
    first = next((i for i, v in enumerate(macd_line) if v is not None), None)
    sig_line: list[float | None] = [None] * len(closes)
    hist: list[float | None] = [None] * len(closes)
    if first is None:
        return macd_line, sig_line, hist
    macd_tail = [v for v in macd_line[first:] if v is not None]
    if len(macd_tail) < signal:
        return macd_line, sig_line, hist
    sig_tail = ema(macd_tail, signal)
    for offset, v in enumerate(sig_tail):
        sig_line[first + offset] = v
    for i in range(len(closes)):
        m, s = macd_line[i], sig_line[i]
        hist[i] = m - s if (m is not None and s is not None) else None
    return macd_line, sig_line, hist


def vwap_rolling(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    n: int = 20,
) -> list[float | None]:
    """Rolling n-day VWAP using typical price = (H+L+C)/3, volume-weighted."""
    out: list[float | None] = [None] * len(closes)
    if n <= 0 or len(closes) < n:
        return out
    tp = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(len(closes))]
    pv = [tp[i] * volumes[i] for i in range(len(closes))]
    pv_sum = sum(pv[:n])
    v_sum = sum(volumes[:n])
    out[n - 1] = pv_sum / v_sum if v_sum > 0 else None
    for i in range(n, len(closes)):
        pv_sum += pv[i] - pv[i - n]
        v_sum += volumes[i] - volumes[i - n]
        out[i] = pv_sum / v_sum if v_sum > 0 else None
    return out


# ---------------------------------------------------------------------------
# Signal detectors — each returns TechnicalSignal | None
# ---------------------------------------------------------------------------


def _make_signal(sig_id: str, direction: str, detail: str | None = None) -> TechnicalSignal:
    return TechnicalSignal(
        id=sig_id,
        label=SIGNAL_LABELS[sig_id],
        direction=direction,  # type: ignore[arg-type]
        weight=SIGNAL_WEIGHTS[sig_id],
        detail=detail,
    )


def detect_golden_cross(closes: Sequence[float], window: int = 5) -> TechnicalSignal | None:
    """MA50 crosses above MA200 within the trailing ``window`` sessions."""
    ma50 = sma(closes, 50)
    ma200 = sma(closes, 200)
    n = len(closes)
    start = max(1, n - window)
    for t in range(start, n):
        a, b = ma50[t - 1], ma200[t - 1]
        c, d = ma50[t], ma200[t]
        if None in (a, b, c, d):
            continue
        if a <= b and c > d:  # type: ignore[operator]
            return _make_signal(
                "golden_cross",
                "bull",
                detail=f"MA50 crossed above MA200 {n - t} session(s) ago.",
            )
    return None


def detect_macd_bullish_crossover(
    closes: Sequence[float], window: int = 5
) -> TechnicalSignal | None:
    _, sig, _ = macd(closes)
    macd_line, _, _ = macd(closes)  # cheap re-call; macd() is fast
    n = len(closes)
    start = max(1, n - window)
    for t in range(start, n):
        m_prev, m_now = macd_line[t - 1], macd_line[t]
        s_prev, s_now = sig[t - 1], sig[t]
        if None in (m_prev, m_now, s_prev, s_now):
            continue
        if m_prev <= s_prev and m_now > s_now:  # type: ignore[operator]
            return _make_signal(
                "macd_bullish_crossover",
                "bull",
                detail=f"MACD crossed above signal {n - t} session(s) ago.",
            )
    return None


def detect_higher_highs_lows(closes: Sequence[float]) -> TechnicalSignal | None:
    if len(closes) < 40:
        return None
    recent = closes[-20:]
    prior = closes[-40:-20]
    if max(recent) > max(prior) and min(recent) > min(prior):
        return _make_signal("higher_highs_lows", "bull")
    return None


def detect_volume_confirms_trend(
    closes: Sequence[float], volumes: Sequence[float]
) -> TechnicalSignal | None:
    if len(closes) < 31:
        return None
    up_vol: list[float] = []
    down_vol: list[float] = []
    for i in range(len(closes) - 30, len(closes)):
        if closes[i] > closes[i - 1]:
            up_vol.append(volumes[i])
        elif closes[i] < closes[i - 1]:
            down_vol.append(volumes[i])
    if not up_vol or not down_vol:
        return None
    if (sum(up_vol) / len(up_vol)) > 1.1 * (sum(down_vol) / len(down_vol)):
        return _make_signal("volume_confirms_trend", "bull")
    return None


def detect_above_all_mas(closes: Sequence[float]) -> TechnicalSignal | None:
    ma20 = sma(closes, 20)
    ma50 = sma(closes, 50)
    ma200 = sma(closes, 200)
    if None in (ma20[-1], ma50[-1], ma200[-1]):
        return None
    c = closes[-1]
    if c > ma20[-1] > ma50[-1] > ma200[-1]:  # type: ignore[operator]
        return _make_signal("above_all_mas", "bull")
    return None


def detect_relative_strength(
    closes: Sequence[float], spy_closes: Sequence[float], lookback: int = 30
) -> TechnicalSignal | None:
    if len(closes) <= lookback or len(spy_closes) <= lookback:
        return None
    if closes[-lookback - 1] <= 0 or spy_closes[-lookback - 1] <= 0:
        return None
    r_ticker = closes[-1] / closes[-lookback - 1] - 1
    r_spy = spy_closes[-1] / spy_closes[-lookback - 1] - 1
    if r_ticker > r_spy:
        return _make_signal(
            "relative_strength",
            "bull",
            detail=f"{(r_ticker - r_spy) * 100:+.1f}% vs SPY over {lookback}d.",
        )
    return None


def detect_breakout_base(
    closes: Sequence[float], highs: Sequence[float]
) -> TechnicalSignal | None:
    if len(highs) < 61:
        return None
    if closes[-1] > max(highs[-61:-1]):
        return _make_signal("breakout_base", "bull")
    return None


def detect_above_vwap(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> TechnicalSignal | None:
    vwap = vwap_rolling(highs, lows, closes, volumes, n=20)
    if len(closes) < 5 or any(vwap[-i] is None for i in range(1, 6)):
        return None
    for i in range(1, 6):
        if closes[-i] <= vwap[-i]:  # type: ignore[operator]
            return None
    return _make_signal("above_vwap", "bull")


def detect_rsi_overbought(closes: Sequence[float]) -> TechnicalSignal | None:
    r = rsi(closes, 14)
    if r[-1] is None:
        return None
    if r[-1] > 70:  # type: ignore[operator]
        return _make_signal(
            "rsi_overbought",
            "bear",
            detail=f"RSI14 = {r[-1]:.0f}",
        )
    return None


def detect_rsi_bearish_divergence(closes: Sequence[float]) -> TechnicalSignal | None:
    if len(closes) < 21:
        return None
    r = rsi(closes, 14)
    if r[-1] is None:
        return None
    prior_max_close = max(closes[-21:-1])
    prior_max_rsi = max(v for v in r[-21:-1] if v is not None) if any(
        v is not None for v in r[-21:-1]
    ) else None
    if prior_max_rsi is None:
        return None
    if closes[-1] > prior_max_close and r[-1] < prior_max_rsi:  # type: ignore[operator]
        return _make_signal("rsi_bearish_divergence", "bear")
    return None


def detect_distribution_days(
    closes: Sequence[float], volumes: Sequence[float]
) -> TechnicalSignal | None:
    if len(closes) < 31:
        return None
    avg_vol = sum(volumes[-30:]) / 30.0
    count = 0
    for i in range(len(closes) - 30, len(closes)):
        if closes[i] < closes[i - 1] and volumes[i] > 1.25 * avg_vol:
            count += 1
    if count >= 4:
        return _make_signal(
            "distribution_days",
            "bear",
            detail=f"{count} distribution day(s) in the last 30 sessions.",
        )
    return None


def detect_signals(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    volumes: Sequence[float],
    spy_closes: Sequence[float] | None = None,
) -> list[TechnicalSignal]:
    """Run every rule. Each detector handles its own data-sufficiency checks."""
    candidates: list[TechnicalSignal | None] = [
        detect_golden_cross(closes),
        detect_macd_bullish_crossover(closes),
        detect_higher_highs_lows(closes),
        detect_volume_confirms_trend(closes, volumes),
        detect_above_all_mas(closes),
        detect_relative_strength(closes, spy_closes) if spy_closes else None,
        detect_breakout_base(closes, highs),
        detect_above_vwap(highs, lows, closes, volumes),
        detect_rsi_overbought(closes),
        detect_rsi_bearish_divergence(closes),
        detect_distribution_days(closes, volumes),
    ]
    return [s for s in candidates if s is not None]


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------


def composite_score(signals: list[TechnicalSignal]) -> int:
    """Weighted sum of signed signals → tanh squashed to 0..100, neutral=50."""
    delta = sum(
        s.weight if s.direction == "bull" else -s.weight for s in signals
    )
    score = 50 + 50 * math.tanh(delta / 4.0)
    return round(score)


def signal_label(score: int) -> SignalLabel:
    if score < 30:
        return "Strong Sell"
    if score < 45:
        return "Sell"
    if score < 55:
        return "Neutral"
    if score < 70:
        return "Buy"
    return "Strong Buy"


def bullish_pct(signals: list[TechnicalSignal]) -> float:
    """Fraction of total signal-weight that is bullish (0..1). 0.5 if no signals."""
    bull = sum(s.weight for s in signals if s.direction == "bull")
    bear = sum(s.weight for s in signals if s.direction == "bear")
    total = bull + bear
    if total == 0:
        return 0.5
    return bull / total


# ---------------------------------------------------------------------------
# Indicator-card builders (the 4-up grid)
# ---------------------------------------------------------------------------


def build_rsi_card(closes: Sequence[float]) -> TechnicalIndicator:
    r = rsi(closes, 14)
    val = r[-1] if r and r[-1] is not None else None
    if val is None:
        return TechnicalIndicator(
            id="rsi", label="RSI 14", value="—",
            sub_label="Insufficient data", tone="neutral",
        )
    if val > 70:
        tone: Tone = "warning"
        sub = "Overbought"
    elif val < 30:
        tone = "warning"
        sub = "Oversold"
    elif val >= 55:
        tone = "bull"
        sub = "Bullish momentum"
    elif val <= 45:
        tone = "bear"
        sub = "Bearish momentum"
    else:
        tone = "neutral"
        sub = "Neutral zone"
    return TechnicalIndicator(
        id="rsi", label="RSI 14", value=f"{val:.0f}", sub_label=sub, tone=tone,
    )


def build_macd_card(closes: Sequence[float]) -> TechnicalIndicator:
    _, _, hist = macd(closes)
    h = hist[-1] if hist and hist[-1] is not None else None
    if h is None:
        return TechnicalIndicator(
            id="macd", label="MACD hist", value="—",
            sub_label="Insufficient data", tone="neutral",
        )
    sign = "+" if h >= 0 else ""
    tone: Tone = "bull" if h > 0 else "bear" if h < 0 else "neutral"
    sub = "Above signal" if h > 0 else "Below signal" if h < 0 else "At signal"
    return TechnicalIndicator(
        id="macd", label="MACD hist", value=f"{sign}{h:.2f}", sub_label=sub, tone=tone,
    )


def build_ma_stack_card(closes: Sequence[float]) -> TechnicalIndicator:
    ma20 = sma(closes, 20)
    ma50 = sma(closes, 50)
    ma200 = sma(closes, 200)
    a, b, c = ma20[-1] if ma20 else None, ma50[-1] if ma50 else None, ma200[-1] if ma200 else None
    if None in (a, b, c):
        return TechnicalIndicator(
            id="ma_stack", label="MA stack", value="—",
            sub_label="Need 200 days", tone="neutral",
        )
    if a > b > c:  # type: ignore[operator]
        return TechnicalIndicator(
            id="ma_stack", label="MA stack", value="20 > 50 > 200",
            sub_label="Bullish alignment", tone="bull",
        )
    if a < b < c:  # type: ignore[operator]
        return TechnicalIndicator(
            id="ma_stack", label="MA stack", value="20 < 50 < 200",
            sub_label="Bearish alignment", tone="bear",
        )
    return TechnicalIndicator(
        id="ma_stack", label="MA stack", value="Mixed",
        sub_label="No clear alignment", tone="neutral",
    )


def build_52w_card(closes: Sequence[float]) -> TechnicalIndicator:
    if len(closes) < 2:
        return TechnicalIndicator(
            id="wk52", label="52W position", value="—",
            sub_label="Insufficient data", tone="neutral",
        )
    window = closes[-min(252, len(closes)):]
    lo, hi = min(window), max(window)
    if hi == lo:
        pct = 50.0
    else:
        pct = (closes[-1] - lo) / (hi - lo) * 100
    pct_int = max(0, min(100, round(pct)))
    if pct_int >= 80:
        tone: Tone = "bull"
        sub = "Near 52W high"
    elif pct_int <= 20:
        tone = "bear"
        sub = "Near 52W low"
    else:
        tone = "neutral"
        sub = "Mid-range"
    return TechnicalIndicator(
        id="wk52", label="52W position", value=f"{pct_int}%", sub_label=sub, tone=tone,
    )


def build_indicator_grid(closes: Sequence[float]) -> list[TechnicalIndicator]:
    """Always returns exactly 4 cards in display order."""
    return [
        build_rsi_card(closes),
        build_macd_card(closes),
        build_ma_stack_card(closes),
        build_52w_card(closes),
    ]
