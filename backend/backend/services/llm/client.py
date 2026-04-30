"""Unified LLM client.

All LLM-powered features should go through this module's ``get_llm_client()``.
The client:
- Loads prompt templates from ``backend.prompts`` (YAML).
- Renders them with user-supplied variables.
- Calls the configured provider with a structured JSON response format.
- Parses + optionally validates the response against a Pydantic model.
- Records token usage to the accounting store.
- Retries once on transient failures.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, TypeVar, overload

import httpx
from pydantic import BaseModel, ValidationError

from backend.config import settings
from backend.services.request_context import current_client_ip
from backend.services.runtime_settings import get_runtime_settings

from .accounting import AccountingStore
from .budget import BudgetGate
from .errors import LLMConfigError, LLMError, LLMParseError, LLMProviderError
from .providers import OpenAICompatibleProvider, Provider, ProviderResponse

logger = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)


def _strip_code_fences(content: str) -> str:
    """Remove ```json ... ``` fences if the model wrapped its output."""
    stripped = content.strip()
    if not stripped.startswith("```"):
        return content
    lines = stripped.split("\n")
    lines = [line for line in lines if not line.strip().startswith("```")]
    return "\n".join(lines)


class LLMClient:
    """Single entry point for LLM calls across the app."""

    def __init__(
        self,
        *,
        primary: Provider,
        narrative: Provider | None,
        accounting: AccountingStore,
        budget_gate: BudgetGate | None = None,
        max_retries: int = 1,
    ) -> None:
        self._primary = primary
        self._narrative = narrative or primary
        self._accounting = accounting
        self._budget_gate = budget_gate or BudgetGate(accounting=accounting)
        self._max_retries = max_retries

    def _select_provider(self, task_tag: str) -> Provider:
        # Narrative-quality tasks route to the dedicated provider when one is
        # configured; otherwise fall back to the primary.
        if task_tag in {"thesis", "report_summary"}:
            return self._narrative
        return self._primary

    @overload
    async def complete_json(
        self,
        *,
        prompt_name: str,
        variables: dict[str, Any],
        task_tag: str,
        response_model: type[M],
        version: int = ...,
        temperature: float | None = ...,
        max_tokens: int | None = ...,
    ) -> M: ...

    @overload
    async def complete_json(
        self,
        *,
        prompt_name: str,
        variables: dict[str, Any],
        task_tag: str,
        response_model: None = ...,
        version: int = ...,
        temperature: float | None = ...,
        max_tokens: int | None = ...,
    ) -> dict[str, Any]: ...

    async def complete_json(
        self,
        *,
        prompt_name: str,
        variables: dict[str, Any],
        task_tag: str,
        response_model: type[BaseModel] | None = None,
        version: int = 1,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Render *prompt_name* v*version*, call the LLM, return parsed JSON.

        When *response_model* is given, validates the response against it and
        returns the Pydantic instance; otherwise returns the parsed dict.

        Raises ``LLMError`` (or subclass) on any failure. Callers that want
        graceful degradation should catch it.
        """
        # Lazy-import to avoid a circular dependency at module-import time.
        from backend.prompts import load_prompt

        template = load_prompt(prompt_name, version=version)
        try:
            user = template.user.format(**variables)
        except KeyError as e:
            raise LLMParseError(
                f"prompt '{prompt_name}' v{version} missing variable {e}"
            ) from e

        provider = self._select_provider(task_tag)
        effective_temperature = (
            temperature if temperature is not None else template.temperature
        )
        effective_max_tokens = (
            max_tokens if max_tokens is not None else template.max_tokens
        )

        client_ip = current_client_ip()
        # Budget gate — raises LLMBudgetExceeded when tripped. Callers catch
        # LLMError to degrade, so the same graceful-degrade path kicks in.
        self._budget_gate.check(client_ip=client_ip)

        last_error: Exception | None = None
        attempts = self._max_retries + 1
        for attempt in range(1, attempts + 1):
            start = time.monotonic()
            try:
                resp: ProviderResponse = await provider.chat_completion(
                    system=template.system,
                    user=user,
                    temperature=effective_temperature,
                    max_tokens=effective_max_tokens,
                    response_format_json=True,
                )
                content = _strip_code_fences(resp.content)
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as e:
                    raise LLMParseError(
                        f"prompt '{prompt_name}' returned invalid JSON: {e}"
                    ) from e

                duration_ms = int((time.monotonic() - start) * 1000)
                self._accounting.record(
                    task_tag=task_tag,
                    provider=provider.name,
                    model=provider.model,
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                    duration_ms=duration_ms,
                    client_ip=client_ip,
                )

                if response_model is None:
                    if not isinstance(parsed, dict):
                        raise LLMParseError(
                            f"prompt '{prompt_name}' expected JSON object, got {type(parsed).__name__}"
                        )
                    return parsed

                try:
                    return response_model.model_validate(parsed)
                except ValidationError as e:
                    raise LLMParseError(
                        f"prompt '{prompt_name}' response failed {response_model.__name__}: {e}"
                    ) from e

            except (LLMProviderError, LLMParseError) as e:
                last_error = e
                retriable = isinstance(e, LLMParseError) or (
                    isinstance(e, LLMProviderError)
                    and (e.status_code is None or e.status_code in {429, 500, 502, 503, 504})
                )
                if attempt < attempts and retriable:
                    logger.warning(
                        "llm_retry prompt=%s attempt=%d/%d reason=%s",
                        prompt_name, attempt, attempts, e,
                    )
                    # Small backoff; DeepSeek rate limits don't need exponential.
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise

        # Unreachable given the loop structure, but keeps mypy happy.
        raise last_error or LLMError(f"prompt '{prompt_name}' failed with no error captured")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_http_client: httpx.AsyncClient | None = None
