"""Runtime-adjustable settings.

Env vars provide the boot-time defaults (via ``backend.config.settings``). The
admin API can override them at runtime through ``RuntimeSettings.update``;
overrides live in memory and reset on process restart. Everything read during
request handling should come through ``get_runtime_settings()`` instead of
``settings`` directly, so admin changes take effect without a restart.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from backend.config import settings


_ALLOWED_FIELDS: set[str] = {
    "llm_daily_budget_usd",
    "llm_per_ip_daily_budget_usd",
    "rate_limit_analyze_per_ip_day",
    "rate_limit_recalculate_per_ip_day",
}


@dataclass
class EffectiveSettings:
    """Snapshot of the currently effective runtime settings."""

    llm_daily_budget_usd: float
    llm_per_ip_daily_budget_usd: float
    rate_limit_analyze_per_ip_day: int
    rate_limit_recalculate_per_ip_day: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "llm_daily_budget_usd": self.llm_daily_budget_usd,
            "llm_per_ip_daily_budget_usd": self.llm_per_ip_daily_budget_usd,
            "rate_limit_analyze_per_ip_day": self.rate_limit_analyze_per_ip_day,
            "rate_limit_recalculate_per_ip_day": self.rate_limit_recalculate_per_ip_day,
        }


class RuntimeSettings:
    """Thread-safe overlay of admin-supplied overrides on top of env defaults."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._overrides: dict[str, Any] = {}

    def _env_value(self, key: str) -> Any:
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
        """Return a copy of the current override dict (for admin introspection)."""
        with self._lock:
            return dict(self._overrides)


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
    return value


_runtime = RuntimeSettings()


def get_runtime_settings() -> RuntimeSettings:
    """Return the module-level ``RuntimeSettings`` singleton."""
    return _runtime
