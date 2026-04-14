"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
        <CardTitle className="text-base">
          {entity_name} - Valuation Summary
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-center space-y-3">
          <div className="inline-flex items-baseline gap-2">
            <span className="text-4xl font-bold font-mono">
              ${intrinsic_value.toFixed(2)}
            </span>
            <span className="text-sm text-muted-foreground">/ share</span>
          </div>
          <p className="text-sm text-muted-foreground">
            DCF Intrinsic Value Estimate
          </p>
          <p className="text-xs text-muted-foreground">
            Compare with current market price to assess over/undervaluation.
            Adjust assumptions below to see sensitivity.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
