"""Admin API: usage telemetry + runtime settings editing.

All endpoints require a bearer token matching ``AQ_ADMIN_TOKEN``. When the
env var is empty the router refuses every request with 503 so a misconfigured
deployment cannot accidentally expose the admin surface.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.services.auth import AuthError, AuthService
from backend.services.db import get_session, is_db_configured
from backend.services.llm import get_accounting_store, invalidate_llm_client
from backend.services.rate_limit import get_rate_limiter
from backend.services.runtime_settings import (
    LLM_PROVIDER_FIELDS,
    REDACTED_FIELDS,
    get_runtime_settings,
    redact_overrides,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

_DAY_SECONDS = 24 * 60 * 60


def require_admin(
    authorization: str | None = Header(default=None),
) -> None:
    """Bearer-token guard. Returns only when the token matches."""
    expected = settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin API disabled (AQ_ADMIN_TOKEN not configured).",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid admin token")


class SettingsPatch(BaseModel):
    """Body for PATCH /api/admin/settings. All fields optional.

    Fields fall into two groups:

    - **Numeric guardrails** (budget caps, rate limits): take effect on the
      next read.
    - **LLM provider config**: a change to any of these triggers
      ``invalidate_llm_client()`` so the cached LLMClient singleton is
      rebuilt with the new config on the next request.

    Empty string for an LLM field == "remove override; fall back to env".
    To roll back ALL overrides at once, use ``POST /settings/reset``.
    """

    model_config = ConfigDict(extra="forbid")

    # Numeric guardrails
    llm_daily_budget_usd: float | None = None
    llm_per_ip_daily_budget_usd: float | None = None
    rate_limit_analyze_per_ip_day: int | None = None
    rate_limit_recalculate_per_ip_day: int | None = None

    # LLM provider config (admin-overridable at runtime)
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_narrative_api_key: str | None = None
    llm_narrative_base_url: str | None = None
    llm_narrative_model: str | None = None


def _redact_applied(applied: dict[str, Any]) -> dict[str, Any]:
    """Mask secret values in the patch echo so logs/responses don't leak keys."""
    return {
        k: ("***" if k in REDACTED_FIELDS and v else v)
        for k, v in applied.items()
    }


@router.get("/settings")
def get_settings(_: None = Depends(require_admin)) -> dict[str, Any]:
    rt = get_runtime_settings()
    return {
        "effective": rt.snapshot().as_dict(redact=True),
        "overrides": redact_overrides(rt.overrides()),
    }


@router.patch("/settings")
def patch_settings(
    patch: SettingsPatch,
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    non_null = {k: v for k, v in patch.model_dump().items() if v is not None}
    if not non_null:
        raise HTTPException(status_code=400, detail="No fields provided")
    try:
        effective = get_runtime_settings().update(non_null)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Provider config changed → drop the cached LLMClient so the next
    # request rebuilds with the new config. httpx connection pool stays
    # alive (it has no host affinity beyond DNS caching).
    llm_changed = bool(non_null.keys() & LLM_PROVIDER_FIELDS)
    if llm_changed:
        invalidate_llm_client()

    return {
        "effective": effective.as_dict(redact=True),
        "applied": _redact_applied(non_null),
        "llm_client_invalidated": llm_changed,
    }


@router.post("/settings/reset")
def reset_settings(_: None = Depends(require_admin)) -> dict[str, Any]:
    rt = get_runtime_settings()
    had_llm = rt.has_llm_overrides()
    effective = rt.reset()
    # If we just dropped any LLM override, the next request must observe the
    # env-based config — invalidate the singleton.
    if had_llm:
        invalidate_llm_client()
    return {
        "effective": effective.as_dict(redact=True),
        "overrides": {},
        "llm_client_invalidated": had_llm,
    }


class TierPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: str  # "free" | "pro"


@router.patch("/users/{email}/tier")
async def patch_user_tier(
    email: EmailStr,
    body: TierPatch,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Manually promote / demote a user's subscription tier.

    Used during the pre-Stripe phase to grant Pro access. Once Stripe is
    wired up, this remains as an admin override path.
    """
    if not is_db_configured():
        raise HTTPException(status_code=503, detail="Database not configured.")
    auth = AuthService(session)
    user = await auth.get_by_email(email)
    if user is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    try:
        await auth.set_tier(user, tier=body.tier)  # type: ignore[arg-type]
    except AuthError as e:
        raise HTTPException(
            status_code=400, detail={"error": e.code, "message": str(e)}
        ) from e
    await session.commit()
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "tier": user.tier,
            "display_name": user.display_name,
        }
    }


@router.get("/usage")
def get_usage(_: None = Depends(require_admin)) -> dict[str, Any]:
    """Snapshot of LLM spend + rate-limit activity over the last 24h."""
    store = get_accounting_store()
    now = time.time()
    since = now - _DAY_SECONDS
    records = store.records_since(since_ts=since)

    by_task: Counter[str] = Counter()
    by_ip: Counter[str] = Counter()
    for r in records:
        by_task[r.task_tag] += 1
        if r.client_ip:
            by_ip[r.client_ip] += 1

    total_spend = round(sum(r.estimated_cost_usd for r in records), 6)
    input_tokens = sum(r.input_tokens for r in records)
    output_tokens = sum(r.output_tokens for r in records)

    effective = get_runtime_settings().snapshot()
    rate_snapshot = get_rate_limiter().snapshot()

    return {
        "window_hours": 24,
        "llm": {
            "call_count": len(records),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "spend_usd": total_spend,
            "budget_usd": effective.llm_daily_budget_usd,
            "budget_utilization_pct": (
                round(100 * total_spend / effective.llm_daily_budget_usd, 2)
                if effective.llm_daily_budget_usd > 0
                else None
            ),
            "calls_by_task": dict(by_task.most_common()),
            "calls_by_ip": [
                {"ip": ip, "count": c} for ip, c in by_ip.most_common(10)
            ],
        },
        "rate_limits": {
            "analyze_limit_per_day": effective.rate_limit_analyze_per_ip_day,
            "recalculate_limit_per_day": effective.rate_limit_recalculate_per_ip_day,
            "active_buckets": rate_snapshot,
        },
    }
