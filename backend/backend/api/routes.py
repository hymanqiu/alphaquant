"""FastAPI routes: SSE analysis stream and DCF recalculation."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from backend.agents.nodes.dcf_model import compute_dcf
from backend.agents.value_analyst import build_value_analyst_graph
from backend.api.dependencies import cache_financials, get_cached_financials

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/analyze/{ticker}")
async def analyze_ticker(ticker: str) -> EventSourceResponse:
    """Stream analysis events via SSE as the LangGraph workflow executes."""
    graph = build_value_analyst_graph().compile()

    async def event_generator() -> AsyncIterator[ServerSentEvent]:
        initial_state = {
            "ticker": ticker.upper(),
            "financials": None,
            "fetch_errors": [],
            "health_metrics": None,
            "health_assessment": None,
            "dcf_result": None,
            "relative_valuation_result": None,
            "strategy_result": None,
            "source_map": None,
            "reasoning_steps": [],
            "verdict": None,
        }

        try:
            async for mode, chunk in graph.astream(
                initial_state, stream_mode=["custom", "values"]
            ):
                if mode == "custom":
                    event_type = chunk.get("event", "message")
                    yield ServerSentEvent(
                        data=json.dumps(chunk),
                        event=event_type,
                    )
                elif mode == "values":
                    # Cache financials from state updates for DCF recalculation
                    financials = chunk.get("financials")
                    if financials is not None:
                        cache_financials(ticker.upper(), financials)
        except Exception as e:
            logger.exception("Analysis failed for %s", ticker)
            yield ServerSentEvent(
                data=json.dumps({
                    "event": "error",
                    "message": "Analysis failed due to an internal error. Please try again.",
                    "recoverable": False,
                }),
                event="error",
            )

    return EventSourceResponse(event_generator())


class DCFRecalculateRequest(BaseModel):
    ticker: str
    growth_rate: float  # percentage, e.g. 15.0 for 15%
    terminal_growth_rate: float = 3.0
    discount_rate: float  # percentage

    model_config = {"extra": "forbid"}

    def model_post_init(self, __context: object) -> None:
        if self.discount_rate <= self.terminal_growth_rate:
            raise ValueError(
                "discount_rate must be greater than terminal_growth_rate"
            )


@router.post("/api/recalculate-dcf")
async def recalculate_dcf(request: DCFRecalculateRequest) -> dict[str, Any]:
    """Recalculate DCF with user-adjusted assumptions. Uses cached financials."""
    financials = get_cached_financials(request.ticker)
    if financials is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cached data for {request.ticker}. Run analysis first.",
        )

    if not financials.free_cash_flow:
        raise HTTPException(
            status_code=400,
            detail="No free cash flow data available for DCF.",
        )

    latest_fcf = financials.free_cash_flow[-1].value
    shares = financials.diluted_shares[-1].value if financials.diluted_shares else None

    result = compute_dcf(
        latest_fcf=latest_fcf,
        growth_rate=request.growth_rate / 100,
        terminal_growth_rate=request.terminal_growth_rate / 100,
        discount_rate=request.discount_rate / 100,
        shares_outstanding=shares,
    )

    # Include historical + projected FCF for chart update
    historical_fcf = [
        {"year": m.calendar_year, "fcf": m.value, "type": "historical"}
        for m in financials.free_cash_flow
    ]
    projected_fcf = [
        {
            "year": financials.free_cash_flow[-1].calendar_year + p["year"],
            "fcf": p["fcf"],
            "type": "projected",
        }
        for p in result["projected_fcf"]
    ]
    result["chart_data"] = historical_fcf + projected_fcf

    return result
