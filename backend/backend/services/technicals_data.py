"""Data-fetching helpers for the ``technical_pulse`` node.

Sequential async calls (per ADR-010 §10) — keep it simple, no asyncio.gather.
Each helper degrades gracefully: returns ``None`` / ``[]`` on any failure
without raising, so the caller can compose a partial pulse snapshot.

In-memory TTL caches (5 min) sit on top of every fetcher to dampen FMP /
Finnhub / CNN load during a typical interactive testing session — multiple
``/analyze`` calls within 5 min reuse cached SPY history, market-index
quotes, sector ETF quotes, insider txns, and F&G index. Failures are not
cached so the next call gets a fresh shot.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from functools import wraps
from typing import Any, Callable, Coroutine, TypeVar

import httpx

from backend.config import settings
from backend.models.technicals import OHLCV

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TTL cache
# ---------------------------------------------------------------------------


_CACHE_TTL_SECONDS = 300.0  # 5 min — long enough to cover repeat /analyze runs

T = TypeVar("T")


def _is_empty_result(r: Any) -> bool:
    """Don't cache failure values; let the next call retry."""
    if r is None:
        return True
    if isinstance(r, list) and not r:
        return True
    if isinstance(r, tuple) and all(v is None for v in r):
        return True
    return False


def _cached(
    ttl: float = _CACHE_TTL_SECONDS,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, T]]],
    Callable[..., Coroutine[Any, Any, T]],
]:
    """Decorator: in-memory TTL cache keyed by all non-httpx-client args.

    httpx.AsyncClient instances are skipped in the key so different per-call
    transient clients don't bust the cache.
    """

    def decorator(
        fn: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        store: dict[tuple, tuple[float, T]] = {}

        @wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> T:
            key_args = tuple(
                a for a in args if not isinstance(a, httpx.AsyncClient)
            )
            key = (key_args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            hit = store.get(key)
            if hit is not None and now - hit[0] < ttl:
                return hit[1]
            result = await fn(*args, **kwargs)
            if not _is_empty_result(result):
                store[key] = (now, result)
            return result

        return wrapped

    return decorator


# Browser-like UA so CNN's F&G endpoint doesn't return 403.
_FG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
}


# ---------------------------------------------------------------------------
# OHLCV history (FMP)
# ---------------------------------------------------------------------------


@_cached()
async def fetch_history(
    client: httpx.AsyncClient, ticker: str, n_days: int = 370
) -> list[OHLCV]:
    """Fetch ~1Y of daily OHLCV bars (oldest → newest). Empty list on failure."""
    if not settings.fmp_api_key:
        return []
    try:
        from_date = date.today() - timedelta(days=n_days)
        resp = await client.get(
            "/stable/historical-price-eod/full",
            params={
                "symbol": ticker,
                "apikey": settings.fmp_api_key,
                "from": from_date.isoformat(),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        # FMP returns newest-first; we want oldest-first for indicator math.
        sorted_data = sorted(data, key=lambda e: e.get("date", ""))
        bars: list[OHLCV] = []
        for entry in sorted_data:
            try:
                bars.append(OHLCV(
                    date=entry["date"],
                    open=float(entry["open"]),
                    high=float(entry["high"]),
                    low=float(entry["low"]),
                    close=float(entry["close"]),
                    volume=int(entry.get("volume") or 0),
                ))
            except (KeyError, ValueError, TypeError):
                continue
        return bars
    except httpx.HTTPStatusError as e:
        logger.warning("technicals fetch_history(%s) HTTP %s", ticker, e.response.status_code)
    except httpx.RequestError as e:
        logger.warning("technicals fetch_history(%s) request error: %s", ticker, e)
    except (ValueError, TypeError) as e:
        logger.warning("technicals fetch_history(%s) parse error: %s", ticker, e)
    return []


# ---------------------------------------------------------------------------
# Quotes (FMP) — VIX, ^TNX, DXY, sector ETF
# ---------------------------------------------------------------------------


@_cached()
async def fetch_quote(
    client: httpx.AsyncClient, symbol: str
) -> tuple[float | None, float | None]:
    """Returns ``(last_price, change_pct)``. Either may be None on failure."""
    if not settings.fmp_api_key:
        return None, None
    try:
        resp = await client.get(
            "/stable/quote",
            params={"symbol": symbol, "apikey": settings.fmp_api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            item = data[0]
            price = item.get("price")
            chg_pct = item.get("changePercentage") or item.get("changesPercentage")
            return (
                float(price) if price is not None else None,
                float(chg_pct) if chg_pct is not None else None,
            )
    except httpx.HTTPStatusError as e:
        # 401/403 are common for tickers outside the user's plan — log low-key.
        if e.response.status_code not in (401, 403):
            logger.warning("technicals fetch_quote(%s) HTTP %s", symbol, e.response.status_code)
    except httpx.RequestError as e:
        logger.warning("technicals fetch_quote(%s) request error: %s", symbol, e)
    except (ValueError, TypeError) as e:
        logger.warning("technicals fetch_quote(%s) parse error: %s", symbol, e)
    return None, None


# ---------------------------------------------------------------------------
# Insider net 90d (Finnhub)
# ---------------------------------------------------------------------------


@_cached()
async def fetch_insider_net_90d(
    client: httpx.AsyncClient, ticker: str
) -> float | None:
    """Sum of (share_change × transactionPrice) over the trailing 90 days."""
    if not settings.finnhub_api_key:
        return None
    try:
        today = date.today()
        from_date = today - timedelta(days=90)
        resp = await client.get(
            "/stock/insider-transactions",
            params={
                "symbol": ticker,
                "from": from_date.isoformat(),
                "to": today.isoformat(),
                "token": settings.finnhub_api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return None
        rows = data.get("data") or []
        if not isinstance(rows, list):
            return None
        total = 0.0
        for row in rows:
            change = row.get("change") or 0
            price = row.get("transactionPrice") or 0
            try:
                total += float(change) * float(price)
            except (ValueError, TypeError):
                continue
        return total
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 403:
            logger.warning("technicals fetch_insider_net_90d(%s) HTTP %s", ticker, e.response.status_code)
    except httpx.RequestError as e:
        logger.warning("technicals fetch_insider_net_90d(%s) request error: %s", ticker, e)
    except (ValueError, TypeError) as e:
        logger.warning("technicals fetch_insider_net_90d(%s) parse error: %s", ticker, e)
    return None


# ---------------------------------------------------------------------------
# CNN Fear & Greed (unofficial endpoint)
# ---------------------------------------------------------------------------


@_cached()
async def fetch_fear_greed() -> tuple[int, str] | None:
    """Returns ``(value, label)`` from CNN's F&G index. Browser UA required."""
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_FG_HEADERS) as fg:
            resp = await fg.get(url)
            resp.raise_for_status()
            data = resp.json()
            block = data.get("fear_and_greed") or {}
            score = block.get("score")
            rating = block.get("rating")
            if score is None or rating is None:
                return None
            return int(round(float(score))), str(rating).strip().title()
    except httpx.HTTPStatusError as e:
        logger.warning("F&G fetch HTTP %s", e.response.status_code)
    except httpx.RequestError as e:
        logger.warning("F&G fetch request error: %s", e)
    except (ValueError, TypeError, KeyError) as e:
        logger.warning("F&G fetch parse error: %s", e)
    return None


# ---------------------------------------------------------------------------
# Sector → SPDR sector ETF map
# ---------------------------------------------------------------------------


_SECTOR_ETF: dict[str, str] = {
    # FMP profile sector strings. Keys are lowercased; multiple aliases per ETF.
    "technology": "XLK",
    "information technology": "XLK",
    "financial services": "XLF",
    "financial": "XLF",
    "financials": "XLF",
    "energy": "XLE",
    "healthcare": "XLV",
    "health care": "XLV",
    "consumer cyclical": "XLY",
    "consumer discretionary": "XLY",
    "consumer defensive": "XLP",
    "consumer staples": "XLP",
    "industrials": "XLI",
    "industrial": "XLI",
    "utilities": "XLU",
    "basic materials": "XLB",
    "materials": "XLB",
    "real estate": "XLRE",
    "communication services": "XLC",
    "communications": "XLC",
}


def sector_to_etf(sector: str | None) -> str:
    """Map an FMP sector string to the matching SPDR sector ETF.

    Falls back to ``SPY`` (broad market) when the sector is unknown or absent.
    """
    if not sector:
        return "SPY"
    return _SECTOR_ETF.get(sector.strip().lower(), "SPY")
