"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

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

function signalColor(signal: string): string {
  switch (signal) {
    case "Deep Value":
      return "bg-emerald-600";
    case "Undervalued":
      return "bg-emerald-500";
    case "Fair Value":
      return "bg-amber-500";
    case "Overvalued":
      return "bg-red-500";
    default:
      return "bg-gray-500";
  }
}

function signalTextColor(signal: string): string {
  switch (signal) {
    case "Deep Value":
    case "Undervalued":
      return "text-emerald-600";
    case "Fair Value":
      return "text-amber-600";
    case "Overvalued":
      return "text-red-600";
    default:
      return "text-gray-600";
  }
}

/** Map margin-of-safety % to a 0–100 position on the thermometer (0 = overvalued, 100 = deep value). */
function thermometerPosition(mosPct: number): number {
  // -50% MoS → 0 (far left / overvalued), +50% MoS → 100 (far right / deep value)
  return Math.min(100, Math.max(0, (mosPct + 50) / 100 * 100));
}

function entryRecommendation(
  signal: string,
  currentPrice: number,
  intrinsicValue: number,
  suggestedEntry: number,
  mosPct: number,
): string {
  switch (signal) {
    case "Overvalued":
      return `The stock appears overvalued relative to DCF intrinsic value. Consider waiting for a pullback to $${suggestedEntry.toFixed(2)} or below for a 15% margin of safety.`;
    case "Fair Value":
      return `The stock is trading near fair value. A position at $${suggestedEntry.toFixed(2)} would provide a 15% margin of safety.`;
    case "Undervalued":
      return `The stock appears undervalued with ${mosPct.toFixed(1)}% margin of safety. Current price already offers a discount to intrinsic value.`;
    case "Deep Value":
      return `The stock is in deep value territory with ${mosPct.toFixed(1)}% margin of safety. Current price of $${currentPrice.toFixed(2)} is well below the intrinsic value of $${intrinsicValue.toFixed(2)}.`;
    default:
      return "";
  }
}

export default function StrategyDashboard({
  entity_name,
  ticker,
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

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            {entity_name} - Entry Strategy
          </CardTitle>
          <Badge className={`${signalColor(signal)} text-white`}>
            {signal}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Price comparison grid */}
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold font-mono">
              ${current_price.toFixed(2)}
            </p>
            <p className="text-xs text-muted-foreground">Market Price</p>
          </div>
          <div>
            <p className="text-2xl font-bold font-mono">
              ${intrinsic_value.toFixed(2)}
            </p>
            <p className="text-xs text-muted-foreground">Intrinsic Value</p>
          </div>
          <div>
            <p className="text-2xl font-bold font-mono">
              ${suggested_entry_price.toFixed(2)}
            </p>
            <p className="text-xs text-muted-foreground">Entry (15% MoS)</p>
          </div>
        </div>

        <Separator />

        {/* Valuation thermometer */}
        <div>
          <p className="text-xs text-muted-foreground mb-3">
            Valuation Thermometer
          </p>
          <div className="relative h-4 rounded-full overflow-hidden"
            style={{
              background: "linear-gradient(to right, #ef4444, #f59e0b, #10b981)",
            }}
          >
            {/* Marker */}
            <div
              className="absolute top-0 h-full w-1 bg-white shadow-md border border-gray-400"
              style={{ left: `${pos}%`, transform: "translateX(-50%)" }}
            />
          </div>
          <div className="flex justify-between mt-1 text-[10px] text-muted-foreground">
            <span>Overvalued</span>
            <span>Fair Value</span>
            <span>Deep Value</span>
          </div>
        </div>

        <Separator />

        {/* Key metrics */}
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center p-3 bg-muted rounded-md">
            <p className={`text-xl font-mono font-bold ${margin_of_safety_pct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {margin_of_safety_pct > 0 ? "+" : ""}{margin_of_safety_pct.toFixed(1)}%
            </p>
            <p className="text-xs text-muted-foreground">Margin of Safety</p>
          </div>
          <div className="text-center p-3 bg-muted rounded-md">
            <p className={`text-xl font-mono font-bold ${upside_pct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {upside_pct > 0 ? "+" : ""}{upside_pct.toFixed(1)}%
            </p>
            <p className="text-xs text-muted-foreground">
              {upside_pct >= 0 ? "Upside" : "Downside"}
            </p>
          </div>
        </div>

        {/* P/E Percentile */}
        {current_pe != null && (
          <>
            <Separator />
            <div>
              <p className="text-xs text-muted-foreground mb-2">
                P/E Valuation Percentile
              </p>
              <div className="flex items-center gap-3">
                <span className="text-lg font-mono font-bold shrink-0">
                  {current_pe.toFixed(1)}x
                </span>
                {pe_percentile != null && (
                  <div className="flex-1 space-y-1">
                    <div className="relative h-3 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`absolute top-0 left-0 h-full rounded-full transition-all ${
                          pe_percentile > 80
                            ? "bg-red-500"
                            : pe_percentile > 50
                              ? "bg-amber-500"
                              : "bg-emerald-500"
                        }`}
                        style={{ width: `${pe_percentile}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {pe_percentile.toFixed(0)}th percentile over{" "}
                      {historical_pe?.length ?? 0} years of data
                    </p>
                  </div>
                )}
              </div>
              {pe_percentile != null && pe_percentile > 80 && (
                <p className="text-xs text-red-600 mt-1">
                  P/E is in the historically expensive zone.
                </p>
              )}
              {pe_percentile != null && pe_percentile < 20 && (
                <p className="text-xs text-emerald-600 mt-1">
                  P/E is in the historically cheap zone.
                </p>
              )}
            </div>
          </>
        )}

        <Separator />

        {/* Entry recommendation */}
        <p className={`text-sm ${signalTextColor(signal)}`}>
          {entryRecommendation(
            signal,
            current_price,
            intrinsic_value,
            suggested_entry_price,
            margin_of_safety_pct,
          )}
        </p>
      </CardContent>
    </Card>
  );
}
