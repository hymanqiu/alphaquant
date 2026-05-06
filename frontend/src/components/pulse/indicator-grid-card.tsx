"use client";

import { Gauge } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Tone = "bull" | "bear" | "neutral" | "warning";
type IndicatorId = "rsi" | "macd" | "ma_stack" | "wk52";

interface TechnicalIndicator {
  id: IndicatorId;
  label: string;       // "RSI 14"
  value: string;       // "62" / "+0.42" / "20 > 50 > 200" / "89%"
  sub_label: string;   // "Neutral zone"
  tone: Tone;
}

interface IndicatorGridCardProps {
  ticker: string;
  indicators: TechnicalIndicator[];
}

const VALUE_COLOR: Record<Tone, string> = {
  bull: "text-emerald-700 dark:text-emerald-400",
  bear: "text-rose-700 dark:text-rose-400",
  neutral: "text-foreground",
  warning: "text-amber-700 dark:text-amber-400",
};

const SUB_COLOR: Record<Tone, string> = {
  bull: "text-emerald-700 dark:text-emerald-400",
  bear: "text-rose-700 dark:text-rose-400",
  neutral: "text-muted-foreground",
  warning: "text-amber-700 dark:text-amber-400",
};

const DOT_COLOR: Record<Tone, string> = {
  bull: "bg-emerald-500",
  bear: "bg-rose-500",
  neutral: "bg-zinc-400 dark:bg-zinc-500",
  warning: "bg-amber-500",
};

function IndicatorTile({ indicator }: { indicator: TechnicalIndicator }) {
  // The MA-stack value ("20 > 50 > 200") is wider than the others; shrink to fit.
  const valueClass =
    indicator.value.length > 6 ? "text-[16px]" : "text-[22px]";

  return (
    <div className="relative rounded-xl border bg-muted/30 p-3.5 space-y-1.5 overflow-hidden">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">
        {indicator.label}
      </p>
      <p
        className={cn(
          "font-mono font-semibold tabular-nums leading-none",
          valueClass,
          VALUE_COLOR[indicator.tone],
        )}
      >
        {indicator.value}
      </p>
      <div className="flex items-center gap-1.5 pt-0.5">
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full shrink-0",
            DOT_COLOR[indicator.tone],
          )}
        />
        <span
          className={cn(
            "text-[10.5px] font-medium truncate",
            SUB_COLOR[indicator.tone],
          )}
        >
          {indicator.sub_label}
        </span>
      </div>
    </div>
  );
}

export default function IndicatorGridCard({
  ticker,
  indicators,
}: IndicatorGridCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2.5">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
            <Gauge className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <CardTitle className="text-[14px] font-semibold">
              Indicators · {ticker}
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Momentum and trend snapshot from the last session
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {indicators.map((ind) => (
            <IndicatorTile key={ind.id} indicator={ind} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
