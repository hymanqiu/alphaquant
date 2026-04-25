"""LLM budget gate.

Two circuit breakers guard every LLM call:

1. **Global daily budget** — if the last 24h of recorded spend exceeds the
   runtime-configured cap, ``check()`` raises :class:`LLMBudgetExceeded` with
   ``scope="global"``.
2. **Per-IP daily budget** — same logic, scoped to the caller's IP. Prevents
   a single client from draining the global budget within their rate-limit
   quota.

The gate is check-then-record: we look at what has been spent *so far* and
refuse if the **next** call would push over. We don't know the next call's
cost in advance, so we treat "already at or above the cap" as the trip
condition. For multi-call bursts this may over-shoot by one call; acceptable
for an MVP cost guardrail.
"""

from __future__ import annotations

import logging
import time

from backend.services.runtime_settings import RuntimeSettings, get_runtime_settings

from .accounting import AccountingStore
from .errors import LLMBudgetExceeded

logger = logging.getLogger(__name__)

_DAY_SECONDS = 24 * 60 * 60


class BudgetGate:
    """Encapsulates the two-tier budget check."""

    def __init__(
        self,
        *,
        accounting: AccountingStore,
        runtime_settings: RuntimeSettings | None = None,
    ) -> None:
        self._accounting = accounting
        self._runtime = runtime_settings or get_runtime_settings()

    def check(self, *, client_ip: str | None) -> None:
        """Raise :class:`LLMBudgetExceeded` if either budget is already spent."""
        settings_snapshot = self._runtime.snapshot()
        since = time.time() - _DAY_SECONDS

        global_spend = self._accounting.spend_since(since_ts=since)
        if global_spend >= settings_snapshot.llm_daily_budget_usd:
            logger.warning(
                "budget_tripped scope=global spent=%.4f limit=%.4f",
                global_spend, settings_snapshot.llm_daily_budget_usd,
            )
            raise LLMBudgetExceeded(
                f"Global daily LLM budget reached (${global_spend:.4f} / "
                f"${settings_snapshot.llm_daily_budget_usd:.2f})",
                scope="global",
                spent_usd=global_spend,
                limit_usd=settings_snapshot.llm_daily_budget_usd,
            )

        if client_ip:
            ip_spend = self._accounting.spend_since(
                since_ts=since, client_ip=client_ip,
            )
            if ip_spend >= settings_snapshot.llm_per_ip_daily_budget_usd:
                logger.warning(
                    "budget_tripped scope=per_ip ip=%s spent=%.4f limit=%.4f",
                    client_ip, ip_spend,
                    settings_snapshot.llm_per_ip_daily_budget_usd,
                )
                raise LLMBudgetExceeded(
                    f"Per-IP daily LLM budget reached (${ip_spend:.4f} / "
                    f"${settings_snapshot.llm_per_ip_daily_budget_usd:.2f})",
                    scope="per_ip",
                    spent_usd=ip_spend,
                    limit_usd=settings_snapshot.llm_per_ip_daily_budget_usd,
                )
