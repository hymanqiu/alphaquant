"""Token usage accounting for LLM calls.

Primary sink is a structured log line (one JSON per call) written to the
standard logger under the ``llm.accounting`` name. A small in-memory ring
buffer keeps the most recent N records for inspection during a session; this
is deliberately not durable — analysis history / billing will be wired into
Postgres in a later phase.

The store doubles as the source-of-truth for the cost-guardrail circuit
breakers: :func:`AccountingStore.spend_since` aggregates a sliding window
(global or per-IP).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Deque

logger = logging.getLogger("llm.accounting")

_MAX_RING_SIZE = 2000


@dataclass(frozen=True)
class LLMUsageRecord:
    """One LLM call's token usage and estimated cost."""

    task_tag: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    duration_ms: int
    timestamp: float
    client_ip: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AccountingStore:
    """Collects per-call token/cost records.

    The store is process-global (there is one per ``LLMClient``). Records are
    also flushed to a structured log so downstream tooling (e.g. log pipelines)
    can aggregate without touching memory.
    """

    def __init__(
        self,
        *,
        input_price_per_mtok: float,
        output_price_per_mtok: float,
    ) -> None:
        self._input_price = input_price_per_mtok
        self._output_price = output_price_per_mtok
        self._records: Deque[LLMUsageRecord] = deque(maxlen=_MAX_RING_SIZE)
        self._lock = threading.Lock()

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return round(
            (input_tokens / 1_000_000) * self._input_price
            + (output_tokens / 1_000_000) * self._output_price,
            6,
        )

    def record(
        self,
        *,
        task_tag: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        client_ip: str | None = None,
    ) -> LLMUsageRecord:
        rec = LLMUsageRecord(
            task_tag=task_tag,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self.estimate_cost(input_tokens, output_tokens),
            duration_ms=duration_ms,
            timestamp=time.time(),
            client_ip=client_ip,
        )
        with self._lock:
            self._records.append(rec)
        logger.info("llm_usage %s", json.dumps(rec.to_dict(), separators=(",", ":")))
        return rec

    # ------------------------------------------------------------------
    # Sliding-window aggregation (used by BudgetGate + admin endpoints)
    # ------------------------------------------------------------------

    def spend_since(self, *, since_ts: float, client_ip: str | None = None) -> float:
        """Sum ``estimated_cost_usd`` for records newer than *since_ts*.

        When *client_ip* is given, only records tagged with that IP are
        counted. Records with ``client_ip=None`` are treated as global — they
        count toward the global total but not any per-IP total.
        """
        with self._lock:
            snapshot = list(self._records)
        total = 0.0
        for r in snapshot:
            if r.timestamp < since_ts:
                continue
            if client_ip is not None and r.client_ip != client_ip:
                continue
            total += r.estimated_cost_usd
        return round(total, 6)

    def recent(self, n: int = 50) -> list[LLMUsageRecord]:
        """Return the most recent *n* records (newest last)."""
        with self._lock:
            if n >= len(self._records):
                return list(self._records)
            return list(self._records)[-n:]

    def records_since(self, *, since_ts: float) -> list[LLMUsageRecord]:
        with self._lock:
            return [r for r in self._records if r.timestamp >= since_ts]

    def total_cost_usd(self) -> float:
        with self._lock:
            return round(sum(r.estimated_cost_usd for r in self._records), 6)
