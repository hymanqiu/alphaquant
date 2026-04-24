"""Pure computation functions for event & sentiment analysis.

No I/O — all functions are deterministic and testable.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Company name aliases — maps ticker → known company name patterns.
# Used to improve headline relevance detection.  For example, a headline
# "NVIDIA unveils new GPU" won't contain the ticker "NVDA" but should
# still score as highly relevant.
# ---------------------------------------------------------------------------

TICKER_ALIASES: dict[str, list[str]] = {
    "AAPL": ["apple"],
    "MSFT": ["microsoft"],
    "GOOGL": ["google", "alphabet"],
    "GOOG": ["google", "alphabet"],
    "AMZN": ["amazon"],
    "NVDA": ["nvidia"],
    "META": ["meta platforms", "facebook"],
    "TSLA": ["tesla"],
    "NFLX": ["netflix"],
    "AMD": ["amd", "advanced micro devices"],
    "INTC": ["intel"],
    "CRM": ["salesforce"],
    "ORCL": ["oracle"],
    "CSCO": ["cisco"],
    "ADBE": ["adobe"],
    "PYPL": ["paypal"],
    "UBER": ["uber"],
    "DIS": ["disney"],
    "BA": ["boeing"],
    "JPM": ["jpmorgan", "jpmorgan chase"],
    "GS": ["goldman sachs"],
    "V": ["visa"],
    "MA": ["mastercard"],
    "WMT": ["walmart"],
    "KO": ["coca-cola", "coca cola"],
    "PEP": ["pepsico", "pepsi"],
    "NKE": ["nike"],
    "MCD": ["mcdonald"],
    "SBUX": ["starbucks"],
    "XOM": ["exxonmobil", "exxon mobil", "exxon"],
    "CVX": ["chevron"],
    "PFE": ["pfizer"],
    "JNJ": ["johnson & johnson"],
    "UNH": ["unitedhealth"],
    "CVS": ["cvs health"],
    "LLY": ["eli lilly"],
    "ABBV": ["abbvie"],
    "MRK": ["merck"],
}


def _get_aliases(ticker: str) -> list[str]:
    """Return company name aliases for the given ticker (lowercase)."""
    return TICKER_ALIASES.get(ticker.upper(), [])


def _headline_mentions_ticker(ticker: str, headline: str) -> bool:
    """Check if a headline directly mentions the ticker symbol or company name.

    Matches the ticker as a standalone word (not a substring of another word).
    Also matches known company name aliases (e.g., "NVIDIA" for NVDA).
    """
    pattern = rf"\b{re.escape(ticker)}\b"
    if re.search(pattern, headline, re.IGNORECASE):
        return True
    # Check company name aliases
    for alias in _get_aliases(ticker):
        alias_pattern = rf"\b{re.escape(alias)}\b"
        if re.search(alias_pattern, headline, re.IGNORECASE):
            return True
    return False


def _text_mentions_ticker(ticker: str, text: str) -> bool:
    """Check if any text (headline or summary) mentions the ticker or company."""
    if not text:
        return False
    return _headline_mentions_ticker(ticker, text)


def _compute_relevance_score(
    ticker: str, article: dict[str, Any],
) -> int:
    """Compute a relevance score for an article (higher = more relevant).

    Scoring:
      4 = headline mentions target ticker or company name directly
      3 = summary mentions target ticker/company, and ticker is in ``related``
      2 = ticker is the ONLY ticker in ``related`` — article is focused
          but doesn't name the ticker in headline or summary
      0 = excluded (no relevance or headline is about another company)
    """
    ticker_upper = ticker.upper()
    headline = article.get("headline", "")
    summary = article.get("summary", "")
    related_raw = article.get("related", "")

    # Parse related tickers
    related_tickers: list[str] = []
    if related_raw:
        related_tickers = [t.strip().upper() for t in related_raw.split(",")]
    ticker_in_related = ticker_upper in related_tickers

    # Check headline relevance (ticker symbol OR company name)
    headline_match = _headline_mentions_ticker(ticker, headline)

    if not headline_match and not ticker_in_related:
        return 0

    # Headline names our ticker/company — highest confidence
    if headline_match:
        return 4

    # From here: ticker is in related but NOT in headline.
    # Check summary for mention
    if summary and _text_mentions_ticker(ticker, summary):
        return 3

    # Only keep articles where our ticker is the sole symbol in related
    other_count = len(related_tickers) - 1
    if other_count == 0:
        return 2

    return 0


def _extract_article_timestamp(article: dict[str, Any]) -> float:
    """Extract a Unix timestamp from an article for sorting.

    Returns 0.0 if no valid datetime found (oldest possible).
    """
    dt = article.get("datetime")
    if isinstance(dt, (int, float)) and dt > 0:
        return float(dt)
    return 0.0


def filter_relevant_articles(
    ticker: str,
    articles: list[dict[str, Any]],
    max_articles: int = 30,
) -> list[dict[str, Any]]:
    """Filter and rank Finnhub articles by relevance to *ticker*.

    Scoring:
    - **Score 4**: headline mentions ticker symbol or company name
    - **Score 3**: summary mentions ticker/company AND ticker is in related
    - **Score 2**: ticker is the only symbol in ``related`` (focused article)
    - **Excluded**: everything else

    Results are sorted by (relevance DESC, date DESC) and truncated to
    *max_articles*.  The default of 30 ensures broader time coverage before
    LLM analysis; the LLM then further selects the most impactful subset.

    Returns a new list; the original is not mutated.
    """
    scored: list[tuple[int, float, dict[str, Any]]] = []

    for article in articles:
        score = _compute_relevance_score(ticker, article)
        if score > 0:
            ts = _extract_article_timestamp(article)
            scored.append((score, ts, article))

    # Sort by relevance DESC, then by date DESC (most recent first within ties)
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    return [article for _, _, article in scored[:max_articles]]


def compute_sentiment_adjustment(overall_sentiment: float) -> dict[str, Any]:
    """Compute margin-of-safety delta based on overall sentiment score.

    The adjustment is intentionally asymmetric: negative sentiment imposes
    a larger penalty (-8%) than the positive sentiment reward (+5%). This
    follows a conservative investment principle — strong bearish signals
    warrant a higher bar to buy, while bullish signals only modestly lower
    the threshold, avoiding overconfidence.

    Args:
        overall_sentiment: float from -1.0 (very bearish) to +1.0 (very bullish).

    Returns:
        Dict with ``margin_of_safety_pct_delta`` and ``reasoning``.
    """
    if overall_sentiment < -0.5:
        delta = -8
        reasoning = "Very bearish sentiment — raising margin-of-safety bar by 8%"
    elif overall_sentiment < -0.2:
        delta = -4
        reasoning = "Bearish sentiment — raising margin-of-safety bar by 4%"
    elif overall_sentiment > 0.5:
        delta = 5
        reasoning = "Very bullish sentiment — lowering margin-of-safety bar by 5%"
    elif overall_sentiment > 0.2:
        delta = 3
        reasoning = "Bullish sentiment — lowering margin-of-safety bar by 3%"
    else:
        delta = 0
        reasoning = "Neutral sentiment — no margin-of-safety adjustment"

    return {
        "margin_of_safety_pct_delta": delta,
        "reasoning": reasoning,
    }


def compute_overall_sentiment(
    news_score: float | None = None,
    insider_score: float | None = None,
    insider_mspr: float | None = None,
    insider_net_change: int | None = None,
) -> dict[str, Any]:
    """Compute overall sentiment from news and insider data.

    Weights: 60% news + 40% insider (if both available).
    If only one source is available, use it directly.

    Args:
        news_score: Overall news sentiment from LLM (-1.0 to +1.0).
        insider_score: Insider sentiment score from Finnhub (-1.0 to +1.0).
        insider_mspr: Monthly Share Purchase Ratio from Finnhub.
        insider_net_change: Net insider share change.

    Returns:
        Dict with ``overall_sentiment``, ``sentiment_label``,
        ``sentiment_adjustment``, and breakdown details.
    """
    has_news = news_score is not None
    has_insider = insider_score is not None

    if not has_news and not has_insider:
        return {
            "overall_sentiment": 0.0,
            "sentiment_label": "Neutral",
            "news_score": None,
            "insider_score": None,
            "sentiment_adjustment": compute_sentiment_adjustment(0.0),
        }

    if has_news and has_insider:
        # Clamp individual scores before weighting
        ns = max(-1.0, min(1.0, news_score))
        ins = max(-1.0, min(1.0, insider_score))
        overall = 0.6 * ns + 0.4 * ins
    elif has_news:
        overall = max(-1.0, min(1.0, news_score))
    else:
        overall = insider_score

    # Clamp to [-1, 1]
    overall = max(-1.0, min(1.0, overall))

    label = _sentiment_label(overall)
    adjustment = compute_sentiment_adjustment(overall)

    return {
        "overall_sentiment": round(overall, 4),
        "sentiment_label": label,
        "news_score": round(news_score, 4) if news_score is not None else None,
        "insider_score": round(insider_score, 4) if insider_score is not None else None,
        "insider_mspr": insider_mspr,
        "insider_net_change": insider_net_change,
        "sentiment_adjustment": adjustment,
    }


def _sentiment_label(score: float) -> str:
    """Map a numeric sentiment score to a human-readable label."""
    if score < -0.5:
        return "Very Bearish"
    if score < -0.2:
        return "Bearish"
    if score > 0.5:
        return "Very Bullish"
    if score > 0.2:
        return "Bullish"
    return "Neutral"


AUTHORITATIVE_SOURCES: tuple[str, ...] = (
    "reuters",
    "bloomberg",
    "ap",
    "associated press",
    "cnbc",
    "wsj",
    "wall street journal",
    "financial times",
    "ft.com",
    "marketwatch",
    "yahoo",
    "seeking alpha",
    "motley fool",
    "fool.com",
    "investopedia",
    "barron",
    "benzinga",
    "zacks",
    "thestreet",
    "the street",
    "investing.com",
    "business insider",
    "forbes",
    "fortune",
)


def filter_by_authoritative_source(
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter articles to only authoritative financial news sources and SEC filings.

    Articles with ``is_sec_filing=True`` are always retained regardless of source.
    All other articles must have a ``source`` field that substring-matches one of
    the entries in :data:`AUTHORITATIVE_SOURCES`.

    If filtering would remove **all** articles, the original list is returned
    (graceful degradation — some data is better than none).

    Returns a new list; the original is not mutated.
    """
    filtered: list[dict[str, Any]] = []
    for article in articles:
        # SEC filings are always authoritative
        if article.get("is_sec_filing"):
            filtered.append(article)
            continue

        source = article.get("source", "")
        if not source:
            continue

        source_lower = source.lower()
        for auth in AUTHORITATIVE_SOURCES:
            if auth in source_lower:
                filtered.append(article)
                break

    # Graceful degradation: if filter removed everything, keep originals
    if not filtered and articles:
        return list(articles)

    return filtered


