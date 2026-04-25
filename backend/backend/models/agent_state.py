"""LangGraph state definition for the value analyst workflow."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from backend.models.financial import CompanyFinancials


class AnalysisState(TypedDict):
    # Input
    ticker: str
    # Caller's effective tier ("free" / "pro" / "admin"). Pro nodes gate by this.
    user_tier: str
    # SEC data
    financials: CompanyFinancials | None
    fetch_errors: list[str]
    # Financial health
    health_metrics: dict[str, Any] | None
    health_assessment: str | None
    # DCF
    dcf_result: dict[str, Any] | None
    # Relative valuation
    relative_valuation_result: dict[str, Any] | None
    # Event & sentiment
    event_sentiment_result: dict[str, Any] | None
    # Event impact
    event_impact_result: dict[str, Any] | None
    # Strategy
    strategy_result: dict[str, Any] | None
    # Qualitative 10-K MD&A + Risk Factors insights (LLM-extracted, quote-verified)
    qualitative_result: dict[str, Any] | None
    # Year-over-year risk-factor diff between consecutive 10-Ks
    risk_yoy_diff_result: dict[str, Any] | None
    # 7 Powers moat analysis from Item 1 Business
    moat_result: dict[str, Any] | None
    # Investment thesis (LLM-synthesized narrative)
    investment_thesis_result: dict[str, Any] | None
    # Source tracing
    source_map: dict[str, Any] | None
    # Reasoning chain (append-only via operator.add)
    reasoning_steps: Annotated[list[str], add]
    # Final
    verdict: str | None
