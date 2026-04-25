"""Node: Moat Analysis — score the company's economic moat from Item 1 Business.

Implements Hamilton Helmer's "7 Powers" framework: scale_economies,
network_effects, counter_positioning, switching_costs, branding,
cornered_resource, process_power. The LLM scores each 0-10 with a verbatim
quote from the 10-K Business section as evidence.

Quote verification: any power scoring ≥3 without a verifiable quote is
demoted to 0 (no evidence). This prevents hallucinated moat claims.

Runs after ``risk_yoy_diff`` and before ``investment_thesis`` so the thesis
node can reference the moat assessment in its narrative.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.types import StreamWriter
from pydantic import BaseModel, Field

from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    StepCompleteEvent,
)
from backend.services.llm import LLMError, get_llm_client, is_llm_configured
from backend.services.sec_client import sec_client
from backend.services.tenk_parser import (
    extract_business,
    smart_truncate,
)

from ._pro_gate import emit_lock, is_pro_user
from .qualitative_analysis import _normalize  # reuse normalizer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


PowerName = Literal[
    "scale_economies",
    "network_effects",
    "counter_positioning",
    "switching_costs",
    "branding",
    "cornered_resource",
    "process_power",
]

MoatClassification = Literal["wide", "narrow", "none"]

ALL_POWERS: tuple[PowerName, ...] = (
    "scale_economies",
    "network_effects",
    "counter_positioning",
    "switching_costs",
    "branding",
    "cornered_resource",
    "process_power",
)


class MoatPower(BaseModel):
    """One of the 7 powers scored 0-10 with verbatim evidence."""

    power: PowerName
    score: float = Field(..., ge=0.0, le=10.0)
    rationale: str = Field(..., min_length=1, max_length=400)
    evidence_quote: str | None = None


class MoatInsight(BaseModel):
    """Structured output produced by ``moat_analysis_v1``."""

    powers: list[MoatPower] = Field(..., min_length=1, max_length=7)
    overall_moat_score: float = Field(..., ge=0.0, le=10.0)
    moat_classification: MoatClassification
    primary_powers: list[PowerName] = Field(..., min_length=0, max_length=3)
    thesis_one_liner: str = Field(..., min_length=1, max_length=300)
    confidence: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Quote verification (demote unverifiable claims to 0)
# ---------------------------------------------------------------------------


def _verify_and_demote(
    powers: list[MoatPower], *, source_text: str,
) -> tuple[list[dict[str, Any]], int]:
    """Verify each power's evidence_quote against source_text.

    Powers scoring >=3 with an unverifiable quote get demoted to score=0 and
    quote=None — preserving their structural row in the output for UI
    consistency, but stripping the unsubstantiated claim.

    Returns ``(verified_dicts, demoted_count)``.
    """
    norm_source = _normalize(source_text)
    out: list[dict[str, Any]] = []
    demoted = 0
    for p in powers:
        quote = p.evidence_quote.strip() if isinstance(p.evidence_quote, str) else None
        verified = (
            quote is not None
            and len(quote) >= 40
            and _normalize(quote) in norm_source
        )
        if p.score >= 3 and not verified:
            demoted += 1
            out.append({
                "power": p.power,
                "score": 0.0,
                "rationale": (
                    f"[demoted] {p.rationale} (evidence quote could not be "
                    "verified against the source filing)"
                ),
                "evidence_quote": None,
            })
        else:
            out.append({
                "power": p.power,
                "score": float(p.score),
                "rationale": p.rationale,
                "evidence_quote": quote if verified else None,
            })
    return out, demoted


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


async def moat_analysis_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    """Score the company's 7 Powers based on Item 1 Business of latest 10-K."""
    financials = state.get("financials")
    if financials is None or not getattr(financials, "cik", None):
        writer(StepCompleteEvent(
            node="moat_analysis",
            summary="Moat analysis skipped: no CIK available.",
        ).model_dump())
        return {
            "moat_result": None,
            "reasoning_steps": ["Moat: skipped — no CIK"],
        }

    if not is_pro_user(state):
        return emit_lock(
            writer=writer,
            node_name="moat_analysis",
            feature_label="Moat / 7 Powers scoring",
            locked_component_type="moat_locked_card",
            state_field="moat_result",
            ticker=financials.ticker,
            entity_name=financials.entity_name,
        ).payload

    if not is_llm_configured():
        writer(AgentThinkingEvent(
            node="moat_analysis",
            content="LLM not configured. Moat analysis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="moat_analysis",
            summary="Moat analysis skipped: LLM API key not set.",
        ).model_dump())
        return {
            "moat_result": None,
            "reasoning_steps": ["Moat: skipped — no LLM API key"],
        }

    ticker = financials.ticker
    cik = int(financials.cik)

    writer(AgentThinkingEvent(
        node="moat_analysis",
        content=f"Locating Item 1 Business section in {ticker} 10-K...",
    ).model_dump())

    try:
        filing = await sec_client.fetch_10k(cik, n_back=0)
    except Exception:
        logger.exception("Moat fetch_10k crashed for %s", ticker)
        filing = None

    if not filing:
        writer(AgentThinkingEvent(
            node="moat_analysis",
            content="Could not download 10-K. Moat analysis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="moat_analysis",
            summary="Moat skipped: no 10-K filing available.",
        ).model_dump())
        return {
            "moat_result": None,
            "reasoning_steps": ["Moat: skipped — no 10-K"],
        }

    section = extract_business(filing["html"])
    if section is None:
        writer(AgentThinkingEvent(
            node="moat_analysis",
            content="Item 1 Business section could not be isolated. Skipping.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="moat_analysis",
            summary="Moat skipped: Business section parse failed.",
        ).model_dump())
        return {
            "moat_result": None,
            "reasoning_steps": ["Moat: skipped — Item 1 not parseable"],
        }

    truncated = smart_truncate(section.text, max_chars=12_000)

    writer(AgentThinkingEvent(
        node="moat_analysis",
        content=(
            f"Scoring 7 Powers from {section.char_count:,} chars of Business "
            f"({len(truncated):,} chars sent to LLM)..."
        ),
    ).model_dump())

    try:
        client = get_llm_client()
        insight: MoatInsight = await client.complete_json(
            prompt_name="moat_analysis",
            version=1,
            variables={
                "ticker": ticker,
                "company_name": financials.entity_name,
                "filing_date": filing["filing_date"],
                "accession_number": filing["accession_number"],
                "business_text": truncated,
            },
            task_tag="moat",
            response_model=MoatInsight,
        )
    except LLMError as e:
        logger.warning("Moat LLM call failed for %s: %s", ticker, e)
        writer(AgentThinkingEvent(
            node="moat_analysis",
            content="LLM call for moat analysis failed. Skipping.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="moat_analysis",
            summary="Moat skipped: LLM error.",
        ).model_dump())
        return {
            "moat_result": None,
            "reasoning_steps": [f"Moat: error — {e}"],
        }
    except Exception:
        logger.exception("Moat node crashed for %s", ticker)
        writer(StepCompleteEvent(
            node="moat_analysis",
            summary="Moat skipped: unexpected error.",
        ).model_dump())
        return {
            "moat_result": None,
            "reasoning_steps": ["Moat: error — unexpected"],
        }

    verified_powers, demoted = _verify_and_demote(
        insight.powers, source_text=section.text,
    )

    # Recompute overall_moat_score from the verified scores (max), in case
    # demotions changed the picture.
    verified_scores = [p["score"] for p in verified_powers]
    overall = max(verified_scores) if verified_scores else 0.0
    if overall >= 7:
        classification = "wide"
    elif overall >= 4:
        classification = "narrow"
    else:
        classification = "none"

    # Recompute primary_powers from verified scores
    sorted_powers = sorted(
        verified_powers, key=lambda p: p["score"], reverse=True,
    )
    primary = [p["power"] for p in sorted_powers[:3] if p["score"] >= 3]

    if demoted:
        logger.warning(
            "moat_analysis %s demoted %d/%d powers with unverifiable quotes",
            ticker, demoted, len(insight.powers),
        )

    result: dict[str, Any] = {
        "ticker": ticker,
        "filing_date": filing["filing_date"],
        "accession_number": filing["accession_number"],
        "filing_url": filing["url"],
        "powers": verified_powers,
        "overall_moat_score": round(overall, 1),
        "moat_classification": classification,
        "primary_powers": primary,
        "thesis_one_liner": insight.thesis_one_liner,
        "demoted_power_count": demoted,
        "confidence": insight.confidence,
        "parser_strategy": section.strategy,
    }

    writer(ComponentEvent(
        component_type="moat_analysis_card",
        props={
            "entity_name": financials.entity_name,
            **result,
        },
    ).model_dump())

    writer(AgentThinkingEvent(
        node="moat_analysis",
        content=(
            f"Moat: {classification} (overall {overall:.1f}/10). "
            f"Primary powers: {', '.join(primary) if primary else 'none'}"
            + (f" ({demoted} demoted)" if demoted else "")
            + "."
        ),
    ).model_dump())

    writer(StepCompleteEvent(
        node="moat_analysis",
        summary=(
            f"Moat: {classification} ({overall:.1f}/10), "
            f"confidence {insight.confidence:.0%}."
        ),
    ).model_dump())

    return {
        "moat_result": result,
        "reasoning_steps": [
            f"Moat: {classification} (overall {overall:.1f}/10)",
            f"Primary powers: {', '.join(primary) if primary else 'none'}",
        ],
    }
