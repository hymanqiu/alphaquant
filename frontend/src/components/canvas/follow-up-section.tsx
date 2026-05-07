"use client";

import { useState } from "react";
import { ArrowUp, Loader2, MessageSquare, AlertCircle } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { askFollowUp } from "@/lib/follow-up-api";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { deriveHero } from "@/components/canvas/verdict-hero";
import { TAB_LABELS, type TabId } from "@/components/canvas/tab-groups";
import type {
  ComponentInstruction,
  FollowUpAnswer,
  TabHint,
} from "@/lib/types";

interface FollowUpSectionProps {
  ticker: string;
  components: ComponentInstruction[];
  onJumpToTab?: (tab: TabId) => void;
}

interface FollowUpEntry {
  question: string;
  state:
    | { kind: "loading" }
    | { kind: "ok"; answer: FollowUpAnswer }
    | { kind: "error"; message: string };
}

/**
 * Inline Q&A inside the overlay conversation panel. Free-tier users see a
 * "Pro feature" notice; Pro users get unbounded threading bound to the
 * current analysis context.
 */
export function FollowUpSection({
  ticker,
  components,
  onJumpToTab,
}: FollowUpSectionProps) {
  const { isPro, status } = useAuth();
  const [input, setInput] = useState("");
  const [thread, setThread] = useState<FollowUpEntry[]>([]);

  const isAuthed = status === "authenticated";
  const hasPending = thread.some((e) => e.state.kind === "loading");
  // Block resubmits while any earlier question is still in-flight — avoids the
  // double-Enter race that would index two updates onto the same thread slot.
  const submittable = input.trim().length >= 2 && isPro && !hasPending;

  const handleSubmit = async () => {
    const question = input.trim();
    if (!submittable) return;
    setInput("");
    const idx = thread.length;
    setThread((prev) => [...prev, { question, state: { kind: "loading" } }]);

    try {
      const hero = deriveHero(components);
      const answer = await askFollowUp({
        ticker,
        question,
        hero_snapshot: hero,
        components_snapshot: components.map((c) => ({
          component_type: c.component_type,
          props: c.props,
        })),
      });
      setThread((prev) =>
        prev.map((e, i) =>
          i === idx ? { ...e, state: { kind: "ok", answer } } : e
        )
      );
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.code === "pro_required"
            ? "Follow-up Q&A is a Pro feature."
            : e.message
          : "Network error. Try again.";
      setThread((prev) =>
        prev.map((e, i) =>
          i === idx ? { ...e, state: { kind: "error", message: msg } } : e
        )
      );
    }
  };

  return (
    <div className="border-t pt-3 mt-2 space-y-3">
      <div className="flex items-center gap-2 px-1">
        <MessageSquare className="h-3 w-3 text-[var(--brand)]" />
        <span className="text-[12px] font-medium">Ask follow-up</span>
        {!isPro && isAuthed && (
          <span className="ml-auto text-[10px] text-amber-600 dark:text-amber-400 font-medium">
            Pro only
          </span>
        )}
        {!isAuthed && (
          <span className="ml-auto text-[10px] text-muted-foreground">
            Sign in to ask
          </span>
        )}
      </div>

      {/* Thread */}
      {thread.length > 0 && (
        <div className="space-y-3">
          {thread.map((entry, i) => (
            <FollowUpEntryView
              key={i}
              entry={entry}
              onJumpToTab={onJumpToTab}
            />
          ))}
        </div>
      )}

      {/* Input */}
      <div
        className={cn(
          "relative rounded-2xl border bg-card transition-all",
          submittable && "ring-1 ring-[var(--brand)]/20 border-[var(--brand)]/40"
        )}
      >
        <input
          type="text"
          placeholder={
            isPro
              ? `Ask about ${ticker}…  (e.g. "what if growth is 2pp lower?")`
              : isAuthed
              ? "Upgrade to Pro to ask follow-ups"
              : "Sign in to ask follow-ups"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          disabled={!isPro}
          className="w-full bg-transparent border-0 outline-none px-4 pt-2.5 pb-9 text-[12.5px] placeholder:text-muted-foreground/70 disabled:opacity-50"
        />
        <div className="absolute bottom-1.5 right-1.5 flex items-center gap-1">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!submittable}
            className={cn(
              "h-6 w-6 rounded-md flex items-center justify-center transition-all",
              submittable
                ? "bg-foreground text-background hover:bg-foreground/90"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
            aria-label="Send follow-up question"
          >
            <ArrowUp className="h-3 w-3" strokeWidth={2.5} />
          </button>
        </div>
      </div>
    </div>
  );
}

function FollowUpEntryView({
  entry,
  onJumpToTab,
}: {
  entry: FollowUpEntry;
  onJumpToTab?: (tab: TabId) => void;
}) {
  return (
    <div className="space-y-2">
      {/* User question bubble */}
      <div className="flex justify-end">
        <div className="bg-muted/80 text-foreground rounded-2xl rounded-br-md px-3 py-1.5 max-w-[85%]">
          <p className="text-[12.5px]">{entry.question}</p>
        </div>
      </div>

      {/* Assistant response */}
      {entry.state.kind === "loading" && (
        <div className="flex items-center gap-2 px-1 text-[11.5px] text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin text-[var(--brand)]" />
          Thinking…
        </div>
      )}

      {entry.state.kind === "error" && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/5 text-destructive p-2.5 text-[12px] inline-flex items-start gap-1.5">
          <AlertCircle className="h-3 w-3 mt-0.5 shrink-0" />
          {entry.state.message}
        </div>
      )}

      {entry.state.kind === "ok" && (
        <FollowUpAnswerView answer={entry.state.answer} onJumpToTab={onJumpToTab} />
      )}
    </div>
  );
}

function FollowUpAnswerView({
  answer,
  onJumpToTab,
}: {
  answer: FollowUpAnswer;
  onJumpToTab?: (tab: TabId) => void;
}) {
  const tab = answer.tab_hint as TabHint;
  const validTab: TabId | null =
    tab === "verdict" || tab === "valuation" || tab === "strategy" ||
    tab === "risks" || tab === "sources"
      ? tab
      : null;

  return (
    <div className="rounded-xl border bg-muted/30 p-3 space-y-2">
      <p className="text-[12.5px] leading-relaxed text-foreground/90 whitespace-pre-wrap">
        {answer.answer}
      </p>
      <div className="flex items-center gap-3 text-[10.5px] text-muted-foreground">
        <span>Confidence {Math.round(answer.confidence * 100)}%</span>
        {validTab && onJumpToTab && (
          <button
            type="button"
            onClick={() => onJumpToTab(validTab)}
            className="text-[var(--brand)] hover:underline"
          >
            See {TAB_LABELS[validTab]} tab →
          </button>
        )}
      </div>
    </div>
  );
}
