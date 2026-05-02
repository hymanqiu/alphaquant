"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  Loader2,
  ArrowUp,
  Sparkles,
  CircleCheck,
  MessageSquare,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { FollowUpSection } from "@/components/canvas/follow-up-section";
import type { TabId } from "@/components/canvas/tab-groups";
import { cn } from "@/lib/utils";
import type {
  AnalysisStep,
  ComponentInstruction,
  SSEStatus,
  ThinkingMessage,
} from "@/lib/types";

interface ConversationPanelProps {
  ticker: string | null;
  status: SSEStatus;
  steps: AnalysisStep[];
  thinkingMessages: ThinkingMessage[];
  verdict: string | null;
  error: string | null;
  onSubmitTicker: (ticker: string) => void;
  collapsed?: boolean;
  showCloseButton?: boolean;
  onExpand?: () => void;
  onClose?: () => void;
  /** Components on the current canvas — used by Follow-up Q&A as context. */
  components?: ComponentInstruction[];
  /** Switch the canvas to a specific tab (used by Follow-up tab_hint links). */
  onJumpToTab?: (tab: TabId) => void;
}

const STEP_DESCRIPTIONS: Record<string, string> = {
  fetch_sec_data: "Reading SEC EDGAR filings",
  financial_health_scan: "Computing financial ratios",
  dynamic_dcf: "Modeling cash flows",
  strategy: "Analyzing market price & P/E",
  logic_trace: "Verifying sources",
};

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "done":
      return (
        <div className="h-[18px] w-[18px] rounded-full bg-emerald-500/15 ring-1 ring-emerald-500/30 flex items-center justify-center shrink-0">
          <Check className="h-2.5 w-2.5 text-emerald-600" strokeWidth={3} />
        </div>
      );
    case "active":
      return (
        <div className="h-[18px] w-[18px] rounded-full bg-[var(--brand)]/15 ring-1 ring-[var(--brand)]/30 flex items-center justify-center shrink-0">
          <Loader2 className="h-2.5 w-2.5 text-[var(--brand)] animate-spin" />
        </div>
      );
    default:
      return (
        <div className="h-[18px] w-[18px] rounded-full border border-dashed border-muted-foreground/30 shrink-0" />
      );
  }
}

