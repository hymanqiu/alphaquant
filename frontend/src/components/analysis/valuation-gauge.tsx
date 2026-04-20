"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Gauge } from "lucide-react";

interface ValuationGaugeProps {
  intrinsic_value: number;
  entity_name: string;
}

export default function ValuationGauge({
  intrinsic_value,
  entity_name,
}: ValuationGaugeProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
            <Gauge className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <CardTitle className="text-[14px] font-semibold">
              Valuation summary
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">{entity_name}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative rounded-xl overflow-hidden bg-gradient-to-br from-[var(--chart-1)]/10 via-[var(--chart-2)]/5 to-transparent border border-[var(--brand)]/15 p-6">
          <div className="absolute inset-0 bg-grid opacity-25 pointer-events-none" />
          <div className="relative text-center space-y-2">
            <p className="text-[11px] text-muted-foreground uppercase tracking-wider">
              DCF intrinsic value
            </p>
            <div className="inline-flex items-baseline gap-2">
              <span className="text-[48px] font-semibold font-mono tracking-tight leading-none tabular-nums">
                ${intrinsic_value.toFixed(2)}
              </span>
              <span className="text-[13px] text-muted-foreground">/ share</span>
            </div>
            <p className="text-[11px] text-muted-foreground/80 max-w-sm mx-auto pt-1 leading-relaxed">
              Compare against the current market price to assess
              over/undervaluation. Adjust the assumptions below to explore
              sensitivity.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
