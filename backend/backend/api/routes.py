"""FastAPI routes: SSE analysis stream and DCF recalculation."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

_TICKER_RE = re.compile(r"^[A-Za-z]{1,5}$")
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from backend.agents.nodes.dcf_model import compute_dcf
from backend.agents.value_analyst import build_value_analyst_graph
from backend.api.dependencies import cache_financials, get_cached_financials
from backend.services.auth import User
from backend.services.auth.dependencies import get_optional_user
from backend.services.rate_limit import (
    BUCKET_ANALYZE,
    BUCKET_RECALCULATE,
    get_rate_limiter,
)
from backend.services.request_context import bind_client_ip, extract_client_ip

logger = logging.getLogger(__name__)

router = APIRouter()


def _enforce_rate_limit(request: Request, *, bucket: str) -> str:
    """Check the per-IP rate limit. Raises HTTP 429 if over. Returns the IP."""
    client_ip = extract_client_ip(request)
    decision = get_rate_limiter().check_and_record(
        bucket=bucket, client_ip=client_ip,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": (
                    f"Daily limit reached ({decision.limit} per 24h). "
                    f"Try again later."
                ),
                "retry_after_seconds": decision.retry_after_seconds,
                "limit": decision.limit,
            },
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
    return client_ip


@router.get("/api/analyze/{ticker}")
async def analyze_ticker(
    ticker: str,
    request: Request,
    user: User | None = Depends(get_optional_user),
) -> EventSourceResponse:
    """Stream analysis events via SSE as the LangGraph workflow executes.

    Auth is optional: anonymous callers get the free-tier experience
    (Pro nodes emit locked-preview cards). Authenticated users with
    ``tier='pro'`` (or ``'admin'``) get full Pro nodes.
    """
    if not _TICKER_RE.match(ticker):
        raise HTTPException(
            status_code=400,
            detail="Invalid ticker. Must be 1-5 alphabetic characters.",
        )
    client_ip = _enforce_rate_limit(request, bucket=BUCKET_ANALYZE)
    graph = build_value_analyst_graph().compile()
    user_tier = user.tier if user is not None else "free"

    async def event_generator() -> AsyncIterator[ServerSentEvent]:
        initial_state = {
            "ticker": ticker.upper(),
            "user_tier": user_tier,
            "financials": None,
            "fetch_errors": [],
            "health_metrics": None,
            "health_assessment": None,
            "dcf_result": None,
            "relative_valuation_result": None,
            "event_sentiment_result": None,
            "event_impact_result": None,
            "strategy_result": None,
            "qualitative_result": None,
            "risk_yoy_diff_result": None,
            "moat_result": None,
            "investment_thesis_result": None,
            "source_map": None,
            "reasoning_steps": [],
            "verdict": None,
        }

        try:
            # Bind the client IP for the duration of this stream so that
            # downstream LLM calls attribute spend back to the caller.
            with bind_client_ip(client_ip):
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
        except Exception:
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
async def recalculate_dcf(
    request: Request, payload: DCFRecalculateRequest,
) -> dict[str, Any]:
    """Recalculate DCF with user-adjusted assumptions. Uses cached financials."""
    _enforce_rate_limit(request, bucket=BUCKET_RECALCULATE)

    financials = get_cached_financials(payload.ticker)
    if financials is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cached data for {payload.ticker}. Run analysis first.",
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
        growth_rate=payload.growth_rate / 100,
        terminal_growth_rate=payload.terminal_growth_rate / 100,
        discount_rate=payload.discount_rate / 100,
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
