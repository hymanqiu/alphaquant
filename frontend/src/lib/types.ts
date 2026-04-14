export type SSEStatus = "idle" | "connecting" | "connected" | "error" | "complete";

export interface ThinkingMessage {
  node: string;
  content: string;
  timestamp: number;
}

export interface ComponentInstruction {
  component_type: string;
  props: Record<string, unknown>;
  id: string;
}

export interface AgentThinkingEvent {
  event: "agent_thinking";
  node: string;
  content: string;
}

export interface ComponentEvent {
  event: "component";
  component_type: string;
  props: Record<string, unknown>;
}

export interface StepCompleteEvent {
  event: "step_complete";
  node: string;
  summary: string;
}

export interface AnalysisCompleteEvent {
  event: "analysis_complete";
  verdict: string;
  ticker: string;
}

export interface ErrorEvent {
  event: "error";
  message: string;
  recoverable: boolean;
}

export type SSEEventData =
  | AgentThinkingEvent
  | ComponentEvent
  | StepCompleteEvent
  | AnalysisCompleteEvent
  | ErrorEvent;

export interface DCFRecalculateRequest {
  ticker: string;
  growth_rate: number;
  terminal_growth_rate: number;
  discount_rate: number;
}

export interface DCFRecalculateResponse {
  projected_fcf: Array<{
    year: number;
    fcf: number;
    growth_rate: number;
    discount_factor: number;
    present_value: number;
  }>;
  terminal_value: number;
  terminal_pv: number;
  pv_fcf_sum: number;
  enterprise_value: number;
  intrinsic_value_per_share: number | null;
  assumptions: {
    growth_rate: number;
    terminal_growth_rate: number;
    discount_rate: number;
    projection_years: number;
    latest_fcf: number;
  };
  chart_data: Array<{
    year: number;
    fcf: number;
    type: "historical" | "projected";
  }>;
}
