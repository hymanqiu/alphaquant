"use client";

import { useCallback, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { SlidersHorizontal, Loader2, RotateCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface AssumptionSliderProps {
  ticker: string;
  growth_rate: number;
  terminal_growth_rate: number;
  discount_rate: number;
  onRecalculate?: (data: Record<string, unknown>) => void;
}

function SliderRow({
  label,
  hint,
  value,
  initial,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  initial: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  const changed = Math.abs(value - initial) > 0.001;
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <p className="text-[12px] font-medium">{label}</p>
          <p className="text-[10.5px] text-muted-foreground">{hint}</p>
        </div>
        <div className="text-right">
          <span className="font-mono font-semibold text-[15px] tabular-nums">
            {value.toFixed(1)}
            <span className="text-[11px] text-muted-foreground ml-0.5">%</span>
          </span>
          {changed && (
            <span className="block text-[10px] text-[var(--brand)] font-mono">
              Δ {value > initial ? "+" : ""}
              {(value - initial).toFixed(1)}
            </span>
          )}
        </div>
      </div>
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={(vals) => onChange(Array.isArray(vals) ? vals[0] : vals)}
      />
      <div className="flex justify-between text-[10px] text-muted-foreground/60 font-mono">
        <span>{min}%</span>
        <span style={{ opacity: 0.5 }}>
          {pct > 10 && pct < 90 ? `${value.toFixed(1)}%` : ""}
        </span>
        <span>{max}%</span>
      </div>
    </div>
  );
}

export default function AssumptionSlider({
  ticker,
  growth_rate: initialGrowth,
  terminal_growth_rate: initialTerminal,
  discount_rate: initialDiscount,
  onRecalculate,
}: AssumptionSliderProps) {
  const [growth, setGrowth] = useState(initialGrowth);
  const [terminal, setTerminal] = useState(initialTerminal);
  const [discount, setDiscount] = useState(initialDiscount);
  const [loading, setLoading] = useState(false);

  const dirty =
    growth !== initialGrowth ||
    terminal !== initialTerminal ||
    discount !== initialDiscount;

  const handleReset = () => {
    setGrowth(initialGrowth);
    setTerminal(initialTerminal);
    setDiscount(initialDiscount);
  };

  const handleRecalculate = useCallback(async () => {
    if (!onRecalculate) return;
    setLoading(true);
    await onRecalculate({
      ticker,
      growth_rate: growth,
      terminal_growth_rate: terminal,
      discount_rate: discount,
    });
    setLoading(false);
  }, [ticker, growth, terminal, discount, onRecalculate]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Adjust assumptions
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                Explore DCF sensitivity in real time
              </p>
            </div>
          </div>
          {dirty && (
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            >
              <RotateCw className="h-3 w-3" />
              Reset
            </button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <SliderRow
          label="FCF growth rate"
          hint="Annual growth over projection horizon"
          value={growth}
          initial={initialGrowth}
          min={0}
          max={40}
          step={0.5}
          onChange={setGrowth}
        />
        <SliderRow
          label="Discount rate (WACC)"
          hint="Required rate of return"
          value={discount}
          initial={initialDiscount}
          min={4}
          max={20}
          step={0.5}
          onChange={setDiscount}
        />
        <SliderRow
          label="Terminal growth rate"
          hint="Perpetual growth after projection"
          value={terminal}
          initial={initialTerminal}
          min={0}
          max={5}
          step={0.25}
          onChange={setTerminal}
        />
        <button
          onClick={handleRecalculate}
          disabled={loading || !dirty}
          className={cn(
            "w-full h-10 rounded-xl text-[13px] font-medium transition-all flex items-center justify-center gap-2",
            dirty && !loading
              ? "bg-foreground text-background hover:bg-foreground/90 active:scale-[0.99]"
              : "bg-muted text-muted-foreground cursor-not-allowed"
          )}
        >
          {loading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Recalculating…
            </>
          ) : (
            "Recalculate DCF"
          )}
        </button>
      </CardContent>
    </Card>
  );
}
