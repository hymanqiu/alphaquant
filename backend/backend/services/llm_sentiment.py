"""LLM-based news sentiment analysis.

Thin adapter over the unified ``services.llm`` client: renders the
``sentiment_v1`` prompt, sanitizes user-controlled news content, and validates
the response shape. Returns ``None`` on any failure (graceful degradation).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.llm import (
    LLMError,
    get_llm_client,
    is_llm_configured,
    sanitize_list,
)

logger = logging.getLogger(__name__)


def _validate_llm_response(result: dict[str, Any]) -> dict[str, Any] | None:
    """Validate and sanitize the LLM response structure.

    Returns a new validated dict or None if invalid.
    """
    if not isinstance(result, dict):
        return None

    result = dict(result)

    overall_score = result.get("overall_score")
    if not isinstance(overall_score, (int, float)):
        return None
    result["overall_score"] = max(-1.0, min(1.0, float(overall_score)))

    summary = result.get("summary")
    if summary is not None and not isinstance(summary, str):
        result["summary"] = str(summary)

    key_events = result.get("key_events")
    if isinstance(key_events, list):
        result["key_events"] = [str(e) for e in key_events[:5]]
    else:
        result["key_events"] = []

    articles = result.get("articles")
    if isinstance(articles, list):
        validated: list[dict[str, Any]] = []
        for art in articles:
            if not isinstance(art, dict):
                continue
            sentiment = art.get("sentiment", 0.0)
            confidence = art.get("confidence", 0.0)
            validated.append({
                "sentiment": max(-1.0, min(1.0, float(sentiment))) if isinstance(sentiment, (int, float)) else 0.0,
                "event_type": str(art.get("event_type", "other")),
                "confidence": max(0.0, min(1.0, float(confidence))) if isinstance(confidence, (int, float)) else 0.0,
            })
        result["articles"] = validated
    else:
        result["articles"] = []

    return result


async def analyze_news_sentiment(
    ticker: str, articles: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Analyze news articles using LLM for sentiment scoring.

    Returns structured sentiment data or None on failure / misconfiguration.
    """
    if not is_llm_configured() or not articles:
        return None

    article_lines: list[str] = []
    for article in articles[:20]:
        headline = article.get("headline", "")
        summary = article.get("summary", "")
        source = article.get("source", "")
        date_str = article.get("datetime", "")
        parts = [str(headline)]
        if source:
            parts.append(f"Source: {source}")
        if date_str:
            parts.append(f"Date: {date_str}")
        if summary:
            parts.append(str(summary))
        article_lines.append(" | ".join(parts))

    articles_block = sanitize_list(article_lines, max_item_len=600)

    try:
        client = get_llm_client()
        parsed = await client.complete_json(
            prompt_name="sentiment",
            version=1,
            variables={"ticker": ticker, "articles_block": articles_block},
            task_tag="sentiment",
        )
    except LLMError as e:
        logger.warning("LLM sentiment analysis failed for %s: %s", ticker, e)
        return None

    return _validate_llm_response(parsed)
