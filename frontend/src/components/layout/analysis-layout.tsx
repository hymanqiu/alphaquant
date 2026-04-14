"use client";

import { useCallback, useState } from "react";
import { AgentTerminal } from "@/components/agent-terminal";
import { Visualizer } from "@/components/visualizer";
import { Badge } from "@/components/ui/badge";
import { useAnalysisStream } from "@/hooks/use-analysis-stream";
import { API_BASE_URL } from "@/lib/constants";
import type { ComponentInstruction } from "@/lib/types";

interface AnalysisLayoutProps {
  ticker: string;
}

export function AnalysisLayout({ ticker }: AnalysisLayoutProps) {
  const { status, thinkingMessages, components, verdict, error } =
    useAnalysisStream(ticker);
  const [updatedComponents, setUpdatedComponents] = useState<
    ComponentInstruction[]
  >([]);

  const displayComponents =
    updatedComponents.length > 0 ? updatedComponents : components;

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

        // Update the DCF-related components in-place
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
                props: {
                  ...comp.props,
                  data: result.chart_data,
                },
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
                  suggested_entry_price: Math.round(suggestedEntry * 100) / 100,
                  upside_pct: Math.round(upside * 10) / 10,
                  signal,
                },
              };
            }
            return comp;
          })
        );
      } catch {
        // Silently fail - the original components remain
      }
    },
    [components]
  );

  const isActive = status === "connecting" || status === "connected";

  return (
    <div className="flex-1 flex flex-col lg:flex-row gap-4 p-4 overflow-hidden">
      {/* Left: Agent Terminal */}
      <div className="lg:w-2/5 h-64 lg:h-auto">
        <AgentTerminal messages={thinkingMessages} isActive={isActive} />
      </div>

      {/* Right: Visualizer */}
      <div className="lg:w-3/5 overflow-y-auto space-y-4">
        {error && (
          <div className="bg-destructive/10 text-destructive border border-destructive/20 rounded-lg p-4 text-sm">
            {error}
          </div>
        )}

        <Visualizer
          components={displayComponents}
          onRecalculate={handleRecalculate}
        />

        {verdict && (
          <div className="bg-primary/5 border rounded-lg p-4 space-y-2">
            <Badge variant="secondary">Analysis Complete</Badge>
            <p className="text-sm">{verdict}</p>
          </div>
        )}

        {isActive && components.length === 0 && (
          <div className="text-center text-muted-foreground py-12">
            Waiting for analysis results...
          </div>
        )}
      </div>
    </div>
  );
}
