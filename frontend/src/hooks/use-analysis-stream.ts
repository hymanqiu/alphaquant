"use client";

import { useMemo } from "react";
import { API_BASE_URL } from "@/lib/constants";
import type {
  ComponentInstruction,
  SSEStatus,
  ThinkingMessage,
} from "@/lib/types";
import { useSSE } from "./use-sse";

export interface AnalysisStream {
  status: SSEStatus;
  thinkingMessages: ThinkingMessage[];
  components: ComponentInstruction[];
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
    let verdict: string | null = null;
    let componentCounter = 0;

    for (const event of events) {
      switch (event.event) {
        case "agent_thinking":
          thinkingMessages.push({
            node: event.node,
            content: event.content,
            timestamp: Date.now(),
          });
          break;
        case "component":
          components.push({
            component_type: event.component_type,
            props: event.props,
            id: `comp-${componentCounter++}`,
          });
          break;
        case "analysis_complete":
          verdict = event.verdict;
          break;
      }
    }

    return { thinkingMessages, components, verdict };
  }, [events]);

  return {
    status,
    ...result,
    error,
  };
}
