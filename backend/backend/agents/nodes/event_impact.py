"""Node: Event Impact Analysis — maps news events to DCF parameter adjustments.

Two-step LLM process:
1. Filter articles that may impact valuation parameters
2. Analyze parameter-level impacts and produce adjustment recommendations

Then applies adjustments and recalculates DCF.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from langgraph.types import StreamWriter

from backend.config import settings
from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    StepCompleteEvent,
)

from .event_impact_math import (
    apply_all_adjustments,
    recalculate_dcf,
    validate_analysis_response,
    validate_filter_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM prompt templates
# ---------------------------------------------------------------------------

_FILTER_SYSTEM_PROMPT = """You are a financial analyst expert at identifying news events that materially affect a company's valuation parameters.

Given a list of news articles, identify which ones would impact:
- Revenue growth trajectory → growth_rate
- Operating profit margins → margin_adjustment
- Free cash flow (one-time or structural) → fcf_one_time_adjust
- Risk profile (litigation, regulatory, competitive) → risk_adjustment / discount_rate
- Long-term growth assumptions → terminal_growth_rate

EXCLUDE articles that are:
- Routine analyst ratings (unless they present new fundamental arguments)
- Generic market commentary without company-specific impact
- Earnings reports that are already priced in (UNLESS guidance changed)
- Articles that only repeat known information

Return ONLY valid JSON:
{
  "impactful_indices": [list of 0-based indices of impactful articles],
  "reasoning": "brief explanation of selection"
}

If no articles are impactful, return: {"impactful_indices": [], "reasoning": "No material events found"}
"""

_ANALYSIS_SYSTEM_PROMPT = """You are a financial analyst performing event-driven valuation adjustments.

Given impactful news articles and current DCF assumptions, determine parameter adjustments.

Current DCF assumptions are provided as percentages:
- growth_rate: FCF growth rate (%)
- terminal_growth_rate: long-term perpetual growth rate (%)
- discount_rate: WACC / discount rate (%)
- latest_fcf: most recent free cash flow (absolute dollar value)

For each parameter you believe should be adjusted, provide:
- type: "delta" (add to current), "multiplier" (multiply current), or "absolute" (replace)
- value: the adjustment value
- reasoning: why this adjustment is warranted

BE CONSERVATIVE:
- Only suggest adjustments you are confident about
- Consider macro factors (interest rates, commodity prices, etc.)
- Each adjustment must have clear reasoning
- Smaller adjustments are preferred when uncertain

Available parameters:
1. growth_rate (delta, %) — direct FCF growth rate change
2. terminal_growth_rate (delta, %) — long-term growth assumption change
3. discount_rate (delta, %) — WACC/risk premium change
4. risk_adjustment (delta, %) — risk premium change (added to discount_rate)
5. revenue_adjustment (multiplier) — revenue trajectory multiplier (e.g. 0.95 = 5% lower)
6. margin_adjustment (delta, %) — margin change (0.5x weight applied to growth_rate)
7. fcf_one_time_adjust (absolute, $) — one-time FCF replacement value

Return ONLY valid JSON:
{
  "adjustments": {
    "growth_rate": {"type": "delta", "value": 2.0, "reasoning": "..."} | null,
    "terminal_growth_rate": null,
    "discount_rate": {"type": "delta", "value": 0.5, "reasoning": "..."} | null,
    "risk_adjustment": null,
    "revenue_adjustment": null,
    "margin_adjustment": null,
    "fcf_one_time_adjust": null
  },
  "summary": "one sentence summary of overall impact",
  "confidence": 0.75
}

Set parameters to null if no adjustment is needed. Confidence should reflect your overall certainty (0.0 to 1.0).
"""

# ---------------------------------------------------------------------------
# LLM client (reuse singleton pattern from llm_sentiment.py)
# ---------------------------------------------------------------------------

_llm_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return a lazily-initialized, reusable httpx client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = httpx.AsyncClient(timeout=30.0)
    return _llm_client


async def close_event_impact_client() -> None:
    """Close the shared httpx client. Call during app shutdown."""
    global _llm_client
    if _llm_client is not None:
        await _llm_client.aclose()
        _llm_client = None


def _validate_base_url(url: str) -> bool:
    """Ensure the LLM base URL uses HTTPS (or localhost for dev)."""
    if url.startswith("https://"):
        return True
    if url.startswith("http://localhost") or url.startswith("http://127.0.0.1"):
        return True
    return False


async def _call_llm(
    system_prompt: str, user_prompt: str,
) -> dict[str, Any] | None:
    """Make a single LLM API call. Returns parsed JSON or None on failure."""
    if not settings.llm_api_key or not settings.llm_base_url:
        return None

    if not _validate_base_url(settings.llm_base_url):
        logger.warning(
            "LLM base URL must use HTTPS (got %s). Skipping.",
            settings.llm_base_url,
        )
        return None

    try:
        resp = await _get_client().post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model or "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        if content.strip().startswith("```"):
            lines = content.strip().split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            content = "\n".join(lines)

        return json.loads(content)

    except httpx.HTTPStatusError as e:
        logger.warning(
            "Event impact LLM HTTP %s", e.response.status_code,
        )
    except httpx.RequestError as e:
        logger.warning("Event impact LLM request error: %s", e)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Event impact LLM parse error: %s", e)
    except Exception as e:
        logger.warning("Event impact LLM unexpected error: %s", e)

    return None


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


async def event_impact_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    """Analyze event impact on valuation parameters and recalculate DCF."""
    financials = state["financials"]
    sentiment_result = state.get("event_sentiment_result")
    dcf_result = state.get("dcf_result")

    # Guard: skip if prerequisites unavailable
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

    if not settings.llm_api_key or not settings.llm_base_url:
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

    # --- Extract articles and assumptions ---
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

    article_texts = []
    for i, article in enumerate(articles):
        headline = article.get("headline", "")
        source = article.get("source", "")
        event_type = article.get("event_type", "")
        article_texts.append(
            f"[{i}] {headline}"
            + (f" | Source: {source}" if source else "")
            + (f" | Type: {event_type}" if event_type else "")
        )

    filter_prompt = (
        f"Articles for {ticker}:\n\n<articles>\n"
        + "\n".join(article_texts)
        + "\n</articles>"
    )

    filter_response = await _call_llm(_FILTER_SYSTEM_PROMPT, filter_prompt)
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

    analysis_texts = []
    for i, article in enumerate(impactful_articles):
        headline = article.get("headline", "")
        source = article.get("source", "")
        sentiment = article.get("sentiment", 0)
        analysis_texts.append(
            f"[{i}] {headline}"
            + (f" | Source: {source}" if source else "")
            + f" | Sentiment: {sentiment:.2f}"
        )

    analysis_prompt = (
        f"Impactful articles for {ticker}:\n\n<articles>\n"
        + "\n".join(analysis_texts)
        + "\n</articles>\n\n"
        f"Current DCF assumptions:\n"
        f"- growth_rate: {original_assumptions['growth_rate']:.1f}%\n"
        f"- terminal_growth_rate: {original_assumptions['terminal_growth_rate']:.1f}%\n"
        f"- discount_rate: {original_assumptions['discount_rate']:.1f}%\n"
        f"- latest_fcf: ${original_assumptions['latest_fcf']:,.0f}\n"
    )

    analysis_response = await _call_llm(_ANALYSIS_SYSTEM_PROMPT, analysis_prompt)
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

    # Shares outstanding
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

    # --- Build result ---
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

    # Emit component
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
