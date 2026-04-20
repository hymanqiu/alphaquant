"use client";

import { useState } from "react";
import { ArrowUp, Sparkles, TrendingUp, LineChart, Target } from "lucide-react";
import { cn } from "@/lib/utils";

const EXAMPLE_TICKERS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"];

const FEATURE_PILLS = [
  { icon: LineChart, label: "DCF valuation" },
  { icon: TrendingUp, label: "Peer comparison" },
  { icon: Target, label: "Entry strategy" },
];

interface EmptyStateProps {
  onSubmit: (ticker: string) => void;
}

export function EmptyState({ onSubmit }: EmptyStateProps) {
  const [input, setInput] = useState("");

  const handleSubmit = () => {
    const t = input.trim().toUpperCase();
    if (t) {
      onSubmit(t);
      setInput("");
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 relative overflow-hidden bg-surface">
      {/* Grid background */}
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />

      <div className="w-full max-w-[560px] space-y-8 text-center relative">
        {/* Brand mark */}
        <div className="flex flex-col items-center gap-4">
          <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-[var(--brand)] to-[oklch(0.45_0.2_265)] flex items-center justify-center shadow-lg ring-1 ring-black/5">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div className="space-y-2">
            <h1 className="text-[28px] font-semibold tracking-tight leading-none">
              What do you want to analyze?
            </h1>
            <p className="text-[14px] text-muted-foreground">
              Enter a ticker symbol for AI-powered deep-value research.
            </p>
          </div>
        </div>

        {/* Floating input */}
        <div className="relative rounded-2xl border bg-card shadow-float focus-within:ring-2 focus-within:ring-[var(--brand)]/20 focus-within:border-[var(--brand)]/40 transition-all">
          <input
            type="text"
            placeholder="e.g. NVDA, AAPL, TSLA"
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            className="w-full bg-transparent border-0 outline-none px-4 pt-4 pb-12 text-[15px] placeholder:text-muted-foreground/60 font-mono tracking-tight"
            autoFocus
          />
          <div className="absolute bottom-2.5 left-3 flex items-center gap-2">
            {FEATURE_PILLS.map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="hidden sm:inline-flex items-center gap-1 text-[11px] text-muted-foreground bg-muted/50 px-2 py-1 rounded-md"
              >
                <Icon className="h-2.5 w-2.5" />
                {label}
              </span>
            ))}
          </div>
          <button
            onClick={handleSubmit}
            disabled={!input.trim()}
            className={cn(
              "absolute bottom-2.5 right-2.5 h-8 w-8 rounded-xl flex items-center justify-center transition-all",
              input.trim()
                ? "bg-foreground text-background hover:bg-foreground/90"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
            aria-label="Start analysis"
          >
            <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
          </button>
        </div>

        {/* Quick start */}
        <div className="space-y-3">
          <p className="text-[11px] text-muted-foreground/70 uppercase tracking-wider font-medium">
            Quick start
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {EXAMPLE_TICKERS.map((t) => (
              <button
                key={t}
                onClick={() => onSubmit(t)}
                className="h-8 px-3 rounded-lg border bg-card hover:bg-muted text-[12px] font-mono font-medium transition-colors hover:border-[var(--brand)]/40"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
