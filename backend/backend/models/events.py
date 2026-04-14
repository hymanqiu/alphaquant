"""SSE event models for the Generative UI protocol."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class AgentThinkingEvent(BaseModel):
    event: Literal["agent_thinking"] = "agent_thinking"
    node: str
    content: str


class ComponentEvent(BaseModel):
    event: Literal["component"] = "component"
    component_type: str
    props: dict[str, Any]


class StepCompleteEvent(BaseModel):
    event: Literal["step_complete"] = "step_complete"
    node: str
    summary: str


class AnalysisCompleteEvent(BaseModel):
    event: Literal["analysis_complete"] = "analysis_complete"
    verdict: str
    ticker: str


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    message: str
    recoverable: bool = True


SSEEvent = (
    AgentThinkingEvent
    | ComponentEvent
    | StepCompleteEvent
    | AnalysisCompleteEvent
    | ErrorEvent
)
