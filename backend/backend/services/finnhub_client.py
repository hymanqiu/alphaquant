"""Finnhub client for news and insider sentiment data.

Uses Finnhub Free plan endpoints. Premium endpoints gracefully degrade.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# Number of days per API request chunk.
# Finnhub may cap results for large date ranges; 7-day chunks ensure
# full coverage across the entire window.
_CHUNK_DAYS = 7


class FinnhubClient:
    """Lazy-initialized async Finnhub client. Call ``close()`` during app shutdown."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=settings.finnhub_base_url,
                timeout=15.0,
            )
        return self._client

    async def _fetch_news_chunk(
        self, ticker: str, from_date: date, to_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch news for a single date chunk. Returns empty list on failure."""
        try:
            resp = await self._ensure_client().get(
                "/company-news",
                params={
                    "symbol": ticker,
                    "from": from_date.isoformat(),
                    "to": to_date.isoformat(),
                    "token": settings.finnhub_api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Finnhub news chunk (%s %s→%s) HTTP %s",
                ticker, from_date, to_date, e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.warning(
                "Finnhub news chunk (%s %s→%s) error: %s",
                ticker, from_date, to_date, e,
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(
                "Finnhub news chunk (%s %s→%s) parse error: %s",
                ticker, from_date, to_date, e,
            )
        return []

    async def get_company_news(
        self, ticker: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch company news from Finnhub using weekly-batch requests.

        Splits the date range into 7-day chunks to avoid undocumented
        result caps on the Finnhub ``/company-news`` endpoint.  Results
        are deduplicated by article ``id`` and sorted by datetime
        descending (most recent first).

        Returns empty list on failure.
        """
        if not settings.finnhub_api_key:
            return []
        days = max(1, min(days, 90))

        today = date.today()
        range_start = today - timedelta(days=days)

        # Build weekly date chunks
        chunks: list[tuple[date, date]] = []
        current = range_start
        while current < today:
            chunk_end = min(current + timedelta(days=_CHUNK_DAYS), today)
            chunks.append((current, chunk_end))
            current = chunk_end + timedelta(days=1)

        # Fetch all chunks concurrently (respecting Finnhub's ~10 req/s limit)
        # Use a semaphore to avoid overwhelming the API
        semaphore = asyncio.Semaphore(3)
        all_articles: list[dict[str, Any]] = []

        async def _fetch_with_sem(
            chunk: tuple[date, date],
        ) -> list[dict[str, Any]]:
            async with semaphore:
                # Small stagger to be a good API citizen
                await asyncio.sleep(0.1)
                return await self._fetch_news_chunk(ticker, chunk[0], chunk[1])

        results = await asyncio.gather(
            *[_fetch_with_sem(c) for c in chunks],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)

        # Deduplicate by article id
        seen_ids: set[int] = set()
        unique: list[dict[str, Any]] = []
        for article in all_articles:
            art_id = article.get("id")
            if art_id is not None and art_id in seen_ids:
                continue
            if art_id is not None:
                seen_ids.add(art_id)
            unique.append(article)

        # Sort by datetime descending (most recent first)
        unique.sort(
            key=lambda a: a.get("datetime", 0) or 0,
            reverse=True,
        )

        logger.info(
            "Finnhub get_company_news(%s, %d days): %d chunks → %d raw → %d unique",
            ticker, days, len(chunks), len(all_articles), len(unique),
        )

        return unique

    async def get_news_sentiment(self, ticker: str) -> dict[str, Any] | None:
        """Fetch news sentiment from Finnhub. Returns None on failure (Premium only).

        Premium plan endpoint: /news-sentiment
        """
        if not settings.finnhub_api_key:
            return None
        try:
            resp = await self._ensure_client().get(
                "/news-sentiment",
                params={"symbol": ticker, "token": settings.finnhub_api_key},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            # 403 likely means Free plan — don't warn loudly
            if e.response.status_code != 403:
                logger.warning(
                    "Finnhub get_news_sentiment(%s) HTTP %s",
                    ticker,
                    e.response.status_code,
                )
        except httpx.RequestError as e:
            logger.warning(
                "Finnhub get_news_sentiment(%s) request error: %s", ticker, e
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(
                "Finnhub get_news_sentiment(%s) parse error: %s", ticker, e
            )
        return None

    async def get_insider_sentiment(
        self, ticker: str, months: int = 3
    ) -> dict[str, Any] | None:
        """Fetch insider sentiment from Finnhub. Returns None on failure.

        Free plan endpoint: /stock/insider-sentiment
        """
        if not settings.finnhub_api_key:
            return None
        months = max(1, min(months, 12))
        try:
            today = date.today()
            from_date = today - timedelta(days=months * 30)
            resp = await self._ensure_client().get(
                "/stock/insider-sentiment",
                params={
                    "symbol": ticker,
                    "from": from_date.strftime("%Y-%m"),
                    "to": today.strftime("%Y-%m"),
                    "token": settings.finnhub_api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, dict):
                return data
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Finnhub get_insider_sentiment(%s) HTTP %s",
                ticker,
                e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.warning(
                "Finnhub get_insider_sentiment(%s) request error: %s", ticker, e
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(
                "Finnhub get_insider_sentiment(%s) parse error: %s", ticker, e
            )
        return None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


finnhub_client = FinnhubClient()
