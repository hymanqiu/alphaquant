"use client";

import { Activity, ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type SignalLabel = "Strong Sell" | "Sell" | "Neutral" | "Buy" | "Strong Buy";

interface PulseScoreHeroProps {
  ticker: string;
  entity_name: string;
  composite_score: number;     // 0-100
  signal_label: SignalLabel;
  bull_signal_count: number;
  bear_signal_count: number;
  bullish_pct: number;          // 0.0–1.0
}

type Tone = "bull" | "bear" | "neutral";

function tone(score: number): Tone {
  if (score >= 55) return "bull";
  if (score < 45) return "bear";
  return "neutral";
}

const SCORE_COLOR: Record<Tone, string> = {
  bull: "text-emerald-600 dark:text-emerald-400",
  bear: "text-rose-600 dark:text-rose-400",
  neutral: "text-amber-600 dark:text-amber-400",
};

const BADGE: Record<Tone, string> = {
  bull: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 ring-emerald-500/30",
  bear: "bg-rose-500/10 text-rose-700 dark:text-rose-400 ring-rose-500/30",
  neutral: "bg-amber-500/10 text-amber-700 dark:text-amber-400 ring-amber-500/30",
};

const BADGE_DOT: Record<Tone, string> = {
  bull: "bg-emerald-500",
  bear: "bg-rose-500",
  neutral: "bg-amber-500",
};

const BAR_FILL: Record<Tone, string> = {
  bull: "bg-emerald-500",
  bear: "bg-emerald-500",   // bullish weight bar is emerald regardless
  neutral: "bg-emerald-500",
};

export default function PulseScoreHero({
  ticker,
  entity_name,
  composite_score,
  signal_label,
  bull_signal_count,
  bear_signal_count,
  bullish_pct,
}: PulseScoreHeroProps) {
  const t = tone(composite_score);
  const bullPctInt = Math.round(bullish_pct * 100);

  return (
    <Card>
      <CardHeader className="pb-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Technical pulse
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {entity_name} · {ticker}
              </p>
            </div>
          </div>
          <div
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 h-6 rounded-full text-[11px] font-medium ring-1",
              BADGE[t],
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", BADGE_DOT[t])} />
            {signal_label}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Score row: large number on the left, signal counts on the right */}
        <div className="flex items-end justify-between gap-4">
          <div className="flex items-baseline">
            <span
              className={cn(
                "font-mono font-medium tabular-nums leading-none text-[44px]",
                SCORE_COLOR[t],
              )}
            >
              {composite_score}
            </span>
            <span className="ml-1 font-mono text-[13px] tabular-nums text-muted-foreground">
              /100
            </span>
          </div>
          <div className="flex items-center gap-4 pb-1.5 text-[11px]">
            <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
              <ArrowUpRight className="h-3 w-3" />
              <span className="font-mono font-semibold tabular-nums">
                {bull_signal_count}
              </span>
              <span className="text-muted-foreground">bull</span>
            </span>
            <span className="flex items-center gap-1 text-rose-700 dark:text-rose-400">
              <ArrowDownRight className="h-3 w-3" />
              <span className="font-mono font-semibold tabular-nums">
                {bear_signal_count}
              </span>
              <span className="text-muted-foreground">bear</span>
            </span>
          </div>
        </div>

        {/* Bull / bear weight bar */}
        <div className="space-y-1.5">
          <div className="relative h-1.5 rounded-full bg-rose-500/15 overflow-hidden">
            <div
              className={cn(
                "absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out",
                BAR_FILL[t],
              )}
              style={{ width: `${bullPctInt}%` }}
            />
          </div>
          <p className="text-[10.5px] text-muted-foreground tabular-nums">
            {bullPctInt}% bullish weight
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
