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
    # Small in-process FIFO cache of downloaded 10-K filings keyed by
    # accession_number. The HTML is ~1-2 MB so we cap at a handful of entries
    # to avoid memory blow-up; evictions are FIFO. The win is when a single
    # analysis request walks the same filing through multiple nodes (e.g.
    # qualitative + risk_yoy_diff both touch the latest 10-K).
    _10K_CACHE_MAX = 6

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.sec_base_url,
            headers={"User-Agent": settings.sec_user_agent},
            timeout=30.0,
        )
        self._last_request_time: float = 0
        self._lock = asyncio.Lock()
        self._10k_cache: dict[str, dict[str, Any]] = {}
        self._10k_cache_order: list[str] = []

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

        # Submissions response nests recent filings under `filings.recent`.
        recent = (data.get("filings") or {}).get("recent", {})
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

    def _cache_get(self, accession: str) -> dict[str, Any] | None:
        return self._10k_cache.get(accession)

    def _cache_put(self, accession: str, payload: dict[str, Any]) -> None:
        if accession in self._10k_cache:
            return
        self._10k_cache[accession] = payload
        self._10k_cache_order.append(accession)
        while len(self._10k_cache_order) > self._10K_CACHE_MAX:
            evict = self._10k_cache_order.pop(0)
            self._10k_cache.pop(evict, None)

    async def fetch_10k(
        self, cik: int, *, n_back: int = 0, max_bytes: int = 20_000_000,
    ) -> dict[str, Any] | None:
        """Download the HTML of one of the company's 10-K filings.

        ``n_back=0`` returns the most recent 10-K, ``n_back=1`` the prior one,
        and so on. Returns ``{"accession_number": ..., "filing_date": ...,
        "url": ..., "html": ...}`` or ``None`` if the filing isn't available
        or the download fails.

        Filings are cached in-process by accession_number (FIFO, max 6) so
        that a single analysis request walking the same filing through
        multiple nodes only pays the network cost once.
        """
        if n_back < 0:
            return None

        await self._rate_limit()
        padded = str(cik).zfill(10)
        try:
            resp = await self._client.get(f"/submissions/CIK{padded}.json")
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning("SEC fetch_10k CIK=%s list error: %s", padded, e)
            return None

        recent = (data.get("filings") or {}).get("recent", {})
        if not recent:
            return None

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        # Collect all 10-K filings as (filing_date, accession, primary_doc)
        # then sort newest-first.
        candidates: list[tuple[str, str, str]] = []
        for i, form in enumerate(forms):
            if form != "10-K":
                continue
            candidates.append((
                dates[i] if i < len(dates) else "",
                accessions[i] if i < len(accessions) else "",
                primary_docs[i] if i < len(primary_docs) else "",
            ))
        candidates.sort(key=lambda t: t[0], reverse=True)

        if n_back >= len(candidates):
            logger.info(
                "SEC fetch_10k CIK=%s n_back=%d: only %d 10-K filings found",
                padded, n_back, len(candidates),
            )
            return None

        filing_date, accession, primary_doc = candidates[n_back]
        if not accession or not primary_doc or not primary_doc.lower().endswith((".htm", ".html")):
            logger.info(
                "SEC fetch_10k CIK=%s n_back=%d: missing or non-html primary doc (%s)",
                padded, n_back, primary_doc,
            )
            return None

        cached = self._cache_get(accession)
        if cached is not None:
            return cached

        accession_nodashes = accession.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession_nodashes}/{primary_doc}"
        )

        await self._rate_limit()
        try:
            html_resp = await self._client.get(url)
            html_resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning(
                "SEC fetch_10k CIK=%s n_back=%d download error: %s",
                padded, n_back, e,
            )
            return None

        content = html_resp.content
        if len(content) > max_bytes:
            logger.warning(
                "SEC fetch_10k CIK=%s n_back=%d payload %d bytes > cap %d; refusing",
                padded, n_back, len(content), max_bytes,
            )
            return None

        try:
            html = content.decode("utf-8", errors="replace")
        except Exception as e:  # pragma: no cover
            logger.warning(
                "SEC fetch_10k CIK=%s n_back=%d decode error: %s",
                padded, n_back, e,
            )
            return None

        payload = {
            "accession_number": accession,
            "filing_date": filing_date,
            "url": url,
            "html": html,
        }
        self._cache_put(accession, payload)
        return payload

    async def fetch_latest_10k(
        self, cik: int, *, max_bytes: int = 20_000_000,
    ) -> dict[str, Any] | None:
        """Backward-compatible alias for ``fetch_10k(cik, n_back=0)``."""
        return await self.fetch_10k(cik, n_back=0, max_bytes=max_bytes)


sec_client = SECClient()
