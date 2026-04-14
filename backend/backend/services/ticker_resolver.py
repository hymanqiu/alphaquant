"""Resolves stock ticker symbols to SEC CIK numbers."""

from __future__ import annotations

import httpx

from backend.config import settings


class TickerNotFoundError(Exception):
    pass


class TickerResolver:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[int, str]] = {}
        self._loaded = False

    async def load(self) -> None:
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.sec_user_agent}, timeout=30.0
        ) as client:
            resp = await client.get(settings.sec_ticker_url)
            resp.raise_for_status()
            data = resp.json()

        for entry in data.values():
            ticker = entry["ticker"].upper()
            cik = int(entry["cik_str"])
            title = entry["title"]
            self._cache[ticker] = (cik, title)

        self._loaded = True

    async def resolve(self, ticker: str) -> tuple[int, str]:
        if not self._loaded:
            await self.load()

        ticker = ticker.upper()
        if ticker not in self._cache:
            raise TickerNotFoundError(f"Ticker not found: {ticker}")

        return self._cache[ticker]


ticker_resolver = TickerResolver()