def classify_event_type(headline: str) -> str:
    """Classify a news headline into an event type using keyword matching.

    This is a fallback for when LLM classification is unavailable.
    """
    headline_lower = headline.lower()

    keywords: dict[str, list[str]] = {
        "earnings": [
            "earnings", "eps", "revenue", "quarterly", "q1", "q2", "q3", "q4",
            "beats estimate", "misses estimate", "profit", "loss",
        ],
        "guidance": [
            "guidance", "outlook", "forecast", "raises outlook", "lowers outlook",
            "reaffirms", "guidance raised", "guidance lowered",
        ],
        "ma": [
            "acquisition", "acquire", "merger", "buyout", "takeover", "deal",
            "merger agreement", "purchase agreement",
        ],
        "regulatory": [
            "sec", "regulator", "fda", "antitrust", "investigation", "lawsuit",
            "settlement", "fine", "compliance", "probe",
        ],
        "product": [
            "launch", "product", "release", "unveil", "announce", "rollout",
            "partnership", "collaboration", "contract",
        ],
        "executive": [
            "ceo", "cfo", "cto", "resign", "appoint", "executive", "board",
            "leadership", "management change",
        ],
        "macro": [
            "fed", "interest rate", "inflation", "recession", "gdp", "tariff",
            "trade war", "economic", "monetary policy",
        ],
        "analyst": [
            "upgrade", "downgrade", "price target", "analyst", "rating",
            "initiates coverage", "maintains", "reiterates",
        ],
    }

    for event_type, terms in keywords.items():
        for term in terms:
            if term in headline_lower:
                return event_type

    return "other"
