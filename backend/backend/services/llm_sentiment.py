"""LLM-based news sentiment analysis using OpenAI-compatible API (DeepSeek).

Calls the chat/completions endpoint with a structured prompt and returns
parsed sentiment data. Returns None on any failure (graceful degradation).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a financial news sentiment analyst. Analyze the given news articles for the specified stock ticker.

For each article, classify:
- sentiment: a float from -1.0 (very bearish) to +1.0 (very bullish)
- event_type: one of "earnings", "guidance", "ma", "regulatory", "product", "executive", "macro", "analyst", "other"
- confidence: a float from 0.0 to 1.0

Also provide:
- overall_score: weighted average sentiment from -1.0 to +1.0
- summary: 1-2 sentence summary of the overall sentiment
- key_events: list of notable event descriptions (max 5), ordered by importance (most impactful first)

Return ONLY valid JSON matching this schema:
{
  "articles": [{"sentiment": float, "event_type": str, "confidence": float}],
  "overall_score": float,
  "summary": str,
  "key_events": [str]
}"""

# Module-level lazy singleton client
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return a lazily-initialized, reusable httpx client."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


async def close_llm_client() -> None:
    """Close the shared LLM httpx client. Call during app shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _validate_llm_response(result: dict[str, Any]) -> dict[str, Any] | None:
    """Validate and sanitize the LLM response structure.

    Returns a new validated dict or None if invalid.
    """
    if not isinstance(result, dict):
        return None

    # Work on a shallow copy to avoid mutating the caller's dict
    result = dict(result)

    # Validate overall_score
    overall_score = result.get("overall_score")
    if not isinstance(overall_score, (int, float)):
        return None
    result["overall_score"] = max(-1.0, min(1.0, float(overall_score)))

    # Validate summary
    summary = result.get("summary")
    if summary is not None and not isinstance(summary, str):
        result["summary"] = str(summary)

    # Validate key_events
    key_events = result.get("key_events")
    if isinstance(key_events, list):
        result["key_events"] = [str(e) for e in key_events[:5]]
    else:
        result["key_events"] = []

    # Validate articles list
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


def _validate_base_url(url: str) -> bool:
    """Ensure the LLM base URL uses HTTPS (or localhost for dev)."""
    if url.startswith("https://"):
        return True
    # Allow http:// for local development only
    if url.startswith("http://localhost") or url.startswith("http://127.0.0.1"):
        return True
    return False


async def analyze_news_sentiment(
    ticker: str, articles: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Analyze news articles using LLM for sentiment scoring.

    Returns structured sentiment data or None on failure.
    """
    if not settings.llm_api_key or not settings.llm_base_url:
        return None

    if not _validate_base_url(settings.llm_base_url):
        logger.warning(
            "LLM base URL must use HTTPS (got %s). Skipping.",
            settings.llm_base_url,
        )
        return None

    if not articles:
        return None

    # Build article summaries for the prompt (limit to top 20)
    # Use XML delimiters to separate user content from instructions
    article_texts = []
    for i, article in enumerate(articles[:20], 1):
        headline = article.get("headline", "")
        summary = article.get("summary", "")
        source = article.get("source", "")
        date_str = article.get("datetime", "")
        article_texts.append(
            f"[{i}] {headline}"
            + (f" | Source: {source}" if source else "")
            + (f" | Date: {date_str}" if date_str else "")
            + (f" | {summary}" if summary else "")
        )

    user_prompt = (
        f"Analyze the following recent news articles for {ticker}:\n\n"
        "<articles>\n"
        + "\n".join(article_texts)
        + "\n</articles>"
    )

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
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2500,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        if content.strip().startswith("```"):
            lines = content.strip().split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        result = json.loads(content)

        return _validate_llm_response(result)

    except httpx.HTTPStatusError as e:
        logger.warning(
            "LLM sentiment analysis HTTP %s for %s",
            e.response.status_code,
            ticker,
        )
    except httpx.RequestError as e:
        logger.warning("LLM sentiment analysis request error for %s: %s", ticker, e)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("LLM sentiment analysis parse error for %s: %s", ticker, e)
    except Exception as e:
        logger.warning("LLM sentiment analysis unexpected error for %s: %s", ticker, e)

    return None
