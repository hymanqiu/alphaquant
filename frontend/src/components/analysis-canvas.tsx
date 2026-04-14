"use client";

import { Suspense } from "react";
import { BarChart3 } from "lucide-react";
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
        <BarChart3 className="h-12 w-12 mx-auto opacity-30" />
        <p className="text-sm">Analysis results will appear here</p>
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
      <div className="flex-1 bg-muted/20 flex flex-col">
        <EmptyCanvas />
      </div>
    );
  }

  return (
    <div className="flex-1 bg-muted/20 flex flex-col overflow-hidden">
      {/* Canvas header */}
      <div className="px-6 py-3 border-b bg-background/80 flex items-center gap-3">
        <span className="font-mono font-bold text-lg">{ticker}</span>
        <span className="text-sm text-muted-foreground">Analysis</span>
        {isActive && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
            Streaming...
          </span>
        )}
        {status === "complete" && (
          <span className="ml-auto text-xs text-emerald-600">Complete</span>
        )}
      </div>

      {/* Components */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {components.length === 0 && isActive && (
          <div className="text-center text-muted-foreground py-12">
            <p className="text-sm">Waiting for analysis results...</p>
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
                className="p-4 border border-dashed rounded-lg text-muted-foreground text-sm"
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
                fallback={<Skeleton className="h-48 w-full rounded-lg" />}
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
  );
}
