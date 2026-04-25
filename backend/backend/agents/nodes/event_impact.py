"""Node: Event Impact Analysis — maps news events to DCF parameter adjustments.

Two-step LLM process (both calls go through the shared ``services.llm`` client):

1. Filter articles that may impact valuation parameters (``event_filter_v1``)
2. Analyze parameter-level impacts and produce adjustment recommendations
   (``event_analysis_v1``)

Then applies adjustments and recalculates DCF.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.types import StreamWriter

from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    StepCompleteEvent,
)
from backend.services.llm import (
    LLMError,
    get_llm_client,
    is_llm_configured,
    sanitize_list,
)

from .event_impact_math import (
    apply_all_adjustments,
    recalculate_dcf,
    validate_analysis_response,
    validate_filter_response,
)

logger = logging.getLogger(__name__)


async def _call_llm(
    *,
    prompt_name: str,
    variables: dict[str, Any],
    task_tag: str,
) -> dict[str, Any] | None:
    """Single LLM call returning a parsed dict, or None on any LLMError."""
    try:
        client = get_llm_client()
        return await client.complete_json(
            prompt_name=prompt_name,
            version=1,
            variables=variables,
            task_tag=task_tag,
        )
    except LLMError as e:
        logger.warning("Event impact LLM call '%s' failed: %s", prompt_name, e)
        return None


async def event_impact_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    """Analyze event impact on valuation parameters and recalculate DCF."""
    financials = state["financials"]
    sentiment_result = state.get("event_sentiment_result")
    dcf_result = state.get("dcf_result")

    if financials is None:
        writer(StepCompleteEvent(
            node="event_impact",
            summary="Event impact skipped: no financial data.",
        ).model_dump())
        return {
            "event_impact_result": None,
            "reasoning_steps": ["Event impact: skipped — no financial data"],
        }

    if not sentiment_result or not sentiment_result.get("articles"):
        writer(StepCompleteEvent(
            node="event_impact",
            summary="Event impact skipped: no articles to analyze.",
        ).model_dump())
        return {
            "event_impact_result": None,
            "reasoning_steps": ["Event impact: skipped — no articles"],
        }

    if not dcf_result:
        writer(StepCompleteEvent(
            node="event_impact",
            summary="Event impact skipped: no DCF result.",
        ).model_dump())
        return {
            "event_impact_result": None,
            "reasoning_steps": ["Event impact: skipped — no DCF result"],
        }

    if not is_llm_configured():
        writer(AgentThinkingEvent(
            node="event_impact",
            content="LLM API key not configured. Event impact analysis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="event_impact",
            summary="Event impact skipped: LLM API key not set.",
        ).model_dump())
        return {
            "event_impact_result": None,
            "reasoning_steps": ["Event impact: skipped — no LLM API key"],
        }

    try:
        return await _run_event_impact(financials, sentiment_result, dcf_result, writer)
    except Exception:
        logger.exception(
            "Event impact analysis failed for %s",
            financials.ticker if financials else "unknown",
        )
        writer(AgentThinkingEvent(
            node="event_impact",
            content="Event impact analysis encountered an internal error.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="event_impact",
            summary="Event impact analysis encountered an error.",
        ).model_dump())
        return {
            "event_impact_result": None,
            "reasoning_steps": ["Event impact: error — analysis interrupted"],
        }


async def _run_event_impact(
    financials: Any,
    sentiment_result: dict[str, Any],
    dcf_result: dict[str, Any],
    writer: StreamWriter,
) -> dict[str, Any]:
    ticker = financials.ticker
    reasoning: list[str] = []

    writer(AgentThinkingEvent(
        node="event_impact",
        content=f"Analyzing event impact on valuation for {ticker}...",
    ).model_dump())

    articles = sentiment_result.get("articles", [])
    assumptions = dcf_result.get("assumptions", {})

    if not assumptions:
        writer(StepCompleteEvent(
            node="event_impact",
            summary="Event impact skipped: no DCF assumptions.",
        ).model_dump())
        return {
            "event_impact_result": None,
            "reasoning_steps": ["Event impact: skipped — no DCF assumptions"],
        }

    original_assumptions = {
        "growth_rate": assumptions.get("growth_rate", 10.0),
        "terminal_growth_rate": assumptions.get("terminal_growth_rate", 3.0),
        "discount_rate": assumptions.get("discount_rate", 10.0),
        "latest_fcf": assumptions.get("latest_fcf", 0),
    }

    reasoning.append(
        f"Original DCF assumptions: growth={original_assumptions['growth_rate']:.1f}%, "
        f"terminal={original_assumptions['terminal_growth_rate']:.1f}%, "
        f"WACC={original_assumptions['discount_rate']:.1f}%, "
        f"FCF=${original_assumptions['latest_fcf']:,.0f}"
    )

    # --- LLM Call 1: Filter impactful articles ---
    writer(AgentThinkingEvent(
        node="event_impact",
        content=f"Screening {len(articles)} articles for valuation-relevant events...",
    ).model_dump())

    filter_article_lines: list[str] = []
    for article in articles:
        headline = article.get("headline", "")
        source = article.get("source", "")
        event_type = article.get("event_type", "")
        parts = [str(headline)]
        if source:
            parts.append(f"Source: {source}")
        if event_type:
            parts.append(f"Type: {event_type}")
        filter_article_lines.append(" | ".join(parts))

    filter_articles_block = sanitize_list(filter_article_lines, max_item_len=500)

    filter_response = await _call_llm(
        prompt_name="event_filter",
        variables={"ticker": ticker, "articles_block": filter_articles_block},
        task_tag="event_filter",
    )
    filter_result = validate_filter_response(filter_response)

    if not filter_result or not filter_result.get("impactful_indices"):
        writer(AgentThinkingEvent(
            node="event_impact",
            content="No material events found that would impact valuation parameters.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="event_impact",
            summary="Event impact: no material events found.",
        ).model_dump())
        return {
            "event_impact_result": None,
            "reasoning_steps": [
                "Event impact: no material events affecting valuation found"
            ],
        }

    impactful_indices = filter_result["impactful_indices"]
    reasoning.append(
        f"LLM identified {len(impactful_indices)} impactful articles: "
        f"{filter_result.get('reasoning', '')}"
    )

    writer(AgentThinkingEvent(
        node="event_impact",
        content=f"Found {len(impactful_indices)} articles with valuation impact. "
                f"Analyzing parameter adjustments...",
    ).model_dump())

    # --- LLM Call 2: Analyze parameter impacts ---
    impactful_articles = [
        articles[i] for i in impactful_indices if 0 <= i < len(articles)
    ]

    analysis_article_lines: list[str] = []
    for article in impactful_articles:
        headline = article.get("headline", "")
        source = article.get("source", "")
        sentiment = article.get("sentiment", 0)
        parts = [str(headline)]
        if source:
            parts.append(f"Source: {source}")
        parts.append(f"Sentiment: {sentiment:.2f}")
        analysis_article_lines.append(" | ".join(parts))

    analysis_articles_block = sanitize_list(analysis_article_lines, max_item_len=500)

    analysis_response = await _call_llm(
        prompt_name="event_analysis",
        variables={
            "ticker": ticker,
            "articles_block": analysis_articles_block,
            "growth_rate": original_assumptions["growth_rate"],
            "terminal_growth_rate": original_assumptions["terminal_growth_rate"],
            "discount_rate": original_assumptions["discount_rate"],
            "latest_fcf": original_assumptions["latest_fcf"],
        },
        task_tag="event_analysis",
    )
    analysis_result = validate_analysis_response(analysis_response)

    if not analysis_result:
        writer(AgentThinkingEvent(
            node="event_impact",
            content="LLM analysis returned invalid results. No adjustments applied.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="event_impact",
            summary="Event impact: analysis returned invalid results.",
        ).model_dump())
        return {
            "event_impact_result": None,
            "reasoning_steps": [
                "Event impact: LLM analysis returned invalid results"
            ],
        }

    # --- Apply adjustments and recalculate DCF ---
    parameter_adjustments = analysis_result["adjustments"]
    adjusted_assumptions = apply_all_adjustments(
        original_assumptions, parameter_adjustments,
    )

    reasoning.append(
        f"Adjusted assumptions: growth={adjusted_assumptions['growth_rate']:.1f}%, "
        f"terminal={adjusted_assumptions['terminal_growth_rate']:.1f}%, "
        f"WACC={adjusted_assumptions['discount_rate']:.1f}%, "
        f"FCF=${adjusted_assumptions['latest_fcf']:,.0f}"
    )

    shares = None
    if financials.diluted_shares:
        shares = financials.diluted_shares[-1].value

    recalculated_dcf = recalculate_dcf(adjusted_assumptions, shares)

    reasoning.append(f"Impact analysis summary: {analysis_result['summary']}")
    reasoning.append(f"Confidence: {analysis_result['confidence']:.0%}")

    if recalculated_dcf.get("intrinsic_value_per_share"):
        reasoning.append(
            f"Recalculated intrinsic value: "
            f"${recalculated_dcf['intrinsic_value_per_share']:,.2f}/share"
        )

    writer(AgentThinkingEvent(
        node="event_impact",
        content=(
            f"Event impact analysis: {analysis_result['summary']} "
            f"(confidence: {analysis_result['confidence']:.0%})"
        ),
    ).model_dump())

    result: dict[str, Any] = {
        "ticker": ticker,
        "original_assumptions": original_assumptions,
        "parameter_adjustments": parameter_adjustments,
        "adjusted_assumptions": {
            "growth_rate": round(adjusted_assumptions["growth_rate"], 2),
            "terminal_growth_rate": round(adjusted_assumptions["terminal_growth_rate"], 2),
            "discount_rate": round(adjusted_assumptions["discount_rate"], 2),
            "latest_fcf": round(adjusted_assumptions["latest_fcf"], 2),
        },
        "recalculated_dcf": recalculated_dcf,
        "impactful_articles": impactful_articles,
        "summary": analysis_result["summary"],
        "confidence": analysis_result["confidence"],
    }

    writer(ComponentEvent(
        component_type="event_impact_card",
        props={"ticker": ticker, **result},
    ).model_dump())

    writer(StepCompleteEvent(
        node="event_impact",
        summary=(
            f"Event impact: {analysis_result['summary']} "
            f"(confidence: {analysis_result['confidence']:.0%}). "
            f"{len(impactful_articles)} articles affected valuation."
        ),
    ).model_dump())

    return {
        "event_impact_result": result,
        "reasoning_steps": reasoning,
    }