function TaskProgressCard({ steps }: { steps: AnalysisStep[] }) {
  const completedCount = steps.filter((s) => s.status === "done").length;
  const total = steps.length;
  const pct = total > 0 ? (completedCount / total) * 100 : 0;

  return (
    <div className="rounded-xl border bg-card px-4 py-3.5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CircleCheck className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[13px] font-medium">Task progress</span>
        </div>
        <span className="text-[11px] text-muted-foreground font-mono tabular-nums">
          {completedCount} / {total}
        </span>
      </div>
      <div className="h-1 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-[var(--brand)] to-[oklch(0.45_0.2_265)] transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="space-y-2 pt-1">
        {steps.map((step) => (
          <div key={step.node} className="flex items-start gap-2.5">
            <div className="pt-0.5">
              <StepIcon status={step.status} />
            </div>
            <div className="min-w-0 flex-1">
              <p
                className={cn(
                  "text-[13px] leading-[18px]",
                  step.status === "pending"
                    ? "text-muted-foreground/70"
                    : "text-foreground"
                )}
              >
                {step.label}
              </p>
              {step.status === "active" && (
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {STEP_DESCRIPTIONS[step.node] || "Processing..."}
                </p>
              )}
              {step.status === "done" && step.summary && (
                <p className="text-[11px] text-muted-foreground/80 mt-0.5 line-clamp-1">
                  {step.summary}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AssistantAvatar() {
  return (
    <div className="h-6 w-6 rounded-lg bg-gradient-to-br from-[var(--brand)] to-[oklch(0.45_0.2_265)] flex items-center justify-center shrink-0 ring-1 ring-black/5 shadow-sm">
      <Sparkles className="h-3 w-3 text-white" />
    </div>
  );
}

/** 56px rail shown after analysis completes — single button to re-expand the panel. */
const HINT_STORAGE_KEY = "alpha:rail-hint-shown";

function ConversationRail({
  status,
  thinkingMessageCount,
  onExpand,
}: {
  status: SSEStatus;
  thinkingMessageCount: number;
  onExpand?: () => void;
}) {
  // Lazy-init from localStorage so we only ever flip false → true via setTimeout
  // (no synchronous setState inside an effect).
  const [showHint, setShowHint] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return status === "complete" && !window.localStorage.getItem(HINT_STORAGE_KEY);
  });

  useEffect(() => {
    if (!showHint) return;
    const t = window.setTimeout(() => {
      setShowHint(false);
      window.localStorage.setItem(HINT_STORAGE_KEY, "1");
    }, 4500);
    return () => window.clearTimeout(t);
  }, [showHint]);

  return (
    <aside className="w-[56px] shrink-0 border-r bg-surface flex flex-col items-center py-3 gap-3 relative">
      <button
        type="button"
        onClick={onExpand}
        className="h-9 w-9 rounded-xl bg-gradient-to-br from-[var(--brand)] to-[oklch(0.45_0.2_265)] flex items-center justify-center shadow-sm ring-1 ring-black/5 hover:scale-105 transition-transform"
        aria-label="Open conversation panel"
        title="Ask a follow-up"
      >
        <Sparkles className="h-4 w-4 text-white" />
      </button>
      <button
        type="button"
        onClick={onExpand}
        className="h-9 w-9 rounded-xl border bg-card flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
        aria-label="Open conversation panel"
        title="Conversation & progress"
      >
        <MessageSquare className="h-4 w-4" />
      </button>
      {thinkingMessageCount > 0 && (
        <span className="text-[10px] tabular-nums text-muted-foreground font-mono">
          {thinkingMessageCount}
        </span>
      )}

      {showHint && (
        <div className="absolute left-[60px] top-3 z-30 w-56 rounded-lg border bg-card shadow-lg px-3 py-2 animate-in fade-in slide-in-from-left-2 text-[12px] leading-snug">
          <p className="font-medium text-foreground">Conversation tucked away</p>
          <p className="text-muted-foreground mt-0.5">
            Click here anytime to review progress or ask a follow-up.
          </p>
        </div>
      )}
    </aside>
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
  collapsed = false,
  showCloseButton = false,
  onExpand,
  onClose,
  components,
  onJumpToTab,
}: ConversationPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [inputValue, setInputValue] = useState("");

  const isActive = status === "connecting" || status === "connected";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thinkingMessages.length, steps, verdict]);

  if (collapsed) {
    return (
      <ConversationRail
        status={status}
        thinkingMessageCount={thinkingMessages.length}
        onExpand={onExpand}
      />
    );
  }

  const handleSubmit = () => {
    const t = inputValue.trim().toUpperCase();
    if (t) {
      onSubmitTicker(t);
      setInputValue("");
    }
  };

  return (
    <div
      className={cn(
        "w-[420px] shrink-0 border-r flex flex-col bg-surface",
        showCloseButton && "shadow-2xl"
      )}
    >
      {/* Header (only shown in overlay mode where a close affordance is needed) */}
      {showCloseButton && (
        <div className="flex items-center justify-between px-5 h-12 border-b shrink-0">
          <div className="flex items-center gap-2">
            <AssistantAvatar />
            <span className="text-[13px] font-medium">Conversation</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="h-7 w-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
            aria-label="Close conversation panel"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Scrollable conversation */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto scrollbar-thin px-5 pt-6 pb-4 space-y-5"
      >
        {/* User message */}
        {ticker && (
          <div className="flex justify-end">
            <div className="bg-muted/80 text-foreground rounded-2xl rounded-br-md px-3.5 py-2 max-w-[85%]">
              <p className="text-[13px]">
                Analyze <span className="font-mono font-semibold">{ticker}</span>
              </p>
            </div>
          </div>
        )}

        {/* Assistant intro */}
        {ticker && (
          <div className="flex gap-2.5">
            <AssistantAvatar />
            <div className="flex-1 min-w-0 pt-0.5">
              <p className="text-[13px] leading-[20px] text-foreground/90">
                I&apos;ll run a deep valuation analysis on{" "}
                <span className="font-mono font-semibold">{ticker}</span> — financial
                health, DCF modeling, relative valuation, and entry strategy.
              </p>
            </div>
          </div>
        )}

        {/* Task Progress */}
        {(isActive ||
          status === "complete" ||
          steps.some((s) => s.status !== "pending")) && (
          <div className="flex gap-2.5">
            <div className="w-6 shrink-0" />
            <div className="flex-1 min-w-0">
              <TaskProgressCard steps={steps} />
            </div>
          </div>
        )}

        {/* Reasoning trace lives in the Sources tab now (per plan §state machine). */}
        {!isActive && status === "complete" && thinkingMessages.length > 0 && (
          <div className="flex gap-2.5">
            <div className="w-6 shrink-0" />
            <p className="text-[11px] text-muted-foreground italic flex-1">
              Per-node reasoning trace is in the Sources tab on the right.
            </p>
          </div>
        )}

        {/* Loading indicator */}
        {isActive && steps.every((s) => s.status === "pending") && (
          <div className="flex items-center gap-2.5 px-1">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--brand)]" />
            <span className="text-[12px] text-muted-foreground">
              Initializing analysis...
            </span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex gap-2.5">
            <div className="w-6 shrink-0" />
            <div className="flex-1 rounded-xl border border-destructive/20 bg-destructive/5 text-destructive p-3 text-[13px]">
              {error}
            </div>
          </div>
        )}

        {/* Verdict */}
        {verdict && (
          <div className="flex gap-2.5">
            <AssistantAvatar />
            <div className="flex-1 min-w-0 space-y-2">
              <Badge
                variant="secondary"
                className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-0 font-normal text-[11px]"
              >
                <CircleCheck className="h-3 w-3 mr-1" />
                Analysis complete
              </Badge>
              <p className="text-[13px] leading-[20px] text-foreground/90">
                {verdict}
              </p>
            </div>
          </div>
        )}

        {/* Follow-up Q&A — only when analysis is complete and we have context.
            `key={ticker}` forces remount on ticker change so the Q&A thread
            doesn't leak across cached-history switches. */}
        {status === "complete" && ticker && components && components.length > 0 && (
          <FollowUpSection
            key={ticker}
            ticker={ticker}
            components={components}
            onJumpToTab={onJumpToTab}
          />
        )}
      </div>

      {/* Floating pill input */}
      <div className="px-4 pb-4 pt-2 shrink-0">
        <div
          className={cn(
            "relative rounded-2xl border bg-card shadow-float transition-all",
            "focus-within:ring-2 focus-within:ring-[var(--brand)]/20 focus-within:border-[var(--brand)]/40"
          )}
        >
          <input
            type="text"
            placeholder="Analyze another ticker…"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            disabled={isActive}
            className="w-full bg-transparent border-0 outline-none px-4 pt-3 pb-11 text-[13px] placeholder:text-muted-foreground/70 disabled:opacity-50 font-mono tracking-tight"
          />
          <div className="absolute bottom-2 right-2 flex items-center gap-1">
            <button
              onClick={handleSubmit}
              disabled={!inputValue.trim() || isActive}
              className={cn(
                "h-7 w-7 rounded-lg flex items-center justify-center transition-all",
                inputValue.trim() && !isActive
                  ? "bg-foreground text-background hover:bg-foreground/90"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
              aria-label="Submit"
            >
              <ArrowUp className="h-3.5 w-3.5" strokeWidth={2.5} />
            </button>
          </div>
        </div>
        <p className="text-[10.5px] text-muted-foreground/60 text-center mt-2">
          AlphaQuant may produce imprecise estimates. Verify before investing.
        </p>
      </div>
    </div>
  );
}
