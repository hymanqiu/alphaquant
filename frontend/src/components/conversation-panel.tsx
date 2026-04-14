"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
  Circle,
  Loader2,
  Send,
  Database,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { AnalysisStep, SSEStatus, ThinkingMessage } from "@/lib/types";

interface ConversationPanelProps {
  ticker: string | null;
  status: SSEStatus;
  steps: AnalysisStep[];
  thinkingMessages: ThinkingMessage[];
  verdict: string | null;
  error: string | null;
  onSubmitTicker: (ticker: string) => void;
}

const STEP_DESCRIPTIONS: Record<string, string> = {
  fetch_sec_data: "Using SEC EDGAR",
  financial_health_scan: "Computing ratios",
  dynamic_dcf: "Modeling cash flows",
  strategy: "Analyzing market price",
  logic_trace: "Verifying sources",
};

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "done":
      return (
        <div className="h-5 w-5 rounded-full bg-emerald-500 flex items-center justify-center shrink-0">
          <Check className="h-3 w-3 text-white" />
        </div>
      );
    case "active":
      return (
        <div className="h-5 w-5 rounded-full bg-blue-500 flex items-center justify-center shrink-0">
          <Loader2 className="h-3 w-3 text-white animate-spin" />
        </div>
      );
    default:
      return <Circle className="h-5 w-5 text-muted-foreground/40 shrink-0" />;
  }
}

function TaskProgressCard({ steps }: { steps: AnalysisStep[] }) {
  const completedCount = steps.filter((s) => s.status === "done").length;

  return (
    <Card className="border-border/60">
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Task progress</span>
          <span className="text-xs text-muted-foreground font-mono">
            {completedCount} / {steps.length}
          </span>
        </div>
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-0 space-y-2.5">
        {steps.map((step) => (
          <div key={step.node} className="flex items-start gap-3">
            <StepIcon status={step.status} />
            <div className="min-w-0 flex-1">
              <p
                className={`text-sm leading-5 ${step.status === "pending" ? "text-muted-foreground" : "text-foreground"}`}
              >
                {step.label}
              </p>
              {step.status === "active" && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {STEP_DESCRIPTIONS[step.node] || "Processing..."}
                </p>
              )}
              {step.status === "done" && step.summary && (
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                  {step.summary}
                </p>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function ReasoningAccordion({
  messages,
  isActive,
}: {
  messages: ThinkingMessage[];
  isActive: boolean;
}) {
  const [open, setOpen] = useState(false);

  if (messages.length === 0) return null;

  const latestMessage = messages[messages.length - 1];

  return (
    <div className="rounded-lg border border-border/50 bg-muted/30">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Database className="h-3 w-3" />
        <span className="flex-1 text-left truncate">
          {isActive ? latestMessage.content : `${messages.length} reasoning steps`}
        </span>
        <ChevronDown
          className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-1 max-h-48 overflow-y-auto">
          {messages.map((msg, i) => (
            <p
              key={i}
              className="text-xs text-muted-foreground font-mono leading-relaxed"
            >
              {msg.content}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function ConversationPanel({
  ticker,
  status,
  steps,
  thinkingMessages,
  verdict,
  error,
  onSubmitTicker,
}: ConversationPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [inputValue, setInputValue] = useState("");

  const isActive = status === "connecting" || status === "connected";

  // Group thinking messages by node
  const messagesByNode: Record<string, ThinkingMessage[]> = {};
  for (const msg of thinkingMessages) {
    if (!messagesByNode[msg.node]) messagesByNode[msg.node] = [];
    messagesByNode[msg.node].push(msg);
  }

  // Auto-scroll on new content
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thinkingMessages.length, steps, verdict]);

  const handleSubmit = () => {
    const t = inputValue.trim().toUpperCase();
    if (t) {
      onSubmitTicker(t);
      setInputValue("");
    }
  };

  return (
    <div className="w-[420px] shrink-0 border-r flex flex-col">
      {/* Scrollable conversation */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* User message */}
        <div className="flex justify-end">
          <div className="bg-primary text-primary-foreground rounded-2xl rounded-br-sm px-4 py-2 max-w-[80%]">
            <p className="text-sm">
              Analyze <span className="font-mono font-bold">{ticker}</span>
            </p>
          </div>
        </div>

        {/* Assistant intro */}
        <div className="flex justify-start">
          <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-3 max-w-[90%]">
            <p className="text-sm text-foreground">
              I&apos;ll analyze{" "}
              <span className="font-mono font-semibold">{ticker}</span>&apos;s
              valuation using SEC EDGAR filings. This includes financial health
              assessment, DCF modeling, and entry strategy.
            </p>
          </div>
        </div>

        {/* Task Progress */}
        {(isActive || status === "complete" || steps.some((s) => s.status !== "pending")) && (
          <TaskProgressCard steps={steps} />
        )}

        {/* Reasoning sections per node */}
        {steps
          .filter((s) => s.status === "done" || s.status === "active")
          .map((step) => {
            const msgs = messagesByNode[step.node] || [];
            if (msgs.length === 0) return null;
            return (
              <ReasoningAccordion
                key={step.node}
                messages={msgs}
                isActive={step.status === "active"}
              />
            );
          })}

        {/* Loading indicator */}
        {isActive && steps.every((s) => s.status === "pending") && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Initializing analysis...</span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-destructive/10 text-destructive border border-destructive/20 rounded-lg p-3 text-sm">
            {error}
          </div>
        )}

        {/* Verdict */}
        {verdict && (
          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="p-4 space-y-2">
              <Badge variant="secondary">Analysis Complete</Badge>
              <p className="text-sm leading-relaxed">{verdict}</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Bottom input bar */}
      <div className="border-t px-4 py-3">
        <div className="flex gap-2">
          <Input
            placeholder="Analyze another ticker..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            disabled={isActive}
          />
          <Button
            size="icon"
            onClick={handleSubmit}
            disabled={!inputValue.trim() || isActive}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
