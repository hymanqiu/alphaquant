"""Runtime-adjustable settings.

Env vars provide the boot-time defaults (via ``backend.config.settings``). The
admin API can override them at runtime through ``RuntimeSettings.update``;
overrides live in memory and reset on process restart. Everything read during
request handling should come through ``get_runtime_settings()`` instead of
``settings`` directly, so admin changes take effect without a restart.

Two classes of fields are managed here:

1. **Numeric guardrails** (budget caps, rate limits) — admin can change these
   freely, no side effects beyond the next read.
2. **LLM provider config** (api_key / base_url / model for primary + narrative)
   — admin changes require invalidating the cached ``LLMClient`` singleton so
   the next request rebuilds with the new config. The admin handler does
   that explicitly via ``invalidate_llm_client()`` (see ``services.llm.client``).

Secret fields (api_key) are always redacted in admin GET responses; see
``EffectiveSettings.as_dict(redact=...)`` and the ``REDACTED_FIELDS`` set.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from backend.config import settings


# Numeric / non-secret fields. Admin PATCH validates as float / int / >=0.
_NUMERIC_FIELDS: set[str] = {
    "llm_daily_budget_usd",
    "llm_per_ip_daily_budget_usd",
    "rate_limit_analyze_per_ip_day",
    "rate_limit_recalculate_per_ip_day",
}

# LLM provider config — string fields. Admin PATCH stores raw string.
# Empty string acts as "no override; fall back to env" in ``_build_client``.
_LLM_STRING_FIELDS: set[str] = {
    "llm_api_key",
    "llm_base_url",
    "llm_model",
    "llm_narrative_api_key",
    "llm_narrative_base_url",
    "llm_narrative_model",
}

# Subset of the above that should be masked in admin responses.
REDACTED_FIELDS: frozenset[str] = frozenset({
    "llm_api_key",
    "llm_narrative_api_key",
})

# Subset that triggers an LLMClient rebuild when changed.
LLM_PROVIDER_FIELDS: frozenset[str] = frozenset(_LLM_STRING_FIELDS)

_ALLOWED_FIELDS: set[str] = _NUMERIC_FIELDS | _LLM_STRING_FIELDS


def _redact(value: str) -> str:
    """Return a masked form of *value* for admin GET responses."""
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    # Last 4 chars help admin confirm "yes that's the right key" without
    # actually exposing the secret.
    return f"***{value[-4:]}"


@dataclass
class EffectiveSettings:
    """Snapshot of the currently effective runtime settings."""

    llm_daily_budget_usd: float
    llm_per_ip_daily_budget_usd: float
    rate_limit_analyze_per_ip_day: int
    rate_limit_recalculate_per_ip_day: int
    # LLM provider config (string fields; "" means no override → use env)
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_narrative_api_key: str
    llm_narrative_base_url: str
    llm_narrative_model: str

    def as_dict(self, *, redact: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {
            "llm_daily_budget_usd": self.llm_daily_budget_usd,
            "llm_per_ip_daily_budget_usd": self.llm_per_ip_daily_budget_usd,
            "rate_limit_analyze_per_ip_day": self.rate_limit_analyze_per_ip_day,
            "rate_limit_recalculate_per_ip_day": self.rate_limit_recalculate_per_ip_day,
            "llm_api_key": self.llm_api_key,
            "llm_base_url": self.llm_base_url,
            "llm_model": self.llm_model,
            "llm_narrative_api_key": self.llm_narrative_api_key,
            "llm_narrative_base_url": self.llm_narrative_base_url,
            "llm_narrative_model": self.llm_narrative_model,
        }
        if redact:
            for k in REDACTED_FIELDS:
                if d.get(k):
                    d[k] = _redact(str(d[k]))
        return d


def redact_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    """Apply secret redaction to a raw overrides dict (for admin GET)."""
    out: dict[str, Any] = {}
    for k, v in overrides.items():
        if k in REDACTED_FIELDS and isinstance(v, str) and v:
            out[k] = _redact(v)
        else:
            out[k] = v
    return out


class RuntimeSettings:
    """Thread-safe overlay of admin-supplied overrides on top of env defaults."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._overrides: dict[str, Any] = {}

    def _env_value(self, key: str) -> Any:
        # Field names match the Settings attributes one-to-one.
        return getattr(settings, key)

    def snapshot(self) -> EffectiveSettings:
        """Return the currently effective values (env merged with overrides)."""
        with self._lock:
            merged = {k: self._overrides.get(k, self._env_value(k)) for k in _ALLOWED_FIELDS}
        return EffectiveSettings(**merged)  # type: ignore[arg-type]

    def update(self, patch: dict[str, Any]) -> EffectiveSettings:
        """Apply a partial update. Unknown keys raise ``KeyError``; type errors raise ``ValueError``."""
        validated: dict[str, Any] = {}
        for key, raw in patch.items():
            if key not in _ALLOWED_FIELDS:
                raise KeyError(key)
            validated[key] = _coerce(key, raw)

        with self._lock:
            self._overrides.update(validated)
        return self.snapshot()

    def reset(self, keys: list[str] | None = None) -> EffectiveSettings:
        """Remove one or more overrides (all if *keys* is None)."""
        with self._lock:
            if keys is None:
                self._overrides.clear()
            else:
                for k in keys:
                    self._overrides.pop(k, None)
        return self.snapshot()

    def overrides(self) -> dict[str, Any]:
        """Return a copy of the current override dict (for admin introspection).

        Use ``redact_overrides`` before exposing to admin clients.
        """
        with self._lock:
            return dict(self._overrides)

    def has_llm_overrides(self) -> bool:
        """True iff any LLM provider field is currently overridden."""
        with self._lock:
            return bool(self._overrides.keys() & LLM_PROVIDER_FIELDS)


def _coerce(key: str, value: Any) -> Any:
    if key in {"rate_limit_analyze_per_ip_day", "rate_limit_recalculate_per_ip_day"}:
        iv = int(value)
        if iv < 0:
            raise ValueError(f"{key} must be >= 0")
        return iv
    if key in {"llm_daily_budget_usd", "llm_per_ip_daily_budget_usd"}:
        fv = float(value)
        if fv < 0:
            raise ValueError(f"{key} must be >= 0")
        return fv
    if key in _LLM_STRING_FIELDS:
        if value is None:
            return ""
        sv = str(value).strip()
        # Light sanity-check on URL fields. We do NOT verify reachability —
        # admin is trusted; bad URLs surface as LLMProviderError on next call.
        if key in {"llm_base_url", "llm_narrative_base_url"} and sv:
            if not (sv.startswith("https://") or sv.startswith("http://localhost") or sv.startswith("http://127.0.0.1")):
                raise ValueError(
                    f"{key} must use https:// (or http://localhost / http://127.0.0.1)"
                )
        return sv
    return value


_runtime = RuntimeSettings()


def get_runtime_settings() -> RuntimeSettings:
    """Return the module-level ``RuntimeSettings`` singleton."""
    return _runtime
