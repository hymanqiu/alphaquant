"""Unit tests for ``technical_pulse_math``.

Per project convention only the pure ``_math`` sibling has tests; the I/O
node ``technical_pulse.py`` is not covered here.
"""

from __future__ import annotations

from backend.agents.nodes.technical_pulse_math import (
    SIGNAL_WEIGHTS,
    bullish_pct,
    composite_score,
    detect_above_vwap,
    detect_distribution_days,
    detect_golden_cross,
    detect_macd_bullish_crossover,
    detect_relative_strength,
    detect_rsi_bearish_divergence,
    macd,
    signal_label,
    sma,
)
from backend.models.technicals import TechnicalSignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bull(sig_id: str, weight: float | None = None) -> TechnicalSignal:
    return TechnicalSignal(
        id=sig_id, label=sig_id, direction="bull",
        weight=weight if weight is not None else SIGNAL_WEIGHTS[sig_id],
    )


def _bear(sig_id: str, weight: float | None = None) -> TechnicalSignal:
    return TechnicalSignal(
        id=sig_id, label=sig_id, direction="bear",
        weight=weight if weight is not None else SIGNAL_WEIGHTS[sig_id],
    )


# ---------------------------------------------------------------------------
# Composite score + label
# ---------------------------------------------------------------------------


def test_composite_score_neutral_baseline() -> None:
    assert composite_score([]) == 50


def test_composite_score_strong_bullish() -> None:
    bull_ids = [
        "golden_cross", "macd_bullish_crossover", "higher_highs_lows",
        "volume_confirms_trend", "above_all_mas", "relative_strength",
        "breakout_base", "above_vwap",
    ]
    score = composite_score([_bull(i) for i in bull_ids])
    assert score >= 90


def test_composite_score_strong_bearish() -> None:
    bear_ids = ["rsi_overbought", "rsi_bearish_divergence", "distribution_days"]
    score = composite_score([_bear(i) for i in bear_ids])
    assert score <= 25


def test_signal_label_thresholds() -> None:
    assert signal_label(29) == "Strong Sell"
    assert signal_label(30) == "Sell"
    assert signal_label(44) == "Sell"
    assert signal_label(45) == "Neutral"
    assert signal_label(54) == "Neutral"
    assert signal_label(55) == "Buy"
    assert signal_label(69) == "Buy"
    assert signal_label(70) == "Strong Buy"


def test_bullish_pct_no_signals_is_neutral() -> None:
    assert bullish_pct([]) == 0.5


def test_bullish_pct_mixed() -> None:
    sigs = [_bull("golden_cross"), _bear("rsi_overbought")]
    # bull weight 1.5, bear weight 1.0 → 0.6
    assert abs(bullish_pct(sigs) - 0.6) < 1e-9


# ---------------------------------------------------------------------------
# Indicator math basics (sanity)
# ---------------------------------------------------------------------------


def test_sma_basic() -> None:
    out = sma([1, 2, 3, 4, 5], 3)
    assert out == [None, None, 2.0, 3.0, 4.0]


def test_macd_returns_aligned_lengths() -> None:
    closes = list(range(1, 60))
    m, s, h = macd(closes)
    assert len(m) == len(s) == len(h) == len(closes)


# ---------------------------------------------------------------------------
# Signal detectors
# ---------------------------------------------------------------------------


def test_signal_golden_cross_detection() -> None:
    """Build 250 closes with a clear MA50/MA200 cross inside the trailing 5d."""
    closes: list[float] = []
    # 100 flat at 100
    closes += [100.0] * 100
    # 100 of decline 100 → 70
    closes += [100.0 - 0.3 * i for i in range(100)]
    # 50 of recovery 70 → 130
    closes += [70.0 + 1.2 * i for i in range(50)]
    sig = detect_golden_cross(closes, window=10)
    assert sig is not None
    assert sig.id == "golden_cross"
    assert sig.direction == "bull"


def test_signal_macd_crossover_window_excludes_old_cross() -> None:
    """A cross >5 sessions ago should NOT fire under the default 5d window."""
    # Construct a MACD bullish cross ~10 sessions before the end, then keep
    # MACD above signal afterwards (no fresh cross in the trailing 5d).
    closes = [100.0 - i for i in range(40)]      # 40 days down
    closes += [60.0 + 2.0 * i for i in range(20)]  # then 20 days strong up
    closes += [100.0 + 0.1 * i for i in range(15)]  # then 15 days drift up
    sig = detect_macd_bullish_crossover(closes, window=5)
    assert sig is None


