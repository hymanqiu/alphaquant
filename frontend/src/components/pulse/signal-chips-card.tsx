"use client";

import { Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Direction = "bull" | "bear";

interface TechnicalSignal {
  id: string;
  label: string;
  direction: Direction;
  weight: number;
  detail: string | null;
}

interface SignalChipsCardProps {
  ticker: string;
  active_signals: TechnicalSignal[];
}

const CHIP_BG: Record<Direction, string> = {
  bull: "bg-emerald-500/10 ring-emerald-500/30 hover:bg-emerald-500/15 hover:ring-emerald-500/50",
  bear: "bg-rose-500/10 ring-rose-500/30 hover:bg-rose-500/15 hover:ring-rose-500/50",
};

const CHIP_TEXT: Record<Direction, string> = {
  bull: "text-emerald-700 dark:text-emerald-400",
  bear: "text-rose-700 dark:text-rose-400",
};

const CHIP_DOT: Record<Direction, string> = {
  bull: "bg-emerald-500",
  bear: "bg-rose-500",
};

function SignalChip({ signal }: { signal: TechnicalSignal }) {
  // Compose hover hint: detail when present, else just the weight context.
  const tooltip =
    signal.detail ??
    `${signal.direction === "bull" ? "Bullish" : "Bearish"} signal · weight ${signal.weight.toFixed(1)}`;

  return (
    <div
      title={tooltip}
      className={cn(
        "group inline-flex items-center gap-1.5 px-2.5 h-7 rounded-full ring-1 cursor-default transition-all",
        CHIP_BG[signal.direction],
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full shrink-0",
          CHIP_DOT[signal.direction],
        )}
      />
      <span
        className={cn(
          "text-[11.5px] font-medium leading-none",
          CHIP_TEXT[signal.direction],
        )}
      >
        {signal.label}
      </span>
      <span
        className={cn(
          "font-mono text-[10px] tabular-nums leading-none opacity-60",
          CHIP_TEXT[signal.direction],
        )}
      >
        {signal.weight.toFixed(1)}
      </span>
    </div>
  );
}

export default function SignalChipsCard({
  ticker,
  active_signals,
}: SignalChipsCardProps) {
  // Bull first, then bear; within a direction, heaviest weight first.
  const sorted = [...active_signals].sort((a, b) => {
    if (a.direction !== b.direction) return a.direction === "bull" ? -1 : 1;
    return b.weight - a.weight;
  });

  const bullCount = sorted.filter((s) => s.direction === "bull").length;
  const bearCount = sorted.filter((s) => s.direction === "bear").length;

  return (
    <Card>
      <CardHeader className="pb-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Zap className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Active signals · {ticker}
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                Rule-based technical patterns firing right now
              </p>
            </div>
          </div>
          {sorted.length > 0 && (
            <div className="flex items-center gap-3 text-[11px] tabular-nums">
              <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                <span className="font-mono font-semibold">{bullCount}</span>
                <span className="text-muted-foreground">bull</span>
              </span>
              <span className="flex items-center gap-1 text-rose-700 dark:text-rose-400">
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                <span className="font-mono font-semibold">{bearCount}</span>
                <span className="text-muted-foreground">bear</span>
              </span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {sorted.length === 0 ? (
          <div className="rounded-xl border border-dashed bg-muted/20 py-6 text-center text-[12px] text-muted-foreground">
            No signals firing — market is in equilibrium per the rule set.
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {sorted.map((s, i) => (
              <div
                key={s.id}
                className="animate-in fade-in slide-in-from-bottom-1 duration-300"
                style={{ animationDelay: `${i * 40}ms`, animationFillMode: "backwards" }}
              >
                <SignalChip signal={s} />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
