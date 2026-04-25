"""Per-IP sliding-window rate limiter.

Tracks timestamps of recent requests per IP, per "bucket" (one bucket per API
endpoint group). When a request arrives, stale timestamps are dropped and the
remaining count is compared against the bucket's limit (sourced from
``RuntimeSettings`` so admin changes take effect immediately).

Storage is an in-memory dict — fine for a single-instance MVP. Swap for Redis
if we ever go multi-instance.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from backend.services.runtime_settings import RuntimeSettings, get_runtime_settings


_WINDOW_SECONDS = 24 * 60 * 60

# --- Bucket keys -----------------------------------------------------------
# Stable identifiers for the limit lookup. Add a new constant per API group.

BUCKET_ANALYZE = "analyze"
BUCKET_RECALCULATE = "recalculate"

_BUCKET_LIMIT_FIELD = {
    BUCKET_ANALYZE: "rate_limit_analyze_per_ip_day",
    BUCKET_RECALCULATE: "rate_limit_recalculate_per_ip_day",
}


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of :meth:`IPRateLimiter.check_and_record`."""

    allowed: bool
    remaining: int
    limit: int
    retry_after_seconds: int  # 0 when allowed


class IPRateLimiter:
    """Tracks request timestamps per (bucket, ip) and enforces daily limits."""

    def __init__(
        self,
        *,
        runtime_settings: RuntimeSettings | None = None,
    ) -> None:
        self._runtime = runtime_settings or get_runtime_settings()
        self._lock = threading.Lock()
        self._log: dict[tuple[str, str], Deque[float]] = defaultdict(deque)

    def _limit_for(self, bucket: str) -> int:
        field = _BUCKET_LIMIT_FIELD[bucket]
        return int(getattr(self._runtime.snapshot(), field))

    def check_and_record(
        self, *, bucket: str, client_ip: str,
    ) -> RateLimitDecision:
        """Atomically check the limit and record the request if allowed."""
        limit = self._limit_for(bucket)
        now = time.time()
        cutoff = now - _WINDOW_SECONDS
        key = (bucket, client_ip)

        with self._lock:
            dq = self._log[key]
            while dq and dq[0] < cutoff:
                dq.popleft()

            if limit <= 0:
                return RateLimitDecision(
                    allowed=False, remaining=0, limit=limit,
                    retry_after_seconds=_WINDOW_SECONDS,
                )

            if len(dq) >= limit:
                # Retry after the oldest timestamp ages out.
                retry = max(1, int(dq[0] + _WINDOW_SECONDS - now))
                return RateLimitDecision(
                    allowed=False, remaining=0, limit=limit,
                    retry_after_seconds=retry,
                )

            dq.append(now)
            return RateLimitDecision(
                allowed=True, remaining=limit - len(dq), limit=limit,
                retry_after_seconds=0,
            )

    def snapshot(self) -> dict[str, list[dict[str, object]]]:
        """Inspection helper: counts per (bucket, ip) in the live window.

        Returns ``{bucket_name: [{"ip": ..., "count": ...}, ...]}``.
        """
        now = time.time()
        cutoff = now - _WINDOW_SECONDS
        out: dict[str, list[dict[str, object]]] = defaultdict(list)
        with self._lock:
            for (bucket, ip), dq in self._log.items():
                fresh = sum(1 for ts in dq if ts >= cutoff)
                if fresh:
                    out[bucket].append({"ip": ip, "count": fresh})
        # Sort each bucket by count descending for admin UX.
        for bucket, rows in out.items():
            rows.sort(key=lambda r: r["count"], reverse=True)  # type: ignore[arg-type,return-value]
        return dict(out)


_rate_limiter = IPRateLimiter()


def get_rate_limiter() -> IPRateLimiter:
    """Return the module-level ``IPRateLimiter`` singleton."""
    return _rate_limiter