_llm_client: LLMClient | None = None
_accounting_store: AccountingStore | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
    return _http_client


def get_accounting_store() -> AccountingStore:
    """Return the process-wide AccountingStore singleton.

    Created lazily so it is available to admin endpoints even when the LLM
    itself is not configured — useful for the "LLM disabled but I still want
    to see that no charges happened" case.
    """
    global _accounting_store
    if _accounting_store is None:
        _accounting_store = AccountingStore(
            input_price_per_mtok=settings.llm_price_input_per_mtok,
            output_price_per_mtok=settings.llm_price_output_per_mtok,
        )
    return _accounting_store


def _resolve(override: str, env_value: str) -> str:
    """Override-with-env-fallback. Empty override = use env."""
    return override if override else env_value


def _effective_llm_config() -> dict[str, str]:
    """Compute the LLM provider config in effect right now.

    Override (RuntimeSettings, set by admin PATCH) wins over env. Empty
    override falls back to env. This is the single source of truth read by
    both ``_build_client`` and ``is_llm_configured``.
    """
    rt = get_runtime_settings().snapshot()
    return {
        "api_key": _resolve(rt.llm_api_key, settings.llm_api_key),
        "base_url": _resolve(rt.llm_base_url, settings.llm_base_url),
        "model": _resolve(rt.llm_model, settings.llm_model) or "deepseek-chat",
        "narrative_api_key": _resolve(
            rt.llm_narrative_api_key, settings.llm_narrative_api_key,
        ),
        "narrative_base_url": _resolve(
            rt.llm_narrative_base_url, settings.llm_narrative_base_url,
        ),
        "narrative_model": _resolve(
            rt.llm_narrative_model, settings.llm_narrative_model,
        ),
    }


def _build_client() -> LLMClient:
    cfg = _effective_llm_config()
    if not cfg["api_key"] or not cfg["base_url"]:
        raise LLMConfigError(
            "LLM not configured: AQ_LLM_API_KEY and AQ_LLM_BASE_URL must be set "
            "(or override via PATCH /api/admin/settings)"
        )

    http_client = _get_http_client()
    primary = OpenAICompatibleProvider(
        name="primary",
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        http_client=http_client,
    )
    narrative: Provider | None = None
    if cfg["narrative_api_key"] and cfg["narrative_base_url"]:
        narrative = OpenAICompatibleProvider(
            name="narrative",
            api_key=cfg["narrative_api_key"],
            base_url=cfg["narrative_base_url"],
            model=cfg["narrative_model"] or cfg["model"],
            http_client=http_client,
        )

    accounting = get_accounting_store()
    return LLMClient(
        primary=primary,
        narrative=narrative,
        accounting=accounting,
        max_retries=settings.llm_max_retries,
    )


def get_llm_client() -> LLMClient:
    """Return the lazily-initialized global LLM client.

    Raises ``LLMConfigError`` if required env vars are missing. Callers that
    want to gracefully degrade should check ``is_llm_configured()`` first or
    catch the error.
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = _build_client()
    return _llm_client


def is_llm_configured() -> bool:
    """True iff there is a usable api_key + base_url after applying overrides."""
    cfg = _effective_llm_config()
    return bool(cfg["api_key"] and cfg["base_url"])


def invalidate_llm_client() -> None:
    """Drop the cached ``LLMClient`` so the next ``get_llm_client`` rebuilds.

    Used by the admin handler after PATCHing LLM provider fields. The shared
    httpx connection pool (``_http_client``) is NOT closed — switching to a
    different ``base_url`` just opens new connections to the new host on the
    same pool. Accounting state is preserved (so spend history survives).

    In-flight requests using the old client continue to completion; only
    subsequent ``get_llm_client()`` calls observe the change.
    """
    global _llm_client
    _llm_client = None


async def close_llm_client() -> None:
    """Tear down the shared HTTP client. Call during app shutdown."""
    global _http_client, _llm_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
    _llm_client = None
    # Intentionally keep ``_accounting_store`` across restarts of the inner
    # client (e.g. dev reloads) — it is pure in-memory data and its lifetime
    # matches the process, not the LLM client.
