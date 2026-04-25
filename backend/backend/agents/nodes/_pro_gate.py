"""Tier gating helper shared by Pro-only LangGraph nodes.

When a free-tier user hits a Pro node, we don't run the LLM call. Instead we
emit a ``ComponentEvent`` for a "locked preview" card with the metadata the
frontend needs to render an upsell CTA, then return ``None`` for the result
field. The investment thesis node still runs on a free user — it just
receives ``None`` for the gated upstream signals.

The four Pro nodes (``investment_thesis``, ``qualitative_analysis``,
``risk_yoy_diff``, ``moat_analysis``) all share the same gate. Each calls
``check_pro_or_lock(state, writer, ...)`` at the top; if it returns the
"locked" sentinel, the node skips its work and returns the prepared payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.types import StreamWriter

from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    StepCompleteEvent,
)


@dataclass(frozen=True)
class LockedResult:
    """Sentinel returned to the caller when the node was tier-gated."""

    state_field: str
    payload: dict[str, Any]


def is_pro_user(state: AnalysisState) -> bool:
    """Return True iff the request's user_tier grants Pro features."""
    tier = state.get("user_tier") or "free"
    return tier in {"pro", "admin"}


def emit_lock(
    *,
    writer: StreamWriter,
    node_name: str,
    feature_label: str,
    locked_component_type: str,
    state_field: str,
    entity_name: str | None = None,
    ticker: str | None = None,
    extra_props: dict[str, Any] | None = None,
) -> LockedResult:
    """Emit the SSE events for a locked-preview card and return the result dict.

    The frontend renders ``locked_component_type`` as a teaser card with an
    "Unlock Pro" CTA. Each Pro card has a corresponding ``*_locked_card``
    component registered on the frontend.
    """
    props: dict[str, Any] = {
        "ticker": ticker,
        "entity_name": entity_name,
        "feature_label": feature_label,
        "locked_reason": "pro_required",
    }
    if extra_props:
        props.update(extra_props)

    writer(AgentThinkingEvent(
        node=node_name,
        content=f"{feature_label} is a Pro feature. Skipping for free tier.",
    ).model_dump())
    writer(ComponentEvent(
        component_type=locked_component_type,
        props=props,
    ).model_dump())
    writer(StepCompleteEvent(
        node=node_name,
        summary=f"{feature_label}: Pro-only — locked preview emitted.",
    ).model_dump())

    return LockedResult(
        state_field=state_field,
        payload={
            state_field: None,
            "reasoning_steps": [f"{feature_label}: gated — free tier"],
        },
    )
