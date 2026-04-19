"""LangGraph state definition for the value analyst workflow."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from backend.models.financial import CompanyFinancials


class AnalysisState(TypedDict):
    # Input
    ticker: str
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
    # Strategy
    strategy_result: dict[str, Any] | None
    # Source tracing
    source_map: dict[str, Any] | None
    # Reasoning chain (append-only via operator.add)
    reasoning_steps: Annotated[list[str], add]
    # Final
    verdict: str | None
