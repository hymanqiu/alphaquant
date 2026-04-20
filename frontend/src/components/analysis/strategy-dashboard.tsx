"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Target, TrendingUp, TrendingDown } from "lucide-react";

interface HistoricalPE {
  year: number;
  pe: number;
}

interface StrategyDashboardProps {
  entity_name: string;
  ticker: string;
  current_price: number;
  intrinsic_value: number;
  margin_of_safety_pct: number;
  suggested_entry_price: number;
  upside_pct: number;
  signal: "Deep Value" | "Undervalued" | "Fair Value" | "Overvalued";
  current_pe: number | null;
  pe_percentile: number | null;
  historical_pe: HistoricalPE[] | null;
}

function signalTheme(signal: string) {
  switch (signal) {
    case "Deep Value":
      return {
        ring: "ring-emerald-500/30",
        bg: "bg-emerald-500/10",
        text: "text-emerald-700 dark:text-emerald-400",
        dot: "bg-emerald-500",
      };
    case "Undervalued":
      return {
        ring: "ring-emerald-500/20",
        bg: "bg-emerald-500/10",
        text: "text-emerald-600 dark:text-emerald-400",
        dot: "bg-emerald-500",
      };
    case "Fair Value":
      return {
        ring: "ring-amber-500/20",
        bg: "bg-amber-500/10",
        text: "text-amber-700 dark:text-amber-400",
        dot: "bg-amber-500",
      };
    case "Overvalued":
      return {
        ring: "ring-red-500/20",
        bg: "bg-red-500/10",
        text: "text-red-700 dark:text-red-400",
        dot: "bg-red-500",
      };
    default:
      return {
        ring: "ring-gray-500/20",
        bg: "bg-gray-500/10",
        text: "text-gray-700 dark:text-gray-400",
        dot: "bg-gray-500",
      };
  }
}

function thermometerPosition(mosPct: number): number {
  return Math.min(100, Math.max(0, ((mosPct + 50) / 100) * 100));
}

function entryRecommendation(
  signal: string,
  currentPrice: number,
  intrinsicValue: number,
  suggestedEntry: number,
  mosPct: number
): string {
  switch (signal) {
    case "Overvalued":
      return `Stock appears overvalued relative to DCF intrinsic value. Consider waiting for a pullback to $${suggestedEntry.toFixed(2)} or below for a 15% margin of safety.`;
    case "Fair Value":
      return `Stock is trading near fair value. A position at $${suggestedEntry.toFixed(2)} would provide a 15% margin of safety.`;
    case "Undervalued":
      return `Stock appears undervalued with ${mosPct.toFixed(1)}% margin of safety. Current price already offers a discount to intrinsic value.`;
    case "Deep Value":
      return `Stock is in deep value territory with ${mosPct.toFixed(1)}% margin of safety. Current price of $${currentPrice.toFixed(2)} is well below intrinsic value of $${intrinsicValue.toFixed(2)}.`;
    default:
      return "";
  }
}

function PriceColumn({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="space-y-1">
      <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
        {label}
      </p>
      <p
        className={cn(
          "font-mono font-semibold tabular-nums leading-none",
          highlight ? "text-[24px] text-[var(--brand)]" : "text-[22px]"
        )}
      >
        ${value.toFixed(2)}
      </p>
    </div>
  );
}

