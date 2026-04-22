"""Unit tests for event_sentiment_math pure computation functions."""

from __future__ import annotations

import pytest

from backend.agents.nodes.event_sentiment_math import (
    TICKER_ALIASES,
    _headline_mentions_ticker,
    classify_event_type,
    compute_overall_sentiment,
    compute_sentiment_adjustment,
    filter_by_authoritative_source,
    filter_relevant_articles,
)
from backend.services.llm_sentiment import _validate_llm_response


# ---------------------------------------------------------------------------
# compute_sentiment_adjustment
# ---------------------------------------------------------------------------


class TestComputeSentimentAdjustment:
    def test_extreme_bearish(self) -> None:
        result = compute_sentiment_adjustment(-0.8)
        assert result["margin_of_safety_pct_delta"] == -8
        assert "bearish" in result["reasoning"].lower()

    def test_mild_bearish(self) -> None:
        result = compute_sentiment_adjustment(-0.35)
        assert result["margin_of_safety_pct_delta"] == -4
        assert "bearish" in result["reasoning"].lower()

    def test_neutral(self) -> None:
        result = compute_sentiment_adjustment(0.0)
        assert result["margin_of_safety_pct_delta"] == 0
        assert "neutral" in result["reasoning"].lower()

    def test_slightly_negative_neutral(self) -> None:
        result = compute_sentiment_adjustment(-0.15)
        assert result["margin_of_safety_pct_delta"] == 0

    def test_slightly_positive_neutral(self) -> None:
        result = compute_sentiment_adjustment(0.15)
        assert result["margin_of_safety_pct_delta"] == 0

    def test_mild_bullish(self) -> None:
        result = compute_sentiment_adjustment(0.35)
        assert result["margin_of_safety_pct_delta"] == 3
        assert "bullish" in result["reasoning"].lower()

    def test_extreme_bullish(self) -> None:
        result = compute_sentiment_adjustment(0.8)
        assert result["margin_of_safety_pct_delta"] == 5
        assert "bullish" in result["reasoning"].lower()

    def test_boundary_values(self) -> None:
        assert compute_sentiment_adjustment(-0.5)["margin_of_safety_pct_delta"] == -4
        assert compute_sentiment_adjustment(-0.2)["margin_of_safety_pct_delta"] == 0
        assert compute_sentiment_adjustment(0.2)["margin_of_safety_pct_delta"] == 0
        assert compute_sentiment_adjustment(0.5)["margin_of_safety_pct_delta"] == 3


# ---------------------------------------------------------------------------
# compute_overall_sentiment
# ---------------------------------------------------------------------------


class TestComputeOverallSentiment:
    def test_no_data_returns_neutral(self) -> None:
        result = compute_overall_sentiment()
        assert result["overall_sentiment"] == 0.0
        assert result["sentiment_label"] == "Neutral"
        assert result["sentiment_adjustment"]["margin_of_safety_pct_delta"] == 0

    def test_news_only(self) -> None:
        result = compute_overall_sentiment(news_score=0.6)
        assert result["overall_sentiment"] == 0.6
        assert result["sentiment_label"] == "Very Bullish"
        assert result["news_score"] == 0.6
        assert result["insider_score"] is None

    def test_insider_only(self) -> None:
        result = compute_overall_sentiment(insider_score=-0.4)
        assert result["overall_sentiment"] == -0.4
        assert result["sentiment_label"] == "Bearish"
        assert result["insider_score"] == -0.4
        assert result["news_score"] is None

    def test_both_sources_weighted(self) -> None:
        result = compute_overall_sentiment(news_score=1.0, insider_score=0.5)
        # 0.6 * 1.0 + 0.4 * 0.5 = 0.8
        assert abs(result["overall_sentiment"] - 0.8) < 0.001
        assert result["sentiment_label"] == "Very Bullish"

    def test_clamps_to_range(self) -> None:
        # Should not exceed 1.0 even with extreme inputs
        result = compute_overall_sentiment(news_score=2.0, insider_score=2.0)
        assert result["overall_sentiment"] <= 1.0

    def test_clamps_individual_extreme_scores(self) -> None:
        # Individual scores are clamped before weighting
        result = compute_overall_sentiment(news_score=100.0, insider_score=-100.0)
        # 0.6 * 1.0 + 0.4 * (-1.0) = 0.2
        assert abs(result["overall_sentiment"] - 0.2) < 0.001

    def test_sentiment_adjustment_propagates(self) -> None:
        result = compute_overall_sentiment(news_score=-0.8)
        assert result["sentiment_adjustment"]["margin_of_safety_pct_delta"] == -8

    def test_insider_mspr_and_net_change_stored(self) -> None:
        result = compute_overall_sentiment(
            news_score=0.3,
            insider_score=0.5,
            insider_mspr=0.45,
            insider_net_change=10000,
        )
        assert result["insider_mspr"] == 0.45
        assert result["insider_net_change"] == 10000


