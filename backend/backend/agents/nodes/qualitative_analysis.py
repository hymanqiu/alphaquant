"""Node: Qualitative Analysis — extract MD&A + Risk Factors from the latest 10-K.

Runs after ``strategy`` so the investment-thesis node can reference qualitative
signals. Entirely optional: any failure (no 10-K available, HTML parse miss,
LLM refusal, budget tripped) degrades to ``None`` without blocking the rest
of the pipeline.

The node fetches the 10-K once, extracts both the Item 7 (MD&A) and Item 1A
(Risk Factors) sections, then issues the two LLM calls in parallel. Partial
success is supported — if one section fails, the other's card is still
emitted.

Hallucination mitigation has three layers:

1. Strict system prompt (see ``mdna_analysis_v1.yaml`` / ``risk_factors_v1.yaml``).
2. Pydantic-level validation — types, enums, length bounds.
3. Post-hoc quote verification: every ``notable_quotes`` string (MD&A) and
   every ``top_risks[*].quote`` (Risk Factors) must be a verbatim substring
   of the source section text. Mismatches are dropped with a warning; risks
   without a valid quote are dropped entirely, so the card only ever shows
   evidence the user could audit against the original filing.
"""

from __future__ import annotations

import asyncio
import logging
import re
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
from backend.services.sec_client import sec_client

