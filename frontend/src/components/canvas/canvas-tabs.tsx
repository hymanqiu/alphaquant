"use client";

import { Suspense, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getComponent } from "@/components/component-registry";
import { ReasoningTrace } from "@/components/canvas/reasoning-trace";
import {
  TAB_LABELS,
  TAB_ORDER,
  type TabGroups,
  type TabId,
} from "@/components/canvas/tab-groups";
import type {
  AnalysisStep,
  ComponentInstruction,
  SSEStatus,
  ThinkingMessage,
} from "@/lib/types";

interface CanvasTabsProps {
  groups: TabGroups;
  status: SSEStatus;
  thinkingMessages: ThinkingMessage[];
  steps: AnalysisStep[];
  onRecalculate?: (data: Record<string, unknown>) => void;
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

/** Highest-severity risk count, for the Risks tab badge tone. */
function riskSeverityHighlight(components: ComponentInstruction[]): number {
  for (const c of components) {
    if (c.component_type !== "risk_factors_card") continue;
    const top = ((c.props as Record<string, unknown>).top_risks ?? []) as Array<{
      severity?: string;
    }>;
    return top.filter((r) => r.severity === "high").length;
  }
  return 0;
}

export function CanvasTabs({
  groups,
  status,
  thinkingMessages,
  steps,
  onRecalculate,
  activeTab,
  onTabChange,
}: CanvasTabsProps) {
  const isStreaming = status === "connecting" || status === "connected";

  // Per-tab "seen count" snapshot. Lazy-init captures all current counts at mount,
  // so cards already present when CanvasTabs first renders count as "seen" — the
  // pulse-dot only fires for cards that *arrive after* mount (live streams) and
  // for tabs not currently active. Cached views show no dots since nothing arrives.
  const [seenCounts, setSeenCounts] = useState<Record<TabId, number>>(() => ({
    verdict: groups.verdict.length,
    valuation: groups.valuation.length,
    strategy: groups.strategy.length,
    risks: groups.risks.length,
    sources: groups.sources.length,
  }));

  const handleTabChange = (next: string) => {
    const t = next as TabId;
    onTabChange(t);
    setSeenCounts((prev) => ({ ...prev, [t]: groups[t].length }));
  };

  const highSeverityCount = riskSeverityHighlight(groups.risks);

  return (
    <Tabs
      value={activeTab}
      onValueChange={handleTabChange}
      className="flex flex-col flex-1 min-h-0"
    >
      <div className="shrink-0 bg-background/85 backdrop-blur-md border-b">
        <div className="max-w-5xl mx-auto px-6 py-2 overflow-x-auto scrollbar-thin">
          <TabsList variant="line" className="gap-1">
            {TAB_ORDER.map((id) => {
              const count = groups[id].length;
              const seen = seenCounts[id];
              const hasNew = count > seen && id !== activeTab;
              const isRisksHot = id === "risks" && highSeverityCount > 0;

              return (
                <TabsTrigger
                  key={id}
                  value={id}
                  className={cn(
                    "relative px-3 text-[12.5px]",
                    isRisksHot && "data-active:text-red-600 dark:data-active:text-red-400"
                  )}
                >
                  <span className="flex items-center gap-1.5">
                    <span>{TAB_LABELS[id]}</span>
                    {count > 0 && (
                      <span
                        className={cn(
                          "tabular-nums text-[10.5px] px-1.5 h-4 rounded-full inline-flex items-center justify-center min-w-[16px]",
                          isRisksHot && id === "risks"
                            ? "bg-red-500/15 text-red-600 dark:text-red-400"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {count}
                      </span>
                    )}
                    {hasNew && (
                      <span className="relative flex h-1.5 w-1.5">
                        <span className="absolute inline-flex h-full w-full rounded-full bg-[var(--brand)] opacity-60 animate-ping" />
                        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--brand)]" />
                      </span>
                    )}
                  </span>
                </TabsTrigger>
              );
            })}
          </TabsList>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="max-w-5xl mx-auto px-6 py-5 space-y-4">
          {TAB_ORDER.map((id) => (
            <TabsContent key={id} value={id} className="space-y-4 mt-0 data-[state=inactive]:hidden">
              <TabSection
                id={id}
                components={groups[id]}
                isStreaming={isStreaming}
                onRecalculate={onRecalculate}
                thinkingMessages={thinkingMessages}
                steps={steps}
              />
            </TabsContent>
          ))}
        </div>
      </div>
    </Tabs>
  );
}

function TabSection({
  id,
  components,
  isStreaming,
  onRecalculate,
  thinkingMessages,
  steps,
}: {
  id: TabId;
  components: ComponentInstruction[];
  isStreaming: boolean;
  onRecalculate?: (data: Record<string, unknown>) => void;
  thinkingMessages: ThinkingMessage[];
  steps: AnalysisStep[];
}) {
  if (components.length === 0 && id !== "sources") {
    if (isStreaming) {
      return (
        <div className="text-center text-muted-foreground py-12">
          <div className="inline-flex items-center gap-2 text-[12.5px]">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full rounded-full bg-[var(--brand)] opacity-60 animate-ping" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--brand)]" />
            </span>
            Analyzing — cards will appear here as they stream in
          </div>
        </div>
      );
    }
    return (
      <div className="text-center text-muted-foreground py-12 text-[12.5px]">
        No data in this section.
      </div>
    );
  }

  return (
    <>
      {components.map((instruction) => {
        const Component = getComponent(instruction.component_type);
        if (!Component) {
          return (
            <div
              key={instruction.id}
              className="p-4 border border-dashed rounded-xl text-muted-foreground text-sm"
            >
              Unknown component: {instruction.component_type}
            </div>
          );
        }
        return (
          <div
            key={instruction.id}
            className="rounded-xl animate-in fade-in slide-in-from-bottom-2 duration-300"
          >
            <Suspense fallback={<Skeleton className="h-48 w-full rounded-xl" />}>
              <Component {...instruction.props} onRecalculate={onRecalculate} />
            </Suspense>
          </div>
        );
      })}
      {/* Sources tab gets the reasoning trace as a final card. */}
      {id === "sources" && (steps.length > 0 || thinkingMessages.length > 0) && (
        <ReasoningTrace steps={steps} thinkingMessages={thinkingMessages} />
      )}
    </>
  );
}
