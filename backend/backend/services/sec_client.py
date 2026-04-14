"""Raw HTTP client for SEC EDGAR API."""

from __future__ import annotations

import asyncio

import httpx

from backend.config import settings
from backend.models.sec import SECCompanyFacts


class SECClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.sec_base_url,
            headers={"User-Agent": settings.sec_user_agent},
            timeout=30.0,
        )
        self._last_request_time: float = 0
        self._lock = asyncio.Lock()

    async def _rate_limit(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < settings.sec_rate_limit:
                await asyncio.sleep(settings.sec_rate_limit - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def get_company_facts(self, cik: int) -> SECCompanyFacts:
        await self._rate_limit()
        padded = str(cik).zfill(10)
        resp = await self._client.get(
            f"/api/xbrl/companyfacts/CIK{padded}.json"
        )
        resp.raise_for_status()
        return SECCompanyFacts.model_validate(resp.json())

    async def close(self) -> None:
        await self._client.aclose()


sec_client = SECClient()