from ._pro_gate import emit_lock, is_pro_user
from backend.services.tenk_parser import (
    ExtractedSection,
    extract_mdna,
    extract_risk_factors,
    smart_truncate,
    truncate_head,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


Tone = Literal["optimistic", "neutral", "cautious", "negative"]

RiskCategory = Literal[
    "regulatory",
    "competitive",
    "operational",
    "financial",
    "macro",
    "technology",
    "legal",
    "concentration",
]

RiskSeverity = Literal["high", "medium", "low"]


class MDNAInsight(BaseModel):
    """Structured output produced by ``mdna_analysis_v1``."""

    tone: Tone
    forward_guidance_summary: str = Field(..., min_length=1, max_length=1000)
    growth_drivers: list[str] = Field(default_factory=list, max_length=8)
    management_concerns: list[str] = Field(default_factory=list, max_length=8)
    notable_quotes: list[str] = Field(default_factory=list, max_length=6)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("growth_drivers", "management_concerns", "notable_quotes")
    @classmethod
    def _strip_empty(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if isinstance(v, str) and v.strip()]


class TopRisk(BaseModel):
    """A single risk with a verbatim evidence quote."""

    category: RiskCategory
    title: str = Field(..., min_length=1, max_length=150)
    description: str = Field(..., min_length=1, max_length=500)
    severity: RiskSeverity
    quote: str = Field(..., min_length=20, max_length=800)


class RiskFactorInsight(BaseModel):
    """Structured output produced by ``risk_factors_v1``."""

    risk_categories: dict[RiskCategory, int] = Field(default_factory=dict)
    top_risks: list[TopRisk] = Field(default_factory=list, max_length=8)
    concentration_risk: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Quote verification (ground-truth anchoring)
# ---------------------------------------------------------------------------


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(s: str) -> str:
    """Collapse whitespace and normalize smart quotes for substring matching."""
    s = (
        s.replace("\u2019", "'").replace("\u2018", "'")
         .replace("\u201c", '"').replace("\u201d", '"')
         .replace("\u2013", "-").replace("\u2014", "-")
    )
    return _WHITESPACE_RE.sub(" ", s).strip()


def verify_quotes(
    quotes: list[str], *, source_text: str, min_chars: int = 40,
) -> tuple[list[str], list[str]]:
    """Return ``(verified, rejected)``.

    A quote is verified iff its normalized form appears as a substring of the
    normalized source text AND is at least *min_chars* long.
    """
    normalized_source = _normalize(source_text)
    verified: list[str] = []
    rejected: list[str] = []
    for q in quotes:
        if not isinstance(q, str):
            rejected.append(str(q))
            continue
        q_stripped = q.strip()
        if len(q_stripped) < min_chars:
            rejected.append(q_stripped)
            continue
        if _normalize(q_stripped) in normalized_source:
            verified.append(q_stripped)
        else:
            rejected.append(q_stripped)
    return verified, rejected


def _verify_risk_quote(quote: str, source_text: str) -> bool:
    """Fast single-quote check using the same normalization as verify_quotes."""
    normalized_source = _normalize(source_text)
    return len(quote) >= 40 and _normalize(quote) in normalized_source


# ---------------------------------------------------------------------------
# Per-section analysis helpers (each returns a dict payload or None)
# ---------------------------------------------------------------------------


async def _analyze_mdna(
    *,
    section: ExtractedSection,
    ticker: str,
    company_name: str,
    filing: dict[str, Any],
) -> dict[str, Any] | None:
    truncated = smart_truncate(section.text, max_chars=12_000)
    try:
        client = get_llm_client()
        insight: MDNAInsight = await client.complete_json(
            prompt_name="mdna_analysis",
            version=1,
            variables={
                "ticker": ticker,
                "company_name": company_name,
                "filing_date": filing["filing_date"],
                "accession_number": filing["accession_number"],
                "mdna_text": truncated,
            },
            task_tag="mdna",
            response_model=MDNAInsight,
        )
    except LLMError as e:
        logger.warning("MD&A LLM call failed for %s: %s", ticker, e)
        return None

    verified_quotes, rejected_quotes = verify_quotes(
        insight.notable_quotes, source_text=section.text,
    )
    if rejected_quotes:
        logger.warning(
            "qualitative_analysis %s dropped %d/%d hallucinated MD&A quotes",
            ticker, len(rejected_quotes), len(insight.notable_quotes),
        )

    return {
        "tone": insight.tone,
        "forward_guidance_summary": insight.forward_guidance_summary,
        "growth_drivers": insight.growth_drivers,
        "management_concerns": insight.management_concerns,
        "notable_quotes": verified_quotes,
        "rejected_quote_count": len(rejected_quotes),
        "confidence": insight.confidence,
        "parser_strategy": section.strategy,
        "parser_version": section.parser_version,
        "mdna_char_count": section.char_count,
        "llm_sent_char_count": len(truncated),
    }


async def _analyze_risk_factors(
    *,
    section: ExtractedSection,
    ticker: str,
    company_name: str,
    filing: dict[str, Any],
) -> dict[str, Any] | None:
    truncated = truncate_head(section.text, max_chars=16_000)
    try:
        client = get_llm_client()
        insight: RiskFactorInsight = await client.complete_json(
            prompt_name="risk_factors",
            version=1,
            variables={
                "ticker": ticker,
                "company_name": company_name,
                "filing_date": filing["filing_date"],
                "accession_number": filing["accession_number"],
                "risk_text": truncated,
            },
            task_tag="risk_factors",
            response_model=RiskFactorInsight,
        )
    except LLMError as e:
        logger.warning("Risk Factors LLM call failed for %s: %s", ticker, e)
        return None

    # Keep only risks whose evidence quote is verbatim in the source text.
    verified: list[dict[str, Any]] = []
    rejected_count = 0
    for r in insight.top_risks:
        if _verify_risk_quote(r.quote, section.text):
            verified.append(r.model_dump())
        else:
            rejected_count += 1
    if rejected_count:
        logger.warning(
            "qualitative_analysis %s dropped %d/%d risks with unverifiable quotes",
            ticker, rejected_count, len(insight.top_risks),
        )

    return {
        "risk_categories": {k: int(v) for k, v in insight.risk_categories.items()},
        "top_risks": verified,
        "rejected_risk_count": rejected_count,
        "concentration_risk": insight.concentration_risk,
        "confidence": insight.confidence,
        "parser_strategy": section.strategy,
        "parser_version": section.parser_version,
        "risk_char_count": section.char_count,
        "llm_sent_char_count": len(truncated),
    }


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


async def qualitative_analysis_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    """Fetch the latest 10-K, extract MD&A + Risk Factors, synthesize insights."""
    financials = state.get("financials")
    if financials is None or not getattr(financials, "cik", None):
        writer(StepCompleteEvent(
            node="qualitative_analysis",
            summary="Qualitative analysis skipped: no CIK available.",
        ).model_dump())
        return {
            "qualitative_result": None,
            "reasoning_steps": ["Qualitative: skipped — no CIK"],
        }

    if not is_pro_user(state):
        return emit_lock(
            writer=writer,
            node_name="qualitative_analysis",
            feature_label="10-K MD&A + Risk Factors analysis",
            locked_component_type="qualitative_locked_card",
            state_field="qualitative_result",
            ticker=financials.ticker,
            entity_name=financials.entity_name,
        ).payload

    if not is_llm_configured():
        writer(AgentThinkingEvent(
            node="qualitative_analysis",
            content="LLM not configured. Qualitative analysis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="qualitative_analysis",
            summary="Qualitative analysis skipped: LLM API key not set.",
        ).model_dump())
        return {
            "qualitative_result": None,
            "reasoning_steps": ["Qualitative: skipped — no LLM API key"],
        }

    ticker = financials.ticker
    cik = int(financials.cik)

    writer(AgentThinkingEvent(
        node="qualitative_analysis",
        content=f"Fetching {ticker} latest 10-K filing from SEC EDGAR...",
    ).model_dump())

    try:
        filing = await sec_client.fetch_latest_10k(cik)
    except Exception:
        logger.exception("fetch_latest_10k raised for %s", ticker)
        filing = None

    if not filing:
        writer(AgentThinkingEvent(
            node="qualitative_analysis",
            content="Could not download a 10-K filing. Qualitative analysis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="qualitative_analysis",
            summary="Qualitative analysis skipped: no 10-K filing available.",
        ).model_dump())
        return {
            "qualitative_result": None,
            "reasoning_steps": ["Qualitative: skipped — no 10-K"],
        }

    writer(AgentThinkingEvent(
        node="qualitative_analysis",
        content=(
            f"Parsing 10-K filed {filing['filing_date']} "
            f"(accession {filing['accession_number']})..."
        ),
    ).model_dump())

    mdna_section = extract_mdna(filing["html"])
    risk_section = extract_risk_factors(filing["html"])

    if mdna_section is None and risk_section is None:
        writer(AgentThinkingEvent(
            node="qualitative_analysis",
            content="Neither MD&A nor Risk Factors could be isolated. Skipping.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="qualitative_analysis",
            summary="Qualitative analysis skipped: 10-K parse failed.",
        ).model_dump())
        return {
            "qualitative_result": None,
            "reasoning_steps": ["Qualitative: skipped — no recognizable sections"],
        }

    # Announce what we're about to analyze.
    section_notes: list[str] = []
    if mdna_section:
        section_notes.append(f"MD&A ({mdna_section.char_count:,} chars)")
    if risk_section:
        section_notes.append(f"Risk Factors ({risk_section.char_count:,} chars)")
    writer(AgentThinkingEvent(
        node="qualitative_analysis",
        content=f"Analyzing {' + '.join(section_notes)} in parallel...",
    ).model_dump())

    # Parallel LLM calls. Use gather(return_exceptions=...) so a single-section
    # failure degrades to partial success rather than tanking the whole node.
    tasks: list[Any] = []
    kinds: list[str] = []
    if mdna_section is not None:
        tasks.append(_analyze_mdna(
            section=mdna_section,
            ticker=ticker,
            company_name=financials.entity_name,
            filing=filing,
        ))
        kinds.append("mdna")
    if risk_section is not None:
        tasks.append(_analyze_risk_factors(
            section=risk_section,
            ticker=ticker,
            company_name=financials.entity_name,
            filing=filing,
        ))
        kinds.append("risk_factors")

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        logger.exception("Qualitative gather raised for %s", ticker)
        writer(StepCompleteEvent(
            node="qualitative_analysis",
            summary="Qualitative analysis skipped: unexpected error.",
        ).model_dump())
        return {
            "qualitative_result": None,
            "reasoning_steps": ["Qualitative: error — unexpected"],
        }

    mdna_result: dict[str, Any] | None = None
    risk_result: dict[str, Any] | None = None
    for kind, outcome in zip(kinds, results):
        if isinstance(outcome, Exception):
            logger.warning("Qualitative %s task errored for %s: %s", kind, ticker, outcome)
            continue
        if outcome is None:
            continue
        if kind == "mdna":
            mdna_result = outcome
        else:
            risk_result = outcome

    if mdna_result is None and risk_result is None:
        writer(AgentThinkingEvent(
            node="qualitative_analysis",
            content="Both LLM calls failed. Qualitative analysis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="qualitative_analysis",
            summary="Qualitative analysis skipped: LLM error.",
        ).model_dump())
        return {
            "qualitative_result": None,
            "reasoning_steps": ["Qualitative: error — all LLM calls failed"],
        }

    # Emit MD&A card (if available).
    if mdna_result is not None:
        writer(ComponentEvent(
            component_type="qualitative_insights_card",
            props={
                "entity_name": financials.entity_name,
                "ticker": ticker,
                "filing_date": filing["filing_date"],
                "accession_number": filing["accession_number"],
                "filing_url": filing["url"],
                **mdna_result,
            },
        ).model_dump())
        writer(AgentThinkingEvent(
            node="qualitative_analysis",
            content=(
                f"MD&A tone: {mdna_result['tone']}. "
                f"{len(mdna_result['growth_drivers'])} growth drivers, "
                f"{len(mdna_result['management_concerns'])} concerns, "
                f"{len(mdna_result['notable_quotes'])} verified quotes."
            ),
        ).model_dump())

    # Emit Risk Factors card (if available).
    if risk_result is not None:
        writer(ComponentEvent(
            component_type="risk_factors_card",
            props={
                "entity_name": financials.entity_name,
                "ticker": ticker,
                "filing_date": filing["filing_date"],
                "accession_number": filing["accession_number"],
                "filing_url": filing["url"],
                **risk_result,
            },
        ).model_dump())
        writer(AgentThinkingEvent(
            node="qualitative_analysis",
            content=(
                f"Risk Factors: {len(risk_result['top_risks'])} top risks identified "
                f"across {len(risk_result['risk_categories'])} categories "
                f"(confidence {risk_result['confidence']:.0%})."
            ),
        ).model_dump())

    # Compose the nested state payload for downstream consumers (thesis node).
    combined: dict[str, Any] = {
        "ticker": ticker,
        "filing_date": filing["filing_date"],
        "accession_number": filing["accession_number"],
        "filing_url": filing["url"],
        "mdna": mdna_result,
        "risk_factors": risk_result,
    }

    # Summary line for the pipeline step log.
    completed_parts: list[str] = []
    if mdna_result is not None:
        completed_parts.append(f"MD&A tone: {mdna_result['tone']}")
    if risk_result is not None:
        completed_parts.append(f"{len(risk_result['top_risks'])} top risks")
    writer(StepCompleteEvent(
        node="qualitative_analysis",
        summary=(
            "10-K qualitative analysis complete — "
            + "; ".join(completed_parts)
            + "."
        ),
    ).model_dump())

    reasoning: list[str] = []
    if mdna_result:
        reasoning.append(f"Qualitative MD&A tone: {mdna_result['tone']}")
    if risk_result:
        reasoning.append(
            f"Qualitative top risks: "
            + ", ".join(r["title"] for r in risk_result["top_risks"])
        )

    return {
        "qualitative_result": combined,
        "reasoning_steps": reasoning,
    }
