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
from backend.services.llm import get_accounting_store
from backend.services.rate_limit import get_rate_limiter
from backend.services.runtime_settings import get_runtime_settings

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
    """Body for PATCH /api/admin/settings. All fields optional."""

    model_config = ConfigDict(extra="forbid")

    llm_daily_budget_usd: float | None = None
    llm_per_ip_daily_budget_usd: float | None = None
    rate_limit_analyze_per_ip_day: int | None = None
    rate_limit_recalculate_per_ip_day: int | None = None


@router.get("/settings")
def get_settings(_: None = Depends(require_admin)) -> dict[str, Any]:
    rt = get_runtime_settings()
    return {
        "effective": rt.snapshot().as_dict(),
        "overrides": rt.overrides(),
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
    return {"effective": effective.as_dict(), "applied": non_null}


@router.post("/settings/reset")
def reset_settings(_: None = Depends(require_admin)) -> dict[str, Any]:
    effective = get_runtime_settings().reset()
    return {"effective": effective.as_dict(), "overrides": {}}


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
