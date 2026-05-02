"use client";

import { useMemo, useState } from "react";
import { BarChart3, Monitor, CheckCircle2 } from "lucide-react";
import { VerdictHero } from "@/components/canvas/verdict-hero";
import { CanvasTabs } from "@/components/canvas/canvas-tabs";
import { groupByTab, tabFor, type TabId } from "@/components/canvas/tab-groups";
import type {
  AnalysisStep,
  ComponentInstruction,
  SSEStatus,
  ThinkingMessage,
} from "@/lib/types";

interface AnalysisCanvasProps {
  ticker: string | null;
  components: ComponentInstruction[];
  thinkingMessages: ThinkingMessage[];
  steps: AnalysisStep[];
  onRecalculate?: (data: Record<string, unknown>) => void;
  status: SSEStatus;
}

function EmptyCanvas() {
  return (
    <div className="flex-1 flex items-center justify-center text-center p-8">
      <div className="space-y-3 text-muted-foreground">
        <div className="mx-auto h-12 w-12 rounded-2xl bg-muted/50 flex items-center justify-center">
          <BarChart3 className="h-5 w-5 opacity-40" />
        </div>
        <p className="text-[13px]">Analysis results will appear here</p>
      </div>
    </div>
  );
}

export function AnalysisCanvas({
  ticker,
  components,
  thinkingMessages,
  steps,
  onRecalculate,
  status,
}: AnalysisCanvasProps) {
  const isActive = status === "connecting" || status === "connected";
  const groups = useMemo(() => groupByTab(components), [components]);
  const [activeTab, setActiveTab] = useState<TabId>("verdict");

  // Plan §流式 UX: Tab does not auto-switch when new cards arrive — the pulse-dot
  // badge in the tab bar grabs attention while leaving the user in control.
  // For cached views with no Verdict cards, the user lands on Verdict's empty
  // state which surfaces "No data in this section"; they can click a populated
  // tab from the bar.

  if (!ticker) {
    return (
      <div className="flex-1 bg-surface flex flex-col">
        <EmptyCanvas />
      </div>
    );
  }

  return (
    <div className="flex-1 bg-surface flex flex-col overflow-hidden">
      {/* Canvas header */}
      <div className="h-14 px-6 border-b bg-background/60 backdrop-blur-sm flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-lg bg-foreground/5 ring-1 ring-border flex items-center justify-center">
            <Monitor className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono font-bold text-[15px] tracking-tight">{ticker}</span>
            <span className="text-[12px] text-muted-foreground">analysis canvas</span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {isActive && (
            <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-[var(--brand)] opacity-60 animate-ping" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--brand)]" />
              </span>
              Streaming
            </span>
          )}
          {status === "complete" && (
            <span className="flex items-center gap-1.5 text-[11px] text-emerald-600">
              <CheckCircle2 className="h-3 w-3" />
              Complete
            </span>
          )}
        </div>
      </div>

      {/* Hero (sticky) + Tabs (sticky tab bar + scrollable content) */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {components.length === 0 && isActive && (
          <div className="flex-1 flex items-center justify-center">
            <div className="inline-flex items-center gap-2 text-[13px] text-muted-foreground">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-[var(--brand)] opacity-60 animate-ping" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--brand)]" />
              </span>
              Waiting for analysis results…
            </div>
          </div>
        )}

        {components.length === 0 && !isActive && status !== "complete" && <EmptyCanvas />}

        {components.length > 0 && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <VerdictHero
              ticker={ticker}
              components={components}
              status={status}
              onJumpToTab={(t) => setActiveTab(t)}
            />
            <CanvasTabs
              groups={groups}
              status={status}
              thinkingMessages={thinkingMessages}
              steps={steps}
              onRecalculate={onRecalculate}
              activeTab={activeTab}
              onTabChange={setActiveTab}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// Re-export so callers can determine which tab a streaming card belongs to
// (e.g. the conversation panel's "deep-link to Sources" button).
export { tabFor };