# ---------------------------------------------------------------------------
# classify_event_type
# ---------------------------------------------------------------------------


class TestClassifyEventType:
    @pytest.mark.parametrize(
        "headline,expected",
        [
            ("Company beats Q3 earnings expectations", "earnings"),
            ("EPS misses analyst estimates", "earnings"),
            ("Revenue surges 20% in latest quarter", "earnings"),
            ("CEO announces guidance raise for FY2025", "guidance"),
            ("Company lowers outlook amid uncertainty", "guidance"),
            ("Firm acquires smaller competitor in $5B deal", "ma"),
            ("Merger agreement reached between two firms", "ma"),
            ("FDA approves new drug for treatment", "regulatory"),
            ("SEC launches investigation into practices", "regulatory"),
            ("Company unveils new flagship product", "product"),
            ("Strategic partnership announced", "product"),
            ("CFO resigns amid leadership shakeup", "executive"),
            ("New CEO appointed to board", "executive"),
            ("Fed raises interest rates by 25bps", "macro"),
            ("Inflation data shows economic slowdown", "macro"),
            ("Analyst upgrades stock to Buy", "analyst"),
            ("Price target raised to $200", "analyst"),
            ("Random company update", "other"),
        ],
    )
    def test_classification(self, headline: str, expected: str) -> None:
        assert classify_event_type(headline) == expected

    def test_empty_headline(self) -> None:
        assert classify_event_type("") == "other"

    def test_case_insensitive(self) -> None:
        assert classify_event_type("EARNINGS BEAT ESTIMATES") == "earnings"
        assert classify_event_type("fda Approval News") == "regulatory"


# ---------------------------------------------------------------------------
# _validate_llm_response
# ---------------------------------------------------------------------------


class TestValidateLLMResponse:
    def test_valid_response(self) -> None:
        result = _validate_llm_response({
            "overall_score": 0.5,
            "summary": "Bullish outlook",
            "key_events": ["Earnings beat"],
            "articles": [
                {"sentiment": 0.8, "event_type": "earnings", "confidence": 0.9},
            ],
        })
        assert result is not None
        assert result["overall_score"] == 0.5
        assert len(result["articles"]) == 1

    def test_missing_overall_score_returns_none(self) -> None:
        result = _validate_llm_response({"summary": "test"})
        assert result is None

    def test_non_dict_returns_none(self) -> None:
        result = _validate_llm_response("not a dict")
        assert result is None

    def test_clamps_out_of_range_scores(self) -> None:
        result = _validate_llm_response({
            "overall_score": 5.0,
            "articles": [
                {"sentiment": 10.0, "event_type": "other", "confidence": 2.0},
            ],
        })
        assert result is not None
        assert result["overall_score"] == 1.0
        assert result["articles"][0]["sentiment"] == 1.0
        assert result["articles"][0]["confidence"] == 1.0

    def test_truncates_key_events_to_five(self) -> None:
        result = _validate_llm_response({
            "overall_score": 0.0,
            "key_events": ["a", "b", "c", "d", "e", "f", "g"],
        })
        assert result is not None
        assert len(result["key_events"]) == 5

    def test_missing_articles_defaults_to_empty(self) -> None:
        result = _validate_llm_response({"overall_score": 0.0})
        assert result is not None
        assert result["articles"] == []

    def test_non_numeric_overall_score_returns_none(self) -> None:
        result = _validate_llm_response({"overall_score": "bullish"})
        assert result is None

    def test_non_dict_articles_skipped(self) -> None:
        result = _validate_llm_response({
            "overall_score": 0.0,
            "articles": ["not a dict", {"sentiment": 0.5, "event_type": "other", "confidence": 0.8}],
        })
        assert result is not None
        assert len(result["articles"]) == 1
        assert result["articles"][0]["sentiment"] == 0.5


