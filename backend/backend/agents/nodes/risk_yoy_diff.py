"""Node: Risk Yo-Y Diff — compare Risk Factors between consecutive 10-Ks.

Fetches the latest 10-K and the immediately prior 10-K, extracts each year's
``Item 1A. Risk Factors`` section, and asks the LLM to surface MATERIAL
year-over-year changes (newly added / removed / escalated / de-escalated
risks). Every change item must carry verbatim evidence quotes from the
correct year's source text — quotes that don't verify cause the change to
be dropped, eliminating hallucinated diffs.

Runs after ``qualitative_analysis`` (so it benefits from the in-process
10-K HTML cache populated there) and before ``investment_thesis`` (so the
thesis can reference YoY shifts in its narrative).
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
    ExtractedSection,
    extract_risk_factors,
    truncate_head,
)

from ._pro_gate import emit_lock, is_pro_user
from .qualitative_analysis import RiskCategory, _normalize, verify_quotes

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


ChangeKind = Literal["new", "removed", "escalated", "de_escalated"]


class RiskChange(BaseModel):
    """One material year-over-year change in a risk factor."""

    kind: ChangeKind
    category: RiskCategory
    title: str = Field(..., min_length=1, max_length=150)
    description: str = Field(..., min_length=1, max_length=500)
    # Both quotes nullable but presence depends on kind (validated post-hoc).
    quote_current: str | None = None
    quote_prior: str | None = None


class RiskYoYDiff(BaseModel):
    """Structured output produced by ``risk_yoy_diff_v1``."""

    new_risks: list[RiskChange] = Field(default_factory=list, max_length=8)
    removed_risks: list[RiskChange] = Field(default_factory=list, max_length=8)
    escalated_risks: list[RiskChange] = Field(default_factory=list, max_length=8)
    de_escalated_risks: list[RiskChange] = Field(default_factory=list, max_length=8)
    summary: str = Field(..., min_length=1, max_length=600)
    confidence: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Dual-quote verifier
# ---------------------------------------------------------------------------


def _verify_change(
    change: RiskChange, *, current_text: str, prior_text: str,
) -> bool:
    """Return True iff the quotes required by ``change.kind`` verify.

    - kind="new"          → requires verifiable ``quote_current``; ``quote_prior`` ignored.
    - kind="removed"      → requires verifiable ``quote_prior``; ``quote_current`` ignored.
    - kind="escalated"    → requires BOTH quotes verify.
    - kind="de_escalated" → requires BOTH quotes verify.
    """
    norm_current = _normalize(current_text)
    norm_prior = _normalize(prior_text)

    def ok(quote: str | None, source: str) -> bool:
        if not isinstance(quote, str) or len(quote.strip()) < 40:
            return False
        return _normalize(quote) in source

    if change.kind == "new":
        return ok(change.quote_current, norm_current)
    if change.kind == "removed":
        return ok(change.quote_prior, norm_prior)
    # escalated / de_escalated
    return ok(change.quote_current, norm_current) and ok(change.quote_prior, norm_prior)


def _filter_changes(
    items: list[RiskChange], *, current_text: str, prior_text: str,
) -> tuple[list[dict[str, Any]], int]:
    """Apply ``_verify_change`` to a list and return (kept_payloads, dropped_count)."""
    kept: list[dict[str, Any]] = []
    dropped = 0
    for change in items:
        if _verify_change(change, current_text=current_text, prior_text=prior_text):
            kept.append(change.model_dump())
        else:
            dropped += 1
    return kept, dropped


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


async def _fetch_and_parse(
    cik: int, *, n_back: int,
) -> tuple[dict[str, Any], ExtractedSection] | None:
    """Fetch a 10-K and its Risk Factors section. Returns ``None`` on any miss."""
    filing = await sec_client.fetch_10k(cik, n_back=n_back)
    if not filing:
        return None
    section = extract_risk_factors(filing["html"])
    if section is None:
        return None
    return filing, section


async def risk_yoy_diff_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    """Compute the year-over-year change in Risk Factors between 10-Ks."""
    financials = state.get("financials")
    if financials is None or not getattr(financials, "cik", None):
        writer(StepCompleteEvent(
            node="risk_yoy_diff",
            summary="Risk YoY skipped: no CIK available.",
        ).model_dump())
        return {
            "risk_yoy_diff_result": None,
            "reasoning_steps": ["Risk YoY: skipped — no CIK"],
        }

    if not is_pro_user(state):
        return emit_lock(
            writer=writer,
            node_name="risk_yoy_diff",
            feature_label="Year-over-year 10-K risk diff",
            locked_component_type="risk_yoy_diff_locked_card",
            state_field="risk_yoy_diff_result",
            ticker=financials.ticker,
            entity_name=financials.entity_name,
        ).payload

    if not is_llm_configured():
        writer(AgentThinkingEvent(
            node="risk_yoy_diff",
            content="LLM not configured. Risk YoY diff skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="risk_yoy_diff",
            summary="Risk YoY skipped: LLM API key not set.",
        ).model_dump())
        return {
            "risk_yoy_diff_result": None,
            "reasoning_steps": ["Risk YoY: skipped — no LLM API key"],
        }

    ticker = financials.ticker
    cik = int(financials.cik)

    writer(AgentThinkingEvent(
        node="risk_yoy_diff",
        content=f"Fetching {ticker} latest + prior-year 10-K filings...",
    ).model_dump())

    try:
        current = await _fetch_and_parse(cik, n_back=0)
        prior = await _fetch_and_parse(cik, n_back=1)
    except Exception:
        logger.exception("Risk YoY fetch crashed for %s", ticker)
        current = None
        prior = None

    if current is None or prior is None:
        writer(AgentThinkingEvent(
            node="risk_yoy_diff",
            content=(
                "Need both current and prior-year 10-Ks with parseable Risk "
                "Factors. One or both unavailable — skipping."
            ),
        ).model_dump())
        writer(StepCompleteEvent(
            node="risk_yoy_diff",
            summary="Risk YoY skipped: insufficient filings.",
        ).model_dump())
        return {
            "risk_yoy_diff_result": None,
            "reasoning_steps": ["Risk YoY: skipped — need 2 consecutive 10-Ks"],
        }

    cur_filing, cur_section = current
    prev_filing, prev_section = prior

    cur_truncated = truncate_head(cur_section.text, max_chars=12_000)
    prev_truncated = truncate_head(prev_section.text, max_chars=12_000)

    writer(AgentThinkingEvent(
        node="risk_yoy_diff",
        content=(
            f"Comparing Risk Factors: {cur_filing['filing_date']} "
            f"({cur_section.char_count:,} → {len(cur_truncated):,} chars) vs "
            f"{prev_filing['filing_date']} "
            f"({prev_section.char_count:,} → {len(prev_truncated):,} chars)."
        ),
    ).model_dump())

    try:
        client = get_llm_client()
        diff: RiskYoYDiff = await client.complete_json(
            prompt_name="risk_yoy_diff",
            version=1,
            variables={
                "ticker": ticker,
                "company_name": financials.entity_name,
                "current_filing_date": cur_filing["filing_date"],
                "current_accession": cur_filing["accession_number"],
                "prior_filing_date": prev_filing["filing_date"],
                "prior_accession": prev_filing["accession_number"],
                "current_risk_text": cur_truncated,
                "prior_risk_text": prev_truncated,
            },
            task_tag="risk_yoy_diff",
            response_model=RiskYoYDiff,
        )
    except LLMError as e:
        logger.warning("Risk YoY LLM call failed for %s: %s", ticker, e)
        writer(AgentThinkingEvent(
            node="risk_yoy_diff",
            content="LLM call for YoY diff failed. Skipping.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="risk_yoy_diff",
            summary="Risk YoY skipped: LLM error.",
        ).model_dump())
        return {
            "risk_yoy_diff_result": None,
            "reasoning_steps": [f"Risk YoY: error — {e}"],
        }
    except Exception:
        logger.exception("Risk YoY node crashed for %s", ticker)
        writer(StepCompleteEvent(
            node="risk_yoy_diff",
            summary="Risk YoY skipped: unexpected error.",
        ).model_dump())
        return {
            "risk_yoy_diff_result": None,
            "reasoning_steps": ["Risk YoY: error — unexpected"],
        }

    # Verify quotes against the FULL section text (not the truncated input —
    # the LLM may have quoted from the truncated portion, which is a subset
    # of the full text, so verifying against the full text is correct).
    new_risks, drop_n = _filter_changes(
        diff.new_risks,
        current_text=cur_section.text, prior_text=prev_section.text,
    )
    removed_risks, drop_r = _filter_changes(
        diff.removed_risks,
        current_text=cur_section.text, prior_text=prev_section.text,
    )
    escalated, drop_e = _filter_changes(
        diff.escalated_risks,
        current_text=cur_section.text, prior_text=prev_section.text,
    )
    de_escalated, drop_d = _filter_changes(
        diff.de_escalated_risks,
        current_text=cur_section.text, prior_text=prev_section.text,
    )
    total_dropped = drop_n + drop_r + drop_e + drop_d
    if total_dropped:
        logger.warning(
            "risk_yoy_diff %s dropped %d unverifiable change items",
            ticker, total_dropped,
        )

    result: dict[str, Any] = {
        "ticker": ticker,
        "current_filing": {
            "filing_date": cur_filing["filing_date"],
            "accession_number": cur_filing["accession_number"],
            "url": cur_filing["url"],
        },
        "prior_filing": {
            "filing_date": prev_filing["filing_date"],
            "accession_number": prev_filing["accession_number"],
            "url": prev_filing["url"],
        },
        "summary": diff.summary,
        "new_risks": new_risks,
        "removed_risks": removed_risks,
        "escalated_risks": escalated,
        "de_escalated_risks": de_escalated,
        "rejected_change_count": total_dropped,
        "confidence": diff.confidence,
    }

    writer(ComponentEvent(
        component_type="risk_yoy_diff_card",
        props={
            "entity_name": financials.entity_name,
            **result,
        },
    ).model_dump())

    bucket_summary = (
        f"{len(new_risks)} new / {len(removed_risks)} removed / "
        f"{len(escalated)} escalated / {len(de_escalated)} de-escalated"
    )
    writer(AgentThinkingEvent(
        node="risk_yoy_diff",
        content=(
            f"YoY changes — {bucket_summary}"
            + (f" ({total_dropped} unverifiable dropped)" if total_dropped else "")
            + f". Confidence {diff.confidence:.0%}."
        ),
    ).model_dump())

    writer(StepCompleteEvent(
        node="risk_yoy_diff",
        summary=f"Risk YoY: {bucket_summary} (confidence {diff.confidence:.0%}).",
    ).model_dump())

    return {
        "risk_yoy_diff_result": result,
        "reasoning_steps": [
            f"Risk YoY: {bucket_summary}",
            f"Filings: {prev_filing['filing_date']} → {cur_filing['filing_date']}",
        ],
    }
