"""FastAPI dependency injection."""

from __future__ import annotations

import time
from typing import Any

from backend.models.financial import CompanyFinancials

# In-memory cache for DCF recalculation (ticker -> (financials, timestamp))
_financials_cache: dict[str, tuple[CompanyFinancials, float]] = {}
CACHE_TTL = 1800  # 30 minutes


def cache_financials(ticker: str, financials: CompanyFinancials) -> None:
    _financials_cache[ticker.upper()] = (financials, time.time())


def get_cached_financials(ticker: str) -> CompanyFinancials | None:
    entry = _financials_cache.get(ticker.upper())
    if entry is None:
        return None
    financials, ts = entry
    if time.time() - ts > CACHE_TTL:
        del _financials_cache[ticker.upper()]
        return None
    return financials
