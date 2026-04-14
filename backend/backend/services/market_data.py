"""FMP (Financial Modeling Prep) client for market price data."""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from backend.config import settings


class MarketDataClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.fmp_base_url,
            timeout=15.0,
        )

    async def get_current_price(self, ticker: str) -> float | None:
        """Fetch the latest market price for a ticker. Returns None on failure."""
        if not settings.fmp_api_key:
            return None
        try:
            resp = await self._client.get(
                f"/api/v3/quote-short/{ticker}",
                params={"apikey": settings.fmp_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                return float(data[0]["price"])
        except Exception:
            return None
        return None

    async def get_annual_closing_prices(
        self, ticker: str, years: int = 10
    ) -> dict[int, float]:
        """Fetch end-of-year closing prices for the last N years.

        Returns {calendar_year: closing_price} using the last trading day of each year.
        """
        if not settings.fmp_api_key:
            return {}
        try:
            from_date = date.today() - timedelta(days=years * 365 + 30)
            resp = await self._client.get(
                f"/api/v3/historical-price-full/{ticker}",
                params={
                    "apikey": settings.fmp_api_key,
                    "from": from_date.isoformat(),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            historical = data.get("historical", [])
            if not historical:
                return {}

            # Group by year, keep the last trading day (data is sorted newest-first)
            year_prices: dict[int, float] = {}
            for entry in historical:
                year = int(entry["date"][:4])
                if year not in year_prices:
                    year_prices[year] = float(entry["close"])
            return year_prices
        except Exception:
            return {}

    async def close(self) -> None:
        await self._client.aclose()


market_data_client = MarketDataClient()
