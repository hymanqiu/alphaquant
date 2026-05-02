"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Brain, ChevronDown, Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AnalysisStep, ThinkingMessage } from "@/lib/types";

interface ReasoningTraceProps {
  steps: AnalysisStep[];
  thinkingMessages: ThinkingMessage[];
}

export function ReasoningTrace({ steps, thinkingMessages }: ReasoningTraceProps) {
  const messagesByNode: Record<string, ThinkingMessage[]> = {};
  for (const m of thinkingMessages) {
    if (!messagesByNode[m.node]) messagesByNode[m.node] = [];
    messagesByNode[m.node].push(m);
  }

  const visibleSteps = steps.filter((s) => s.status !== "pending");

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
            <Brain className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <CardTitle className="text-[14px] font-semibold">Reasoning trace</CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Per-node thinking from the analysis pipeline
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {visibleSteps.length === 0 && (
          <p className="text-[11px] text-muted-foreground italic py-2">
            Reasoning will appear here once analysis steps run.
          </p>
        )}
        {visibleSteps.map((step) => (
          <NodeAccordion
            key={step.node}
            step={step}
            messages={messagesByNode[step.node] ?? []}
          />
        ))}
      </CardContent>
    </Card>
  );
}

function NodeAccordion({
  step,
  messages,
}: {
  step: AnalysisStep;
  messages: ThinkingMessage[];
}) {
  const [open, setOpen] = useState(false);
  const isActive = step.status === "active";
  const latest = messages[messages.length - 1];
  const subtitle = isActive
    ? latest?.content ?? "Processing..."
    : step.summary ?? `${messages.length} step${messages.length === 1 ? "" : "s"}`;

  return (
    <div className="rounded-lg border bg-muted/20">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted/40 transition-colors rounded-lg"
      >
        {isActive ? (
          <Loader2 className="h-3 w-3 text-[var(--brand)] animate-spin shrink-0" />
        ) : (
          <Check className="h-3 w-3 text-emerald-600 shrink-0" />
        )}
        <span className="font-medium text-[12.5px] text-foreground/90 shrink-0">
          {step.label}
        </span>
        <span className="flex-1 text-left truncate text-[11.5px] text-muted-foreground">
          {subtitle}
        </span>
        <ChevronDown
          className={cn(
            "h-3 w-3 text-muted-foreground transition-transform shrink-0",
            open && "rotate-180"
          )}
        />
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 space-y-1.5 border-t max-h-64 overflow-y-auto scrollbar-thin">
          {messages.length === 0 ? (
            <p className="text-[11px] text-muted-foreground italic pt-2">
              No reasoning recorded for this node.
            </p>
          ) : (
            messages.map((m, i) => (
              <p
                key={i}
                className="text-[11px] text-muted-foreground font-mono leading-relaxed pt-1.5"
              >
                {m.content}
              </p>
            ))
          )}
        </div>
      )}
    </div>
  );
}
