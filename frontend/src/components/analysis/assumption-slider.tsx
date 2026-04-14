"use client";

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";

interface AssumptionSliderProps {
  ticker: string;
  growth_rate: number;
  terminal_growth_rate: number;
  discount_rate: number;
  onRecalculate?: (data: Record<string, unknown>) => void;
}

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono font-medium">{value.toFixed(1)}%</span>
      </div>
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={(vals) => onChange(Array.isArray(vals) ? vals[0] : vals)}
      />
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
        <CardTitle className="text-base">Adjust DCF Assumptions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <SliderRow
          label="FCF Growth Rate"
          value={growth}
          min={0}
          max={40}
          step={0.5}
          onChange={setGrowth}
        />
        <SliderRow
          label="Discount Rate (WACC)"
          value={discount}
          min={4}
          max={20}
          step={0.5}
          onChange={setDiscount}
        />
        <SliderRow
          label="Terminal Growth Rate"
          value={terminal}
          min={0}
          max={5}
          step={0.25}
          onChange={setTerminal}
        />
        <Button
          onClick={handleRecalculate}
          disabled={loading}
          className="w-full"
        >
          {loading ? "Recalculating..." : "Recalculate DCF"}
        </Button>
      </CardContent>
    </Card>
  );
}