# ---------------------------------------------------------------------------
# filter_relevant_articles
# ---------------------------------------------------------------------------


class TestFilterRelevantArticles:
    def test_keeps_articles_where_ticker_is_sole_in_related(self) -> None:
        """Articles with ticker as sole symbol in related are kept (score 2)."""
        articles = [
            {"headline": "Apple product news", "related": "AAPL"},
            {"headline": "B", "related": "AAPL,MSFT"},
            {"headline": "C", "related": "GOOG,TSLA"},
        ]
        result = filter_relevant_articles("AAPL", articles)
        # Only the first article has AAPL as sole related ticker (score 2)
        # "B" has AAPL+MSFT without headline match → excluded
        assert len(result) == 1
        assert result[0]["headline"] == "Apple product news"

    def test_keeps_multi_ticker_if_headline_matches(self) -> None:
        """Multi-ticker articles are kept if headline mentions our ticker."""
        articles = [
            {"headline": "AAPL and MSFT team up", "related": "AAPL,MSFT"},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 1

    def test_filters_out_articles_where_ticker_not_mentioned(self) -> None:
        articles = [
            {"headline": "A", "related": "GOOG,TSLA"},
            {"headline": "B", "related": "MSFT"},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 0

    def test_excludes_articles_with_missing_related(self) -> None:
        """Articles with no related field and no headline match are excluded."""
        articles = [
            {"headline": "Some random news"},
            {"headline": "Other news", "related": ""},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 0

    def test_keeps_missing_related_if_headline_matches(self) -> None:
        """Articles with no related field but headline match are kept."""
        articles = [
            {"headline": "AAPL reports record earnings"},
            {"headline": "Random news", "related": ""},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 1
        assert result[0]["headline"] == "AAPL reports record earnings"

    def test_headline_match_ranks_highest(self) -> None:
        """Headline mentions should rank above related-only matches."""
        articles = [
            {"headline": "AAPL launches new product", "related": "AAPL,MSFT"},
            {"headline": "Sector update", "related": "AAPL"},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 2
        # Headline match should come first (score 4)
        assert result[0]["headline"] == "AAPL launches new product"

    def test_sole_related_ticker_ranks_below_headline(self) -> None:
        """Sole related ticker (score 2) ranks below headline match (score 4)."""
        articles = [
            {"headline": "Interesting development", "related": "AAPL"},
            {"headline": "AAPL earnings beat", "related": "AAPL"},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 2
        assert result[0]["headline"] == "AAPL earnings beat"

    def test_excludes_many_related_without_headline_match(self) -> None:
        """Articles with >3 related tickers and no headline match are excluded."""
        articles = [
            {"headline": "Roundup", "related": "AAPL,MSFT,NVDA,GOOG,TSLA,META"},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 0

    def test_excludes_multi_ticker_without_headline_match(self) -> None:
        """Multi-ticker related without headline match → excluded."""
        articles = [
            {"headline": "NFLX surges on subscriber growth", "related": "NFLX,NVDA"},
            {"headline": "AMD launches new chip", "related": "AMD,NVDA"},
        ]
        result = filter_relevant_articles("NVDA", articles)
        # Both have multiple tickers in related, no NVDA in headline → excluded
        assert len(result) == 0

    def test_respects_max_articles_limit(self) -> None:
        articles = [
            {"headline": f"Article {i}", "related": "AAPL"} for i in range(20)
        ]
        result = filter_relevant_articles("AAPL", articles, max_articles=5)
        assert len(result) == 5

    def test_empty_input_returns_empty(self) -> None:
        result = filter_relevant_articles("AAPL", [])
        assert result == []

    def test_case_insensitive_ticker_matching(self) -> None:
        articles = [
            {"headline": "aapl news", "related": "aapl,msft"},
            {"headline": "AAPL update", "related": "AAPL"},
        ]
        result = filter_relevant_articles("aapl", articles)
        # First: headline mentions "aapl" (score 4)
        # Second: AAPL sole in related (score 2)
        assert len(result) == 2

    def test_case_insensitive_headline_matching(self) -> None:
        articles = [
            {"headline": "aapl beats expectations", "related": ""},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 1

    def test_headline_word_boundary_matching(self) -> None:
        """Ticker should match as a whole word, not a substring."""
        articles = [
            # "AAPL" is a whole word — should match
            {"headline": "AAPL reports earnings", "related": ""},
            # "AAPL" embedded in "AAPLet" — should NOT match
            {"headline": "New AAPLet device launched", "related": ""},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 1
        assert result[0]["headline"] == "AAPL reports earnings"

    def test_does_not_mutate_input(self) -> None:
        articles = [
            {"headline": "A", "related": "GOOG"},
            {"headline": "B", "related": "AAPL"},
        ]
        original = list(articles)
        filter_relevant_articles("AAPL", articles)
        assert articles == original

    def test_netflix_filtered_when_analyzing_nvda(self) -> None:
        """Simulates the real NVDA scenario — unrelated articles should be excluded."""
        articles = [
            {"headline": "NVIDIA unveils new GPU architecture", "related": "NVDA"},
            {"headline": "Netflix surges on subscriber growth", "related": "NFLX,DIS,CMCSA,NVDA"},
            {"headline": "Tech stocks rally", "related": "AAPL,MSFT,NVDA,GOOG,TSLA,META,NFLX"},
            {"headline": "NVDA earnings beat expectations", "related": "NVDA,AMD"},
            {"headline": "Netflix announces price increase", "related": "NFLX"},
        ]
        result = filter_relevant_articles("NVDA", articles)
        # "NVIDIA unveils..." → score 4 (company name alias "nvidia" in headline)
        # "NVDA earnings..." → score 4 (headline match)
        # "Netflix surges..." → 0 (headline names Netflix, excluded)
        # "Tech stocks rally" → 0 (too many tickers, no headline match)
        # "Netflix announces..." → 0 (no NVDA at all)
        assert len(result) == 2
        headlines = [a["headline"] for a in result]
        assert "Netflix surges on subscriber growth" not in headlines
        assert "Tech stocks rally" not in headlines
        assert "Netflix announces price increase" not in headlines

    def test_real_world_yahoo_junk_filtered(self) -> None:
        """Articles from user's real report — should be excluded for NVDA."""
        articles = [
            {"headline": "Is Netflix Stock a Buy on the Dip? Here's What History Says", "related": "NFLX,NVDA"},
            {"headline": "Small Caps, Big Possibilities With This Cheap Schwab ETF", "related": "SCHW,NVDA"},
            {"headline": "Prediction Market Giants Kalshi, Polymarket Eye Perpetual Futures Push: Report", "related": "NVDA"},
            {"headline": "American Airlines Has Denied Rumors of a Merger With United", "related": "AAL,UAL,NVDA"},
        ]
        result = filter_relevant_articles("NVDA", articles)
        # First 3: multiple tickers in related, no NVDA in headline → excluded
        # "Prediction Market..." has only NVDA in related (score 2) — borderline
        # kept because Finnhub says it's related. This is a known limitation.
        assert len(result) <= 1

    # --- Company name alias tests ---

    def test_company_name_alias_nvidia(self) -> None:
        """NVIDIA company name should match NVDA ticker."""
        articles = [
            {"headline": "NVIDIA unveils new GPU", "related": "NVDA"},
        ]
        result = filter_relevant_articles("NVDA", articles)
        assert len(result) == 1

    def test_company_name_alias_apple(self) -> None:
        """Apple company name should match AAPL ticker."""
        articles = [
            {"headline": "Apple announces new iPhone", "related": ""},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 1

    def test_company_name_alias_microsoft(self) -> None:
        """Microsoft company name should match MSFT ticker."""
        articles = [
            {"headline": "Microsoft Azure revenue grows", "related": "MSFT"},
        ]
        result = filter_relevant_articles("MSFT", articles)
        assert len(result) == 1

    def test_company_name_alias_case_insensitive(self) -> None:
        """Company name matching should be case-insensitive."""
        articles = [
            {"headline": "nvidia reports earnings", "related": "NVDA"},
        ]
        result = filter_relevant_articles("NVDA", articles)
        assert len(result) == 1

    def test_company_name_word_boundary(self) -> None:
        """Company name should match as whole word, not substring."""
        articles = [
            {"headline": "NVIDIA reports earnings", "related": ""},
            {"headline": "NVIDIAification trend grows", "related": ""},
        ]
        result = filter_relevant_articles("NVDA", articles)
        assert len(result) == 1
        assert result[0]["headline"] == "NVIDIA reports earnings"

    def test_headline_mentions_ticker_function(self) -> None:
        """Test _headline_mentions_ticker directly with aliases."""
        assert _headline_mentions_ticker("NVDA", "NVIDIA unveils GPU")
        assert _headline_mentions_ticker("NVDA", "NVDA hits all time high")
        assert _headline_mentions_ticker("AAPL", "Apple launches new device")
        assert _headline_mentions_ticker("AAPL", "AAPL stock rises")
        assert not _headline_mentions_ticker("NVDA", "Netflix surges")

    # --- Summary field tests ---

    def test_summary_field_match_with_related(self) -> None:
        """Summary mentioning ticker + ticker in related → score 3."""
        articles = [
            {
                "headline": "Tech sector analysis",
                "summary": "NVIDIA leads the semiconductor rally with strong demand",
                "related": "NVDA,AMD",
            },
        ]
        result = filter_relevant_articles("NVDA", articles)
        # headline doesn't mention NVDA, but summary does + related has NVDA
        assert len(result) == 1

    def test_summary_field_no_related_excluded(self) -> None:
        """Summary mention without related field → excluded."""
        articles = [
            {
                "headline": "Tech sector analysis",
                "summary": "NVIDIA leads the semiconductor rally",
                "related": "AMD",
            },
        ]
        result = filter_relevant_articles("NVDA", articles)
        assert len(result) == 0

    def test_summary_field_with_no_summary(self) -> None:
        """Article with no summary field falls back to related-only logic."""
        articles = [
            {"headline": "Sector update", "related": "NVDA"},
        ]
        result = filter_relevant_articles("NVDA", articles)
        # Only NVDA in related (score 2)
        assert len(result) == 1

    # --- Date sorting tests ---

    def test_sorted_by_relevance_then_date(self) -> None:
        """Articles are sorted by relevance DESC, then date DESC."""
        articles = [
            {"headline": "AAPL earnings", "related": "AAPL", "datetime": 1000},
            {"headline": "AAPL new product", "related": "AAPL", "datetime": 3000},
            {"headline": "Sector update", "related": "AAPL", "datetime": 2000},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 3
        # First two: score 4 (headline match), sorted by date DESC
        # Third: score 2 (related only)
        assert result[0]["datetime"] == 3000
        assert result[1]["datetime"] == 1000
        assert result[2]["datetime"] == 2000  # score 2, comes after all score 4

    def test_date_sorting_across_scores(self) -> None:
        """Higher score always beats lower score regardless of date."""
        articles = [
            {"headline": "Old news", "related": "AAPL", "datetime": 1000},
            {"headline": "AAPL breaking news", "related": "", "datetime": 5000},
        ]
        result = filter_relevant_articles("AAPL", articles)
        assert len(result) == 2
        # Score 4 (headline match) > score 2 (related only)
        assert result[0]["headline"] == "AAPL breaking news"

    def test_date_sort_within_same_score(self) -> None:
        """Within same score, newer articles come first."""
        articles = [
            {"headline": "NVDA update", "related": "NVDA", "datetime": 1000},
            {"headline": "NVIDIA launches chip", "related": "NVDA", "datetime": 3000},
        ]
        result = filter_relevant_articles("NVDA", articles)
        assert len(result) == 2
        # Both score 4 (headline/company name match), sorted by date DESC
        assert result[0]["headline"] == "NVIDIA launches chip"
        assert result[1]["headline"] == "NVDA update"


# ---------------------------------------------------------------------------
# filter_by_authoritative_source
# ---------------------------------------------------------------------------


class TestFilterByAuthoritativeSource:
    def test_sec_filings_always_kept(self) -> None:
        articles = [
            {"headline": "SEC 8-K Filing", "is_sec_filing": True, "source": "SEC EDGAR"},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 1

    def test_reuters_bloomberg_kept(self) -> None:
        articles = [
            {"headline": "A", "source": "Reuters"},
            {"headline": "B", "source": "Bloomberg"},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 2

    def test_wsj_kept(self) -> None:
        articles = [
            {"headline": "A", "source": "Wall Street Journal"},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 1

    def test_unknown_source_falls_back_to_all(self) -> None:
        """When all articles are non-authoritative, keep them all (degradation)."""
        articles = [
            {"headline": "A", "source": "Random Blog"},
            {"headline": "B", "source": "Unknown Source"},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 2  # fallback keeps all

    def test_no_source_falls_back_to_all(self) -> None:
        """When all articles have no source, keep them all (degradation)."""
        articles = [
            {"headline": "A"},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 1  # fallback keeps all

    def test_empty_source_falls_back_to_all(self) -> None:
        """When all articles have empty source, keep them all (degradation)."""
        articles = [
            {"headline": "A", "source": ""},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 1  # fallback keeps all

    def test_mixed_keeps_authoritative_only(self) -> None:
        """When some articles are authoritative, only those are kept."""
        articles = [
            {"headline": "Good", "source": "Reuters"},
            {"headline": "Bad", "source": "Some Blog"},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 1
        assert result[0]["headline"] == "Good"

    def test_empty_input_returns_empty(self) -> None:
        assert filter_by_authoritative_source([]) == []

    def test_does_not_mutate_input(self) -> None:
        articles = [
            {"headline": "A", "source": "Random"},
            {"headline": "B", "source": "Reuters"},
        ]
        original = list(articles)
        filter_by_authoritative_source(articles)
        assert articles == original

    def test_substring_matching(self) -> None:
        articles = [
            {"headline": "A", "source": "Reuters Editorial"},
            {"headline": "B", "source": "Yahoo Finance News"},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 2

    def test_mixed_sources_filters_correctly(self) -> None:
        articles = [
            {"headline": "SEC", "is_sec_filing": True, "source": "SEC EDGAR"},
            {"headline": "Good", "source": "CNBC"},
            {"headline": "Bad", "source": "Some Blog"},
            {"headline": "Good2", "source": "MarketWatch"},
        ]
        result = filter_by_authoritative_source(articles)
        assert len(result) == 3
