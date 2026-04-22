"""Node: Event & Sentiment analysis — news sentiment and insider activity.

Fetches news from Finnhub, classifies via LLM (DeepSeek) since Finnhub
Premium news-sentiment is unavailable on the Free plan, and retrieves
insider sentiment. Produces an overall sentiment score that feeds into
the strategy node for margin-of-safety adjustment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.types import StreamWriter

from backend.config import settings
from backend.models.agent_state import AnalysisState
from backend.models.events import (
    AgentThinkingEvent,
    ComponentEvent,
    StepCompleteEvent,
)
from backend.services.finnhub_client import finnhub_client
from backend.services.llm_sentiment import analyze_news_sentiment
from backend.services.sec_client import sec_client
from backend.services.ticker_resolver import ticker_resolver

from .event_sentiment_math import (
    classify_event_type,
    compute_overall_sentiment,
    filter_by_authoritative_source,
    filter_relevant_articles,
)

logger = logging.getLogger(__name__)


def _log_date_distribution(
    articles: list[dict[str, Any]], label: str,
) -> None:
    """Log the date distribution of articles for debugging."""
    if not articles:
        return
    dates: list[str] = []
    for a in articles:
        dt = a.get("datetime")
        if isinstance(dt, (int, float)) and dt > 0:
            try:
                dates.append(
                    datetime.fromtimestamp(dt, tz=timezone.utc).strftime("%Y-%m-%d")
                )
            except (OSError, ValueError):
                pass
        elif isinstance(dt, str) and dt:
            dates.append(str(dt)[:10])
    if dates:
        # Count per date
        counts: dict[str, int] = {}
        for d in dates:
            counts[d] = counts.get(d, 0) + 1
        sorted_dates = sorted(counts.items(), reverse=True)
        date_summary = ", ".join(f"{d}({n})" for d, n in sorted_dates[:7])
        logger.info(
            "%s date distribution (%d articles): %s%s",
            label, len(articles), date_summary,
            "..." if len(sorted_dates) > 7 else "",
        )


async def event_sentiment_node(
    state: AnalysisState, writer: StreamWriter,
) -> dict[str, Any]:
    """Analyze event sentiment: news + insider data → overall sentiment score."""
    financials = state["financials"]
    if financials is None:
        writer(StepCompleteEvent(
            node="event_sentiment",
            summary="Event sentiment skipped: no financial data.",
        ).model_dump())
        return {
            "event_sentiment_result": None,
            "reasoning_steps": ["Event sentiment: skipped — no financial data"],
        }

    if not settings.finnhub_api_key:
        writer(AgentThinkingEvent(
            node="event_sentiment",
            content="Finnhub API key not configured. Event sentiment analysis skipped.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="event_sentiment",
            summary="Event sentiment skipped: Finnhub API key not set.",
        ).model_dump())
        return {
            "event_sentiment_result": None,
            "reasoning_steps": ["Event sentiment: skipped — no Finnhub API key"],
        }

    try:
        return await _run_event_sentiment(financials.ticker, writer)
    except Exception:
        logger.exception(
            "Event sentiment analysis failed for %s",
            financials.ticker if financials else "unknown",
        )
        writer(AgentThinkingEvent(
            node="event_sentiment",
            content="Event sentiment analysis encountered an internal error.",
        ).model_dump())
        writer(StepCompleteEvent(
            node="event_sentiment",
            summary="Event sentiment analysis encountered an error.",
        ).model_dump())
        return {
            "event_sentiment_result": None,
            "reasoning_steps": ["Event sentiment: error — analysis interrupted"],
        }


async def _run_event_sentiment(
    ticker: str, writer: StreamWriter,
) -> dict[str, Any]:
    reasoning: list[str] = []

    writer(AgentThinkingEvent(
        node="event_sentiment",
        content=f"Analyzing event sentiment for {ticker}...",
    ).model_dump())

    # --- Fetch company news ---
    writer(AgentThinkingEvent(
        node="event_sentiment",
        content=f"Fetching recent news for {ticker} from Finnhub...",
    ).model_dump())

    raw_articles = await finnhub_client.get_company_news(ticker, days=30)
    reasoning.append(f"Fetched {len(raw_articles)} news articles (last 30 days)")
    _log_date_distribution(raw_articles, f"{ticker} raw articles")

    # Filter for relevance — Finnhub returns tangential mentions
    articles = filter_relevant_articles(ticker, raw_articles)
    filtered_out = len(raw_articles) - len(articles)
    if filtered_out > 0:
        reasoning.append(
            f"Filtered out {filtered_out} irrelevant articles, "
            f"kept {len(articles)} relevant"
        )
        logger.info(
            "Filtered %d/%d irrelevant articles for %s",
            filtered_out, len(raw_articles), ticker,
        )
    _log_date_distribution(articles, f"{ticker} after relevance filter")

    # Filter for authoritative sources only
    pre_source_count = len(articles)
    articles = filter_by_authoritative_source(articles)
    source_filtered = pre_source_count - len(articles)
    if source_filtered > 0:
        reasoning.append(
            f"Filtered out {source_filtered} non-authoritative articles, "
            f"kept {len(articles)} from authoritative sources"
        )
        logger.info(
            "Filtered %d non-authoritative articles for %s",
            source_filtered, ticker,
        )
    _log_date_distribution(articles, f"{ticker} after source filter")

    writer(AgentThinkingEvent(
        node="event_sentiment",
        content=f"Found {len(articles)} authoritative articles for {ticker}"
                f" ({filtered_out + source_filtered} filtered out).",
    ).model_dump())

    # --- Fetch SEC 8-K filings ---
    sec_filings: list[dict[str, Any]] = []
    try:
        cik, _company_name = await ticker_resolver.resolve(ticker)
        sec_filings = await sec_client.get_recent_8k_filings(cik, days=30)
        if sec_filings:
            reasoning.append(f"Found {len(sec_filings)} SEC 8-K filings (last 30 days)")
            writer(AgentThinkingEvent(
                node="event_sentiment",
                content=f"Found {len(sec_filings)} SEC 8-K filings for {ticker}.",
            ).model_dump())
    except Exception:
        logger.warning("Could not fetch SEC 8-K filings for %s", ticker, exc_info=True)

    # Convert 8-K filings into article-like dicts for unified LLM analysis
    sec_article_dicts: list[dict[str, Any]] = []
    for filing in sec_filings:
        desc = filing.get("description", "")
        headline = f"SEC 8-K Filing: {desc}" if desc else "SEC 8-K Filing"
        sec_article_dicts.append({
            "headline": headline,
            "source": "SEC EDGAR",
            "url": filing.get("url", ""),
            "datetime": filing.get("filing_date", ""),
            "sentiment": 0.0,
            "event_type": "regulatory",
            "confidence": 0.0,
            "is_sec_filing": True,
        })

    # Prepend 8-K items — they are high-quality, authoritative data
    articles = sec_article_dicts + articles

    # --- Try Finnhub Premium news-sentiment (returns None on Free plan) ---
    finnhub_sentiment = await finnhub_client.get_news_sentiment(ticker)

    # --- LLM-based sentiment analysis (fallback for Free plan) ---
    news_score: float | None = None
    llm_result: dict[str, Any] | None = None
    classified_articles: list[dict[str, Any]] = []

    if finnhub_sentiment and finnhub_sentiment.get("buzz"):
        # Premium data available — extract score
        buzz = finnhub_sentiment.get("buzz", {})
        # Finnhub buzz has articlesInLastWeek, etc. — use sentiment if present
        bearish = finnhub_sentiment.get("bearishPercent", 0)
        bullish = finnhub_sentiment.get("bullishPercent", 0)
        if bullish + bearish > 0:
            news_score = (bullish - bearish) / (bullish + bearish)
        reasoning.append("Used Finnhub Premium news-sentiment data")
    elif articles:
        # Use LLM to analyze articles
        writer(AgentThinkingEvent(
            node="event_sentiment",
            content=f"Analyzing {min(len(articles), 20)} articles via LLM for sentiment...",
        ).model_dump())

        llm_result = await analyze_news_sentiment(ticker, articles)

        if llm_result:
            news_score = llm_result.get("overall_score")
            reasoning.append(
                f"LLM sentiment analysis: overall score {news_score:.2f}"
                if news_score is not None
                else "LLM sentiment analysis: no score returned"
            )

            # Merge LLM article classifications with original articles.
            # Use headline-based matching instead of positional index,
            # since LLMs may reorder or skip articles.
            llm_articles = llm_result.get("articles", [])
            # Build a lookup from LLM article index to its data
            # The LLM returns articles in the same count/order it received
            # them, but match by position within the first pass, falling
            # back to headline substring matching.
            llm_lookup: dict[int, dict[str, Any]] = {}
            for idx, art in enumerate(llm_articles):
                llm_lookup[idx] = art

            for i, article in enumerate(articles[:20]):
                headline = article.get("headline", "")
                classified: dict[str, Any] = {
                    "headline": headline,
                    "source": article.get("source", ""),
                    "url": article.get("url", ""),
                    "date": article.get("datetime", ""),
                    "sentiment": 0.0,
                    "event_type": classify_event_type(headline),
                    "confidence": 0.0,
                    "is_sec_filing": article.get("is_sec_filing", False),
                }

                # Try positional match first (most reliable)
                llm_art = llm_lookup.get(i)
                if llm_art is None:
                    # Fallback: no LLM data for this position
                    classified_articles.append(classified)
                    continue

                classified["sentiment"] = llm_art.get("sentiment", 0.0)
                classified["event_type"] = llm_art.get(
                    "event_type", classified["event_type"]
                )
                classified["confidence"] = llm_art.get("confidence", 0.0)
                classified_articles.append(classified)
        else:
            # LLM unavailable — use keyword-based classification
            for article in articles[:20]:
                classified_articles.append({
                    "headline": article.get("headline", ""),
                    "source": article.get("source", ""),
                    "url": article.get("url", ""),
                    "date": article.get("datetime", ""),
                    "sentiment": 0.0,
                    "event_type": classify_event_type(article.get("headline", "")),
                    "confidence": 0.0,
                    "is_sec_filing": article.get("is_sec_filing", False),
                })
            reasoning.append("LLM unavailable — used keyword-based event classification only")

    # --- Fetch insider sentiment ---
    writer(AgentThinkingEvent(
        node="event_sentiment",
        content="Fetching insider sentiment data...",
    ).model_dump())

    insider_data = await finnhub_client.get_insider_sentiment(ticker, months=3)
    insider_score: float | None = None
    insider_mspr: float | None = None
    insider_net_change: int | None = None

    if insider_data:
        data_list = insider_data.get("data", [])
        if data_list:
            # Aggregate MSPR and net change across all months
            total_mspr = sum(d.get("mspr", 0) for d in data_list)
            total_change = sum(d.get("change", 0) for d in data_list)
            count = len(data_list)
            insider_mspr = round(total_mspr / count, 4) if count else None
            insider_net_change = total_change

            # Map MSPR to a -1 to +1 score
            # MSPR typically ranges from -1 to +1, but can exceed
            if insider_mspr is not None:
                insider_score = max(-1.0, min(1.0, insider_mspr))

            reasoning.append(
                f"Insider sentiment: MSPR={insider_mspr}, "
                f"net change={insider_net_change} shares"
            )
            writer(AgentThinkingEvent(
                node="event_sentiment",
                content=(
                    f"Insider sentiment: MSPR={insider_mspr}, "
                    f"net share change={insider_net_change}"
                ),
            ).model_dump())
        else:
            reasoning.append("Insider sentiment: no data available for the period")
    else:
        reasoning.append("Insider sentiment: data unavailable")

    # --- Compute overall sentiment ---
    overall = compute_overall_sentiment(
        news_score=news_score,
        insider_score=insider_score,
        insider_mspr=insider_mspr,
        insider_net_change=insider_net_change,
    )

    reasoning.append(
        f"Overall sentiment: {overall['sentiment_label']} "
        f"(score: {overall['overall_sentiment']:.2f})"
    )
    if overall["sentiment_adjustment"]["margin_of_safety_pct_delta"] != 0:
        reasoning.append(
            f"Sentiment MoS adjustment: "
            f"{overall['sentiment_adjustment']['margin_of_safety_pct_delta']:+d}%"
        )

    writer(AgentThinkingEvent(
        node="event_sentiment",
        content=(
            f"Overall sentiment: {overall['sentiment_label']} "
            f"(score: {overall['overall_sentiment']:.2f}). "
            f"{overall['sentiment_adjustment']['reasoning']}"
        ),
    ).model_dump())

    # --- Build result ---
    result: dict[str, Any] = {
        "ticker": ticker,
        "overall_sentiment": overall["overall_sentiment"],
        "sentiment_label": overall["sentiment_label"],
        "news_score": overall["news_score"],
        "insider_score": overall["insider_score"],
        "insider_mspr": insider_mspr,
        "insider_net_change": insider_net_change,
        "sentiment_adjustment": overall["sentiment_adjustment"],
        "articles": classified_articles,
        "article_count": len(articles),
        "llm_summary": llm_result.get("summary") if llm_result else None,
        "key_events": llm_result.get("key_events", []) if llm_result else [],
    }

    # Emit component
    writer(ComponentEvent(
        component_type="sentiment_card",
        props={"ticker": ticker, **result},
    ).model_dump())

    writer(StepCompleteEvent(
        node="event_sentiment",
        summary=(
            f"Event sentiment: {overall['sentiment_label']} "
            f"(score: {overall['overall_sentiment']:.2f}). "
            f"Analyzed {len(articles)} articles."
        ),
    ).model_dump())

    return {
        "event_sentiment_result": result,
        "reasoning_steps": reasoning,
    }