def test_signal_rsi_bearish_divergence_fires() -> None:
    """Price makes a fresh 20d high but RSI fails to confirm → divergence."""
    closes: list[float] = []
    last = 100.0
    # 14-day oscillating warmup so RSI seeds around neutral
    for i in range(14):
        last += 1.0 if i % 2 == 0 else -1.0
        closes.append(last)
    # 10-day sharp rally — drives RSI very high
    for _ in range(10):
        last += 2.0
        closes.append(last)
    # 25-day mean-reverting oscillation — RSI cools back down
    for i in range(25):
        last += 1.0 if i % 2 == 0 else -1.0
        closes.append(last)
    # Final marginal new high vs the prior 20 closes
    closes.append(max(closes[-20:]) + 0.5)
    sig = detect_rsi_bearish_divergence(closes)
    assert sig is not None
    assert sig.id == "rsi_bearish_divergence"
    assert sig.direction == "bear"


def test_signal_distribution_days_fires_with_4_plus() -> None:
    """≥4 days where close drops on volume >1.25× avg in last 30 sessions."""
    # 31 closes (so 30 day-over-day comparisons); volumes aligned 1:1.
    closes = [100.0]
    volumes = [1_000_000.0]
    base_vol = 1_000_000.0
    for i in range(30):
        if i % 2 == 0:
            closes.append(closes[-1] + 0.5)
        else:
            closes.append(closes[-1] - 0.5)
        volumes.append(base_vol)
    # Spike volume on 4 down days (closes indices 2, 4, 6, 8 — even i in
    # the loop above produced *up* days, so down days are at odd loop i,
    # i.e. closes indices 2, 4, 6, 8).
    for idx in (2, 4, 6, 8):
        volumes[idx] = base_vol * 2.0
    sig = detect_distribution_days(closes, volumes)
    assert sig is not None
    assert sig.id == "distribution_days"


def test_signal_distribution_days_no_fire_below_threshold() -> None:
    """3 distribution days → does NOT fire."""
    closes = [100.0]
    volumes = [1_000_000.0]
    for i in range(30):
        if i % 2 == 0:
            closes.append(closes[-1] + 0.5)
        else:
            closes.append(closes[-1] - 0.5)
        volumes.append(1_000_000.0)
    for idx in (2, 4, 6):  # only 3 spiked down-day volumes
        volumes[idx] = 2_000_000.0
    sig = detect_distribution_days(closes, volumes)
    assert sig is None


def test_relative_strength_vs_spy_fires_when_outperforming() -> None:
    closes = [100.0] * 31
    closes[-1] = 105.0          # +5% over 30d
    spy = [100.0] * 31
    spy[-1] = 103.0             # +3% over 30d
    sig = detect_relative_strength(closes, spy, lookback=30)
    assert sig is not None
    assert sig.id == "relative_strength"


def test_relative_strength_no_fire_when_underperforming() -> None:
    closes = [100.0] * 31
    closes[-1] = 102.0
    spy = [100.0] * 31
    spy[-1] = 105.0
    assert detect_relative_strength(closes, spy, lookback=30) is None


def test_above_vwap_requires_5_consecutive_days() -> None:
    """4 days satisfy, 1 day breaks → no fire."""
    # Build 30 bars with H/L/C tightly grouped and rising volume so VWAP is
    # close to closes; then push the last 4 closes well above VWAP but
    # have closes[-5] sit below VWAP.
    n = 30
    highs = [100.0 + i * 0.1 for i in range(n)]
    lows = [99.0 + i * 0.1 for i in range(n)]
    closes = [99.5 + i * 0.1 for i in range(n)]   # near VWAP
    volumes = [1_000_000.0] * n
    # Last 4 well above VWAP
    for k in (1, 2, 3, 4):
        closes[-k] = 200.0
    # The 5th-from-last sits below VWAP
    closes[-5] = 50.0
    sig = detect_above_vwap(highs, lows, closes, volumes)
    assert sig is None


def test_above_vwap_fires_when_5_consecutive_above() -> None:
    n = 30
    highs = [100.0 + i * 0.1 for i in range(n)]
    lows = [99.0 + i * 0.1 for i in range(n)]
    closes = [99.5 + i * 0.1 for i in range(n)]
    volumes = [1_000_000.0] * n
    # Last 5 closes well above VWAP
    for k in (1, 2, 3, 4, 5):
        closes[-k] = 200.0
    sig = detect_above_vwap(highs, lows, closes, volumes)
    assert sig is not None
    assert sig.id == "above_vwap"