export default function StrategyDashboard({
  entity_name,
  current_price,
  intrinsic_value,
  margin_of_safety_pct,
  suggested_entry_price,
  upside_pct,
  signal,
  current_pe,
  pe_percentile,
  historical_pe,
}: StrategyDashboardProps) {
  const pos = thermometerPosition(margin_of_safety_pct);
  const theme = signalTheme(signal);
  const positive = margin_of_safety_pct >= 0;
  const UpDownIcon = upside_pct >= 0 ? TrendingUp : TrendingDown;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Target className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Entry strategy
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">{entity_name}</p>
            </div>
          </div>
          <div
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 h-6 rounded-full text-[11px] font-medium ring-1",
              theme.bg,
              theme.text,
              theme.ring
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", theme.dot)} />
            {signal}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Price grid */}
        <div className="grid grid-cols-3 gap-4">
          <PriceColumn label="Market price" value={current_price} />
          <PriceColumn
            label="Intrinsic value"
            value={intrinsic_value}
            highlight
          />
          <PriceColumn
            label="Entry (15% MoS)"
            value={suggested_entry_price}
          />
        </div>

        {/* Thermometer */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[10.5px] uppercase tracking-wider text-muted-foreground">
            <span>Valuation thermometer</span>
          </div>
          <div className="relative">
            <div
              className="h-2 rounded-full"
              style={{
                background:
                  "linear-gradient(to right, oklch(0.62 0.2 25) 0%, oklch(0.75 0.14 85) 50%, oklch(0.68 0.17 150) 100%)",
              }}
            />
            {/* Marker */}
            <div
              className="absolute top-1/2 -translate-y-1/2 transition-all duration-300"
              style={{ left: `${pos}%`, transform: "translate(-50%, -50%)" }}
            >
              <div className="h-4 w-4 rounded-full bg-background ring-2 ring-foreground shadow-md" />
            </div>
          </div>
          <div className="flex justify-between text-[10px] text-muted-foreground/70 font-medium">
            <span>Overvalued</span>
            <span>Fair</span>
            <span>Deep value</span>
          </div>
        </div>

        {/* Key metrics tiles */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border bg-muted/30 p-3.5 space-y-1">
            <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
              Margin of safety
            </p>
            <p
              className={cn(
                "font-mono font-semibold text-[22px] tabular-nums leading-none",
                positive
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400"
              )}
            >
              {margin_of_safety_pct > 0 ? "+" : ""}
              {margin_of_safety_pct.toFixed(1)}%
            </p>
          </div>
          <div className="rounded-xl border bg-muted/30 p-3.5 space-y-1">
            <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
              <UpDownIcon className="h-2.5 w-2.5" />
              {upside_pct >= 0 ? "Upside" : "Downside"}
            </p>
            <p
              className={cn(
                "font-mono font-semibold text-[22px] tabular-nums leading-none",
                upside_pct >= 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400"
              )}
            >
              {upside_pct > 0 ? "+" : ""}
              {upside_pct.toFixed(1)}%
            </p>
          </div>
        </div>

        {/* P/E percentile */}
        {current_pe != null && (
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
                P/E valuation percentile
              </p>
              <span className="font-mono font-semibold text-[13px] tabular-nums">
                {current_pe.toFixed(1)}x
              </span>
            </div>
            {pe_percentile != null && (
              <>
                <div className="relative h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className={cn(
                      "absolute inset-y-0 left-0 rounded-full",
                      pe_percentile > 80
                        ? "bg-red-500"
                        : pe_percentile > 50
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                    )}
                    style={{ width: `${pe_percentile}%` }}
                  />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {pe_percentile.toFixed(0)}th percentile over{" "}
                  {historical_pe?.length ?? 0} years
                  {pe_percentile > 80 && (
                    <span className="text-red-600 dark:text-red-400 ml-1.5">
                      · historically expensive
                    </span>
                  )}
                  {pe_percentile < 20 && (
                    <span className="text-emerald-600 dark:text-emerald-400 ml-1.5">
                      · historically cheap
                    </span>
                  )}
                </p>
              </>
            )}
          </div>
        )}

        {/* Recommendation callout */}
        <div
          className={cn(
            "rounded-xl p-3.5 text-[12.5px] leading-relaxed border",
            theme.bg,
            theme.text,
            theme.ring
          )}
        >
          {entryRecommendation(
            signal,
            current_price,
            intrinsic_value,
            suggested_entry_price,
            margin_of_safety_pct
          )}
        </div>
      </CardContent>
    </Card>
  );
}
