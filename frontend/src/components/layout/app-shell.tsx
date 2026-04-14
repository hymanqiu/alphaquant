"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { ConversationPanel } from "@/components/conversation-panel";
import { AnalysisCanvas } from "@/components/analysis-canvas";
import { useAnalysisStream } from "@/hooks/use-analysis-stream";
import { useHistory } from "@/context/history-context";
import { API_BASE_URL } from "@/lib/constants";
import type { ComponentInstruction } from "@/lib/types";

interface AppShellProps {
  initialTicker?: string;
}

export function AppShell({ initialTicker }: AppShellProps) {
  const [ticker, setTicker] = useState<string | null>(
    initialTicker?.toUpperCase() ?? null
  );
  const { status, thinkingMessages, components, steps, verdict, error } =
    useAnalysisStream(ticker);
  const [updatedComponents, setUpdatedComponents] = useState<
    ComponentInstruction[]
  >([]);
  const { addEntry, updateEntry } = useHistory();
  const entryIdRef = useRef<string | null>(null);

  const displayComponents =
    updatedComponents.length > 0 ? updatedComponents : components;

  // Track history entry
  useEffect(() => {
    if (ticker && status === "connecting" && !entryIdRef.current) {
      entryIdRef.current = addEntry(ticker);
    }
  }, [ticker, status, addEntry]);

  useEffect(() => {
    if (!entryIdRef.current) return;
    if (status === "complete") {
      updateEntry(entryIdRef.current, { status: "complete", verdict: verdict ?? undefined });
    } else if (status === "error") {
      updateEntry(entryIdRef.current, { status: "error" });
    }
  }, [status, verdict, updateEntry]);

  const handleRecalculate = useCallback(
    async (data: Record<string, unknown>) => {
      try {
        const resp = await fetch(`${API_BASE_URL}/api/recalculate-dcf`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        if (!resp.ok) return;
        const result = await resp.json();

        setUpdatedComponents(
          components.map((comp) => {
            if (comp.component_type === "dcf_result_card") {
              return {
                ...comp,
                props: {
                  ...comp.props,
                  intrinsic_value_per_share: result.intrinsic_value_per_share,
                  enterprise_value: result.enterprise_value,
                  terminal_value: result.terminal_value,
                  pv_fcf_sum: result.pv_fcf_sum,
                  assumptions: result.assumptions,
                },
              };
            }
            if (comp.component_type === "valuation_gauge") {
              return {
                ...comp,
                props: {
                  ...comp.props,
                  intrinsic_value: result.intrinsic_value_per_share,
                },
              };
            }
            if (comp.component_type === "fcf_chart") {
              return {
                ...comp,
                props: { ...comp.props, data: result.chart_data },
              };
            }
            if (
              comp.component_type === "strategy_dashboard" &&
              result.intrinsic_value_per_share != null &&
              result.intrinsic_value_per_share > 0
            ) {
              const newIntrinsic = result.intrinsic_value_per_share as number;
              const currentPrice = comp.props.current_price as number;
              const mosPct =
                ((newIntrinsic - currentPrice) / newIntrinsic) * 100;
              const upside =
                ((newIntrinsic - currentPrice) / currentPrice) * 100;
              const suggestedEntry = newIntrinsic * 0.85;
              let signal: string;
              if (mosPct > 25) signal = "Deep Value";
              else if (mosPct > 10) signal = "Undervalued";
              else if (mosPct > -10) signal = "Fair Value";
              else signal = "Overvalued";
              return {
                ...comp,
                props: {
                  ...comp.props,
                  intrinsic_value: newIntrinsic,
                  margin_of_safety_pct: Math.round(mosPct * 10) / 10,
                  suggested_entry_price:
                    Math.round(suggestedEntry * 100) / 100,
                  upside_pct: Math.round(upside * 10) / 10,
                  signal,
                },
              };
            }
            return comp;
          })
        );
      } catch {
        // Silently fail — original components remain
      }
    },
    [components]
  );

  const handleSubmitTicker = useCallback((t: string) => {
    setTicker(t.toUpperCase());
    setUpdatedComponents([]);
    entryIdRef.current = null;
  }, []);

  const handleNewAnalysis = useCallback(() => {
    setTicker(null);
    setUpdatedComponents([]);
    entryIdRef.current = null;
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        currentTicker={ticker}
        onSelectTicker={handleSubmitTicker}
        onNewAnalysis={handleNewAnalysis}
      />
      <div className="flex flex-1 overflow-hidden">
        <ConversationPanel
          ticker={ticker}
          status={status}
          steps={steps}
          thinkingMessages={thinkingMessages}
          verdict={verdict}
          error={error}
          onSubmitTicker={handleSubmitTicker}
        />
        <AnalysisCanvas
          ticker={ticker}
          components={displayComponents}
          onRecalculate={handleRecalculate}
          status={status}
        />
      </div>
    </div>
  );
}
