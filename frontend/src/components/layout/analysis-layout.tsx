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
