"""Exception hierarchy for LLM operations.

Callers should catch ``LLMError`` to gracefully degrade. Specific subclasses
are provided for logging/telemetry purposes.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM operation failures."""


class LLMConfigError(LLMError):
    """LLM is not configured (missing api key / base url) or misconfigured."""


class LLMProviderError(LLMError):
    """Upstream provider returned an error (HTTP / network / timeout)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMParseError(LLMError):
    """LLM response could not be parsed as JSON or failed schema validation."""


class LLMBudgetExceeded(LLMError):
    """Cost guardrail tripped — call was refused before hitting the provider.

    ``scope`` is ``"global"`` or ``"per_ip"`` so downstream logs / dashboards
    can distinguish the two cases.
    """

    def __init__(
        self,
        message: str,
        *,
        scope: str,
        spent_usd: float,
        limit_usd: float,
    ) -> None:
        super().__init__(message)
        self.scope = scope
        self.spent_usd = spent_usd
        self.limit_usd = limit_usd
