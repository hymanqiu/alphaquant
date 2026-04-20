"""FMP (Financial Modeling Prep) client for market price data.

Uses the /stable/ API endpoints (FMP deprecated /api/v3/ in Aug 2025).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class MarketDataClient:
    """Lazy-initialized async FMP client. Call ``close()`` during app shutdown."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=settings.fmp_base_url,
                timeout=15.0,
            )
        return self._client

    async def get_current_price(self, ticker: str) -> float | None:
        """Fetch the latest market price for a ticker. Returns None on failure."""
        if not settings.fmp_api_key:
            return None
        try:
            resp = await self._ensure_client().get(
                "/stable/quote",
                params={"symbol": ticker, "apikey": settings.fmp_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                return float(data[0]["price"])
        except httpx.HTTPStatusError as e:
            logger.warning("FMP get_current_price(%s) HTTP %s", ticker, e.response.status_code)
        except httpx.RequestError as e:
            logger.warning("FMP get_current_price(%s) request error: %s", ticker, e)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("FMP get_current_price(%s) parse error: %s", ticker, e)
        return None

    async def get_company_profile(self, ticker: str) -> dict[str, Any]:
        """Fetch GICS sector/industry, TTM dividend, and price. Returns {} on failure.

        Also returns ``price`` — the profile endpoint includes it and works on
        FMP free-tier symbols that ``/stable/quote`` rejects as premium-only.
        """
        if not settings.fmp_api_key:
            return {}
        try:
            resp = await self._ensure_client().get(
                "/stable/profile",
                params={"symbol": ticker, "apikey": settings.fmp_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                item = data[0]
                last_div = item.get("lastDividend")
                price = item.get("price")
                return {
                    "sector": item.get("sector") or None,
                    "industry": item.get("industry") or None,
                    "last_dividend": float(last_div) if last_div else None,
                    "price": float(price) if price else None,
                }
        except httpx.HTTPStatusError as e:
            logger.warning("FMP get_company_profile(%s) HTTP %s", ticker, e.response.status_code)
        except httpx.RequestError as e:
            logger.warning("FMP get_company_profile(%s) request error: %s", ticker, e)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("FMP get_company_profile(%s) parse error: %s", ticker, e)
        return {}

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
            resp = await self._ensure_client().get(
                "/stable/historical-price-eod/full",
                params={
                    "symbol": ticker,
                    "apikey": settings.fmp_api_key,
                    "from": from_date.isoformat(),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if not data or not isinstance(data, list):
                return {}

            # Enforce newest-first ordering (don't rely on API sort order)
            sorted_data = sorted(data, key=lambda e: e["date"], reverse=True)

            year_prices: dict[int, float] = {}
            for entry in sorted_data:
                year = int(entry["date"][:4])
                if year not in year_prices:
                    year_prices[year] = float(entry["close"])
            return year_prices
        except httpx.HTTPStatusError as e:
            logger.warning("FMP get_annual_closing_prices(%s) HTTP %s", ticker, e.response.status_code)
        except httpx.RequestError as e:
            logger.warning("FMP get_annual_closing_prices(%s) request error: %s", ticker, e)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("FMP get_annual_closing_prices(%s) parse error: %s", ticker, e)
        return {}

    async def get_peers(self, ticker: str) -> list[str]:
        """Fetch peer tickers for a company. Returns empty list on failure."""
        if not settings.fmp_api_key:
            return []
        try:
            resp = await self._ensure_client().get(
                "/stable/stock-peers",
                params={"symbol": ticker, "apikey": settings.fmp_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, list):
                return [p["symbol"] for p in data if "symbol" in p and p["symbol"].upper() != ticker.upper()][:10]
        except httpx.HTTPStatusError as e:
            logger.warning("FMP get_peers(%s) HTTP %s", ticker, e.response.status_code)
        except httpx.RequestError as e:
            logger.warning("FMP get_peers(%s) request error: %s", ticker, e)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("FMP get_peers(%s) parse error: %s", ticker, e)
        return []

    async def get_peer_key_metrics_ttm(self, ticker: str) -> dict[str, float | None]:
        """Fetch TTM valuation ratios (P/E, P/B, P/S, EV/Revenue, EV/FCF, PEG) for a ticker."""
        if not settings.fmp_api_key:
            return {}
        try:
            resp = await self._ensure_client().get(
                "/stable/ratios-ttm",
                params={"symbol": ticker, "apikey": settings.fmp_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                item = data[0]
                return {
                    "peRatio": item.get("priceToEarningsRatioTTM"),
                    "pbRatio": item.get("priceToBookRatioTTM"),
                    "priceToSalesRatio": item.get("priceToSalesRatioTTM"),
                    "evToRevenue": item.get("enterpriseValueMultipleTTM"),
                    "evToFreeCashFlow": item.get("priceToFreeCashFlowRatioTTM"),
                    "pegRatio": item.get("priceToEarningsGrowthRatioTTM"),
                }
        except httpx.HTTPStatusError as e:
            logger.warning("FMP get_peer_key_metrics_ttm(%s) HTTP %s", ticker, e.response.status_code)
        except httpx.RequestError as e:
            logger.warning("FMP get_peer_key_metrics_ttm(%s) request error: %s", ticker, e)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("FMP get_peer_key_metrics_ttm(%s) parse error: %s", ticker, e)
        return {}

    async def get_batch_peer_metrics(
        self, peers: list[str]
    ) -> dict[str, dict[str, float | None]]:
        """Fetch key metrics for multiple peers concurrently."""
        results = await asyncio.gather(
            *(self.get_peer_key_metrics_ttm(p) for p in peers),
            return_exceptions=True,
        )
        output: dict[str, dict[str, float | None]] = {}
        for peer, result in zip(peers, results):
            if isinstance(result, Exception):
                logger.warning("FMP batch metrics error for %s: %s", peer, result)
                output[peer] = {}
            else:
                output[peer] = result
        return output

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


market_data_client = MarketDataClient()
