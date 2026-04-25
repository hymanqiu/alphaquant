"use client";

import { useMemo } from "react";
import { API_BASE_URL } from "@/lib/constants";
import type {
  AnalysisStep,
  ComponentInstruction,
  SSEStatus,
  ThinkingMessage,
} from "@/lib/types";
import { useSSE } from "./use-sse";

const PIPELINE_NODES = [
  { node: "fetch_sec_data", label: "Fetching SEC EDGAR Data" },
  { node: "financial_health_scan", label: "Analyzing Financial Health" },
  { node: "dynamic_dcf", label: "Building DCF Model" },
  { node: "relative_valuation", label: "Comparing Market Multiples" },
  { node: "event_sentiment", label: "Analyzing Event Sentiment" },
  { node: "event_impact", label: "Analyzing Event Impact" },
  { node: "strategy", label: "Generating Entry Strategy" },
  { node: "qualitative_analysis", label: "Extracting 10-K MD&A Insights" },
  { node: "risk_yoy_diff", label: "Comparing 10-K Risks YoY" },
  { node: "moat_analysis", label: "Scoring Economic Moat (7 Powers)" },
  { node: "investment_thesis", label: "Drafting Investment Thesis" },
  { node: "logic_trace", label: "Tracing Data Sources" },
] as const;

export interface AnalysisStream {
  status: SSEStatus;
  thinkingMessages: ThinkingMessage[];
  components: ComponentInstruction[];
  steps: AnalysisStep[];
  verdict: string | null;
  error: string | null;
}

export function useAnalysisStream(ticker: string | null): AnalysisStream {
  const url = ticker ? `${API_BASE_URL}/api/analyze/${ticker}` : "";
  const { status, events, error } = useSSE({
    url,
    enabled: !!ticker,
  });

  const result = useMemo(() => {
    const thinkingMessages: ThinkingMessage[] = [];
    const components: ComponentInstruction[] = [];
    const completedNodes = new Set<string>();
    let activeNode: string | null = null;
    let verdict: string | null = null;
    let componentCounter = 0;
    const stepSummaries: Record<string, string> = {};

    for (const event of events) {
      switch (event.event) {
        case "agent_thinking":
          thinkingMessages.push({
            node: event.node,
            content: event.content,
            timestamp: Date.now(),
          });
          activeNode = event.node;
          break;
        case "component":
          components.push({
            component_type: event.component_type,
            props: event.props,
            id: `comp-${componentCounter++}`,
          });
          break;
        case "step_complete":
          completedNodes.add(event.node);
          stepSummaries[event.node] = event.summary;
          if (activeNode === event.node) activeNode = null;
          break;
        case "analysis_complete":
          verdict = event.verdict;
          break;
      }
    }

    const steps: AnalysisStep[] = PIPELINE_NODES.map(({ node, label }) => ({
      node,
      label,
      status: completedNodes.has(node)
        ? "done"
        : activeNode === node
          ? "active"
          : "pending",
      summary: stepSummaries[node],
    }));

    return { thinkingMessages, components, steps, verdict };
  }, [events]);

  return {
    status,
    ...result,
    error,
  };
}
