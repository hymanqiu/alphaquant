"""Raw HTTP client for SEC EDGAR API."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

from backend.config import settings
from backend.models.sec import SECCompanyFacts

logger = logging.getLogger(__name__)


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

    async def get_recent_8k_filings(
        self, cik: int, days: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch recent 8-K filings from SEC EDGAR submissions endpoint.

        Args:
            cik: Central Index Key (integer, e.g. 1045810).
            days: Look-back window in days.

        Returns:
            List of dicts with ``filing_date``, ``accession_number``, ``form``,
            ``report_date``, ``description``, and ``url``.
        """
        await self._rate_limit()
        padded = str(cik).zfill(10)
        try:
            resp = await self._client.get(
                f"/submissions/CIK{padded}.json"
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(
                "SEC get_recent_8k_filings CIK=%s HTTP %s",
                padded, e.response.status_code,
            )
            return []
        except httpx.RequestError as e:
            logger.warning("SEC get_recent_8k_filings CIK=%s error: %s", padded, e)
            return []

        recent = data.get("recent", {})
        if not recent:
            return []

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        report_dates = recent.get("reportDate", [])
        descriptions = recent.get("primaryDocDescription", [])

        cutoff = (date.today() - timedelta(days=days)).isoformat()

        filings: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form != "8-K":
                continue
            filing_date = dates[i] if i < len(dates) else ""
            if filing_date < cutoff:
                continue

            accession = accessions[i] if i < len(accessions) else ""
            # Build the SEC URL: accession uses dashes in the path
            accession_dashes = accession.replace("-", "")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik}/{accession_dashes}/{accession}.htm"
            )

            filings.append({
                "filing_date": filing_date,
                "accession_number": accession,
                "form": "8-K",
                "report_date": report_dates[i] if i < len(report_dates) else "",
                "description": descriptions[i] if i < len(descriptions) else "",
                "url": url,
            })

        return filings


sec_client = SECClient()
