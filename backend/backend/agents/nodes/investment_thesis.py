"""Node: Investment Thesis — LLM synthesizes a structured research narrative.

Runs after the strategy node so it can consume every upstream result. The
entire node is optional: if the LLM is not configured or the call fails, the
pipeline continues without a thesis.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.types import StreamWriter
from pydantic import BaseModel, Field, field_validator

from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    StepCompleteEvent,
)
from backend.services.llm import LLMError, get_llm_client, is_llm_configured

from ._pro_gate import emit_lock, is_pro_user

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response schema (validated by LLMClient.complete_json)
# ---------------------------------------------------------------------------


Recommendation = Literal["Strong Buy", "Buy", "Hold", "Reduce", "Sell"]


class InvestmentThesis(BaseModel):
    """Structured output produced by ``investment_thesis_v1``."""

    thesis_headline: str = Field(..., min_length=1, max_length=300)
    recommendation: Recommendation
    bull_points: list[str] = Field(..., min_length=1, max_length=8)
    bear_points: list[str] = Field(..., min_length=0, max_length=8)
    key_risks: list[str] = Field(..., min_length=1, max_length=8)
    action_summary: str = Field(..., min_length=1, max_length=800)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("bull_points", "bear_points", "key_risks")
    @classmethod
    def _non_empty_strings(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if isinstance(v, str) and v.strip()]


# ---------------------------------------------------------------------------
# Variable construction
# ---------------------------------------------------------------------------


def _fmt_pct(value: Any, suffix: str = "%") -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.1f}{suffix}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_money(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _dcf_summary(dcf: dict[str, Any] | None, event_impact: dict[str, Any] | None) -> str:
    if not dcf:
        return "No DCF result."
    a = dcf.get("assumptions", {}) or {}
    lines = [
        f"Intrinsic value/share: {_fmt_money(dcf.get('intrinsic_value_per_share'))}",
        f"Growth rate: {_fmt_pct(a.get('growth_rate'))}",
        f"Terminal growth: {_fmt_pct(a.get('terminal_growth_rate'))}",
        f"Discount rate (WACC): {_fmt_pct(a.get('discount_rate'))}",
        f"Latest FCF: {_fmt_money(a.get('latest_fcf'))}",
    ]
    if event_impact and event_impact.get("recalculated_dcf", {}).get("intrinsic_value_per_share"):
        recalc = event_impact["recalculated_dcf"]["intrinsic_value_per_share"]
        lines.append(f"Event-adjusted intrinsic/share: {_fmt_money(recalc)}")
    return "\n  ".join(lines)


def _relative_valuation_summary(rv: dict[str, Any] | None) -> str:
    if not rv:
        return "No relative valuation result."
    parts: list[str] = []
    peer_comp = rv.get("peer_comparison") or {}
    if peer_comp.get("peer_data_available"):
        deltas = peer_comp.get("deltas", {}) or {}
        pe = deltas.get("pe")
        pb = deltas.get("pb")
        ev_ebitda = deltas.get("ev_ebitda")
        if pe is not None:
            parts.append(f"P/E vs peer median: {pe:+.1f}%")
        if pb is not None:
            parts.append(f"P/B vs peer median: {pb:+.1f}%")
        if ev_ebitda is not None:
            parts.append(f"EV/EBITDA vs peer median: {ev_ebitda:+.1f}%")
        peer_names = peer_comp.get("peer_tickers") or []
        if peer_names:
            parts.append(f"Peers: {', '.join(map(str, peer_names[:6]))}")
    if not parts:
        return "Peer data unavailable; relative valuation not computed."
    return "\n  ".join(parts)


def _financial_health_summary(state: AnalysisState) -> str:
    metrics = state.get("health_metrics") or {}
    assessment = state.get("health_assessment") or ""
    if not metrics and not assessment:
        return "No financial health assessment."
    rows: list[str] = []
    for key in ("debt_to_ebitda", "interest_coverage", "quick_ratio", "current_ratio"):
        if key in metrics and metrics[key] is not None:
            rows.append(f"{key}: {metrics[key]}")
    if assessment:
        rows.append(f"Assessment: {assessment}")
    return "\n  ".join(rows) if rows else "No financial health assessment."


def _event_sentiment_summary(sent: dict[str, Any] | None) -> str:
    if not sent:
        return "No event sentiment result."
    parts: list[str] = []
    if "overall_score" in sent:
        parts.append(f"Overall score: {sent['overall_score']:+.2f}")
    if sent.get("sentiment_label"):
        parts.append(f"Label: {sent['sentiment_label']}")
    if sent.get("summary"):
        parts.append(f"Summary: {sent['summary']}")
    key_events = sent.get("key_events") or []
    if key_events:
        parts.append("Key events: " + "; ".join(str(e) for e in key_events[:5]))
    return "\n  ".join(parts) if parts else "No sentiment detail available."


def _event_impact_summary(ei: dict[str, Any] | None) -> str:
    if not ei:
        return "No event impact adjustments applied."
    parts: list[str] = []
    if ei.get("summary"):
        parts.append(f"Impact: {ei['summary']}")
    if "confidence" in ei:
        parts.append(f"Confidence: {float(ei['confidence']):.0%}")
    adj = ei.get("parameter_adjustments") or {}
    for name, spec in adj.items():
        if not spec:
            continue
        value = spec.get("value")
        kind = spec.get("type")
        if value is not None and kind:
            parts.append(f"{name}: {kind} {value}")
    return "\n  ".join(parts) if parts else "No material parameter adjustments."


def _moat_summary(m: dict[str, Any] | None) -> str:
    """Format the moat_result dict for the thesis prompt."""
    if not m:
        return "No moat / 7 Powers analysis available."
    parts: list[str] = [
        f"Moat classification: {m.get('moat_classification', 'unknown')} "
        f"(overall {m.get('overall_moat_score', 0)}/10)",
    ]
    primary = m.get("primary_powers") or []
    if primary:
        parts.append("Primary powers: " + ", ".join(primary))
    if m.get("thesis_one_liner"):
        parts.append(f"Moat thesis: {m['thesis_one_liner']}")
    # Include scoring grid for top scorers
    scored = sorted(m.get("powers") or [], key=lambda p: p.get("score", 0), reverse=True)
    if scored:
        top_str = "; ".join(
            f"{p['power']}={p['score']}" for p in scored[:5] if p.get("score", 0) > 0
        )
        if top_str:
            parts.append(f"Power scores: {top_str}")
    return "\n  ".join(parts)


def _risk_yoy_summary(d: dict[str, Any] | None) -> str:
    """Format the YoY risk diff for the thesis prompt."""
    if not d:
        return "No year-over-year risk diff available."
    parts: list[str] = []
    cur = d.get("current_filing", {}).get("filing_date", "?")
    prev = d.get("prior_filing", {}).get("filing_date", "?")
    parts.append(f"Comparison: {prev} → {cur}")
    if d.get("summary"):
        parts.append(f"Diff summary: {d['summary']}")

    def render_bucket(label: str, items: list[dict[str, Any]]) -> str | None:
        if not items:
            return None
        titles = [str(i.get("title", "")).strip() for i in items[:4]]
        titles = [t for t in titles if t]
        if not titles:
            return None
        return f"{label}: " + "; ".join(titles)

    for label, key in [
        ("New risks", "new_risks"),
        ("Removed risks", "removed_risks"),
        ("Escalated risks", "escalated_risks"),
        ("De-escalated risks", "de_escalated_risks"),
    ]:
        rendered = render_bucket(label, d.get(key) or [])
        if rendered:
            parts.append(rendered)

    if (
        not d.get("new_risks") and not d.get("removed_risks")
        and not d.get("escalated_risks") and not d.get("de_escalated_risks")
    ):
        parts.append("No material year-over-year changes identified.")

    return "\n  ".join(parts)


def _qualitative_summary(q: dict[str, Any] | None) -> str:
    """Format the qualitative_result dict for the thesis prompt.

    Expects the nested ``{mdna: ..., risk_factors: ...}`` structure produced
    by ``qualitative_analysis_node``. Either sub-object may be None; falls
    back gracefully when neither is available.
    """
    if not q:
        return "No 10-K qualitative analysis available."

    parts: list[str] = [f"Filing date: {q.get('filing_date', 'n/a')}"]

    mdna = q.get("mdna")
    if mdna:
        parts.append(f"Management tone: {mdna.get('tone', 'unknown')}")
        guidance = mdna.get("forward_guidance_summary")
        if guidance:
            parts.append(f"Forward guidance: {guidance}")
        drivers = mdna.get("growth_drivers") or []
        if drivers:
            parts.append("Growth drivers: " + "; ".join(drivers[:5]))
        concerns = mdna.get("management_concerns") or []
        if concerns:
            parts.append("Management concerns: " + "; ".join(concerns[:5]))
    else:
        parts.append("MD&A: not available.")

    risks = q.get("risk_factors")
    if risks:
        top = risks.get("top_risks") or []
        if top:
            rendered = []
            for r in top[:5]:
                rendered.append(
                    f"[{r.get('category', '?')}/{r.get('severity', '?')}] "
                    f"{r.get('title', '').strip()}"
                )
            parts.append("Top risks: " + " | ".join(rendered))
        concentration = risks.get("concentration_risk")
        if concentration:
            parts.append(f"Concentration risk: {concentration}")
    else:
        parts.append("Risk Factors: not available.")

    return "\n  ".join(parts)


def _build_variables(state: AnalysisState) -> dict[str, Any]:
    financials = state["financials"]
    strat = state.get("strategy_result") or {}
    dcf = state.get("dcf_result")
    rel_val = state.get("relative_valuation_result")
    sent = state.get("event_sentiment_result")
    ei = state.get("event_impact_result")
    qual = state.get("qualitative_result")
    yoy = state.get("risk_yoy_diff_result")
    moat = state.get("moat_result")

    ticker = financials.ticker if financials else state.get("ticker", "UNKNOWN")
    company_name = financials.entity_name if financials else ticker

    return {
        "ticker": ticker,
        "company_name": company_name,
        "current_price_str": _fmt_money(strat.get("current_price")),
        "intrinsic_value_str": _fmt_money(strat.get("intrinsic_value")),
        "margin_of_safety_str": _fmt_pct(strat.get("margin_of_safety_pct")),
        "upside_str": _fmt_pct(strat.get("upside_pct")),
        "signal": strat.get("signal") or "n/a",
        "suggested_entry_str": _fmt_money(strat.get("suggested_entry_price")),
        "current_pe_str": (
            f"{strat.get('current_pe')}" if strat.get("current_pe") is not None else "n/a"
        ),
        "pe_percentile_str": (
            _fmt_pct(strat.get("pe_percentile"))
            if strat.get("pe_percentile") is not None
            else "n/a"
        ),
        "dcf_summary": _dcf_summary(dcf, ei),
        "relative_valuation_summary": _relative_valuation_summary(rel_val),
        "financial_health_summary": _financial_health_summary(state),
        "event_sentiment_summary": _event_sentiment_summary(sent),
        "event_impact_summary": _event_impact_summary(ei),
        "qualitative_summary": _qualitative_summary(qual),
        "risk_yoy_summary": _risk_yoy_summary(yoy),
        "moat_summary": _moat_summary(moat),
    }


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


async def investment_thesis_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    """Generate a narrative investment thesis from upstream node results."""
    financials = state.get("financials")
    strat = state.get("strategy_result")

    if financials is None or not strat:
        writer(StepCompleteEvent(
            node="investment_thesis",
            summary="Investment thesis skipped: no strategy result.",
        ).model_dump())
        return {
            "investment_thesis_result": None,
            "reasoning_steps": ["Investment thesis: skipped — no strategy result"],
        }

    if not is_pro_user(state):
        return emit_lock(
            writer=writer,
            node_name="investment_thesis",
            feature_label="Investment thesis",
            locked_component_type="investment_thesis_locked_card",
            state_field="investment_thesis_result",
            ticker=financials.ticker,
            entity_name=financials.entity_name,
            extra_props={
                "preview_signal": strat.get("signal"),
                "preview_margin_of_safety_pct": strat.get("margin_of_safety_pct"),
            },
        ).payload

    if not is_llm_configured():
        writer(AgentThinkingEvent(
            node="investment_thesis",
            content="LLM not configured. Investment thesis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="investment_thesis",
            summary="Investment thesis skipped: LLM API key not set.",
        ).model_dump())
        return {
            "investment_thesis_result": None,
            "reasoning_steps": ["Investment thesis: skipped — no LLM API key"],
        }

    ticker = financials.ticker
    writer(AgentThinkingEvent(
        node="investment_thesis",
        content=f"Drafting structured investment thesis for {ticker}...",
    ).model_dump())

    try:
        variables = _build_variables(state)
        client = get_llm_client()
        thesis = await client.complete_json(
            prompt_name="investment_thesis",
            version=1,
            variables=variables,
            task_tag="thesis",
            response_model=InvestmentThesis,
        )
    except LLMError as e:
        logger.warning("Investment thesis generation failed for %s: %s", ticker, e)
        writer(AgentThinkingEvent(
            node="investment_thesis",
            content="Investment thesis generation failed; the numeric analysis still stands.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="investment_thesis",
            summary="Investment thesis skipped: LLM error.",
        ).model_dump())
        return {
            "investment_thesis_result": None,
            "reasoning_steps": [f"Investment thesis: error — {e}"],
        }
    except Exception:  # pragma: no cover - defense-in-depth
        logger.exception("Investment thesis node crashed for %s", ticker)
        writer(StepCompleteEvent(
            node="investment_thesis",
            summary="Investment thesis skipped: unexpected error.",
        ).model_dump())
        return {
            "investment_thesis_result": None,
            "reasoning_steps": ["Investment thesis: error — unexpected"],
        }

    thesis_dict = thesis.model_dump()

    writer(ComponentEvent(
        component_type="investment_thesis_card",
        props={
            "ticker": ticker,
            "entity_name": financials.entity_name,
            **thesis_dict,
        },
    ).model_dump())

    writer(AgentThinkingEvent(
        node="investment_thesis",
        content=f"Thesis: {thesis.thesis_headline}",
    ).model_dump())

    writer(StepCompleteEvent(
        node="investment_thesis",
        summary=(
            f"Investment thesis: {thesis.recommendation} — "
            f"{thesis.thesis_headline} (confidence: {thesis.confidence:.0%})"
        ),
    ).model_dump())

    return {
        "investment_thesis_result": thesis_dict,
        "reasoning_steps": [
            f"Investment thesis: {thesis.recommendation} — {thesis.thesis_headline}",
            f"Thesis confidence: {thesis.confidence:.0%}",
        ],
    }
