"use client";

import { Suspense } from "react";
import { BarChart3, Monitor, CheckCircle2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { getComponent } from "@/components/component-registry";
import type { ComponentInstruction, SSEStatus } from "@/lib/types";

interface AnalysisCanvasProps {
  ticker: string | null;
  components: ComponentInstruction[];
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
  onRecalculate,
  status,
}: AnalysisCanvasProps) {
  const isActive = status === "connecting" || status === "connected";

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
            <span className="font-mono font-bold text-[15px] tracking-tight">
              {ticker}
            </span>
            <span className="text-[12px] text-muted-foreground">
              analysis canvas
            </span>
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

      {/* Components */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="max-w-5xl mx-auto p-6 space-y-4">
          {components.length === 0 && isActive && (
            <div className="text-center text-muted-foreground py-16">
              <div className="inline-flex items-center gap-2 text-[13px]">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-[var(--brand)] opacity-60 animate-ping" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--brand)]" />
                </span>
                Waiting for analysis results…
              </div>
            </div>
          )}

          {components.length === 0 && !isActive && status !== "complete" && (
            <EmptyCanvas />
          )}

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
                className="animate-in fade-in slide-in-from-bottom-2 duration-300"
              >
                <Suspense
                  fallback={<Skeleton className="h-48 w-full rounded-xl" />}
                >
                  <Component
                    {...instruction.props}
                    onRecalculate={onRecalculate}
                  />
                </Suspense>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
