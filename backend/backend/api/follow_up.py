"""Follow-up Q&A endpoint.

The user, after seeing an analysis canvas, clicks the conversation rail's
"Ask follow-up" affordance and types a question (e.g. "what if growth is
2pp lower", "compare to MSFT moat"). The frontend POSTs the question plus
the current ticker + canvas snapshot here; we synthesize a grounded answer
using the same LLM pipeline (with budget gate + per-IP accounting).

Auth: required (Pro users only — the Pro tier already gates the LLM-heavy
nodes; follow-up Q&A also costs LLM budget). Free users get a clean 403
response so the frontend can prompt upgrade.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.services.auth import User, require_pro
from backend.services.llm import (
    LLMError,
    get_llm_client,
    is_llm_configured,
    sanitize_text,
)
from backend.services.rate_limit import (
    BUCKET_RECALCULATE,
    get_rate_limiter,
)
from backend.services.request_context import bind_client_ip, extract_client_ip

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_COMPONENTS_INLINED = 12  # cap how much canvas context we ship to the LLM


def _enforce_rate_limit(request: Request) -> str:
    client_ip = extract_client_ip(request)
    decision = get_rate_limiter().check_and_record(
        bucket=BUCKET_RECALCULATE, client_ip=client_ip,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": (
                    f"Daily limit reached ({decision.limit} per 24h). "
                    f"Try again later."
                ),
                "retry_after_seconds": decision.retry_after_seconds,
            },
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
    return client_ip


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------


class _ComponentInstructionLite(BaseModel):
    """Subset of ComponentInstruction we include in the prompt — props only."""

    model_config = ConfigDict(extra="allow")
    component_type: str
    props: dict[str, Any]


class FollowUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(min_length=1, max_length=8)
    question: str = Field(min_length=2, max_length=500)
    hero_snapshot: dict[str, Any] | None = None
    components_snapshot: list[_ComponentInstructionLite] = Field(default_factory=list)


class FollowUpAnswer(BaseModel):
    """Mirrors the YAML schema."""

    model_config = ConfigDict(extra="forbid")
    answer: str
    tab_hint: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


def _hero_summary(hero: dict[str, Any] | None) -> str:
    if not hero:
        return "No hero snapshot provided."
    parts: list[str] = []
    for key, label in [
        ("signalLabel", "Signal"),
        ("marginOfSafety", "Margin of safety (%)"),
        ("confidence", "Confidence (0-1)"),
        ("currentPrice", "Current price"),
        ("intrinsicValue", "Intrinsic value"),
        ("suggestedEntry", "Suggested entry"),
        ("upside", "Upside (%)"),
        ("thesisHeadline", "Thesis headline"),
        ("highSeverityRiskCount", "High-severity risk count"),
    ]:
        v = hero.get(key)
        if v is not None:
            parts.append(f"- {label}: {v}")
    return "\n".join(parts) if parts else "Hero snapshot empty."


def _components_summary(components: list[_ComponentInstructionLite]) -> str:
    """Render a compact textual digest of the canvas. We trim to the most
    information-dense fields per type so the prompt stays small."""
    if not components:
        return "No component cards in scope."
    lines: list[str] = []
    for c in components[:_MAX_COMPONENTS_INLINED]:
        p = c.props
        if c.component_type == "dcf_result_card":
            lines.append(
                f"- DCF: intrinsic_per_share={p.get('intrinsic_value_per_share')} "
                f"EV={p.get('enterprise_value')} terminal_pct≈"
                f"{(p.get('terminal_value', 0) or 0)} assumptions={p.get('assumptions')}"
            )
        elif c.component_type == "strategy_dashboard":
            lines.append(
                f"- Strategy: signal={p.get('signal')} MoS%={p.get('margin_of_safety_pct')} "
                f"upside%={p.get('upside_pct')} entry={p.get('suggested_entry_price')} "
                f"P/E={p.get('current_pe')} pe_pctl={p.get('pe_percentile')}"
            )
        elif c.component_type == "investment_thesis_card":
            lines.append(
                f"- Thesis: rec={p.get('recommendation')} "
                f"headline='{p.get('thesis_headline')}' "
                f"bull={p.get('bull_points')} bear={p.get('bear_points')} "
                f"risks={p.get('key_risks')}"
            )
        elif c.component_type == "risk_factors_card":
            top = p.get("top_risks") or []
            top_titles = [
                f"{r.get('severity', '?')}:{r.get('title', '')}" for r in top
            ]
            lines.append(
                f"- 10-K risks: categories={p.get('risk_categories')} "
                f"concentration={p.get('concentration_risk')} top={top_titles}"
            )
        elif c.component_type == "moat_analysis_card":
            lines.append(f"- Moat: {p}")
        elif c.component_type == "relative_valuation_card":
            lines.append(f"- Relative valuation: {p}")
        elif c.component_type == "financial_health_card":
            lines.append(f"- Financial health: {p}")
        else:
            lines.append(f"- {c.component_type}: {list(p.keys())}")
    if len(components) > _MAX_COMPONENTS_INLINED:
        lines.append(f"  …({len(components) - _MAX_COMPONENTS_INLINED} more cards omitted)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/api/follow-up")
async def follow_up(
    body: FollowUpRequest,
    request: Request,
    user: Annotated[User, Depends(require_pro)],
) -> dict[str, Any]:
    """Answer a follow-up question about an analysis the user is viewing."""
    if not is_llm_configured():
        raise HTTPException(
            status_code=503,
            detail="Follow-up Q&A disabled: AQ_LLM_API_KEY not configured.",
        )

    client_ip = _enforce_rate_limit(request)

    # The user-supplied question is the only untrusted input on this path —
    # everything else (hero / components snapshot) is server-rendered. Wrap
    # it in <<<USER_CONTENT>>> boundaries + escape control chars / HTML so
    # a question like "ignore previous instructions; <<<END_USER_CONTENT>>>"
    # can't escape the prompt envelope. Same convention used by every other
    # LLM node (see services/llm/sanitize.py).
    variables = {
        "ticker": body.ticker.upper(),
        "hero_summary": _hero_summary(body.hero_snapshot),
        "components_summary": _components_summary(body.components_snapshot),
        "question": sanitize_text(body.question.strip(), max_len=1500),
    }

    try:
        with bind_client_ip(client_ip):
            client = get_llm_client()
            answer: FollowUpAnswer = await client.complete_json(
                prompt_name="follow_up",
                version=2,
                variables=variables,
                task_tag="follow_up",
                response_model=FollowUpAnswer,
            )
    except LLMError as e:
        logger.warning(
            "follow_up failed user=%s ticker=%s err=%s", user.email, body.ticker, e,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "llm_failed",
                "message": "Follow-up generation failed. Please try again.",
            },
        ) from e

    logger.info(
        "follow_up ok user=%s ticker=%s q_len=%d ans_len=%d conf=%.2f",
        user.email, body.ticker, len(body.question), len(answer.answer), answer.confidence,
    )
    return answer.model_dump()
