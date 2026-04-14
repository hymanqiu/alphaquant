"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface DCFResultCardProps {
  entity_name: string;
  intrinsic_value_per_share: number | null;
  enterprise_value: number;
  terminal_value: number;
  pv_fcf_sum: number;
  assumptions: {
    growth_rate: number;
    terminal_growth_rate: number;
    discount_rate: number;
    projection_years: number;
    latest_fcf: number;
  };
}

function formatLarge(value: number): string {
  if (Math.abs(value) >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

export default function DCFResultCard({
  entity_name,
  intrinsic_value_per_share,
  enterprise_value,
  terminal_value,
  pv_fcf_sum,
  assumptions,
}: DCFResultCardProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">
          {entity_name} - DCF Valuation
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {intrinsic_value_per_share != null && (
          <div className="text-center py-2">
            <p className="text-3xl font-bold font-mono">
              ${intrinsic_value_per_share.toFixed(2)}
            </p>
            <p className="text-sm text-muted-foreground">
              Intrinsic Value per Share
            </p>
          </div>
        )}

        <Separator />

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Enterprise Value</p>
            <p className="font-mono font-medium">{formatLarge(enterprise_value)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">PV of FCFs</p>
            <p className="font-mono font-medium">{formatLarge(pv_fcf_sum)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Terminal Value</p>
            <p className="font-mono font-medium">{formatLarge(terminal_value)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Latest FCF</p>
            <p className="font-mono font-medium">
              {formatLarge(assumptions.latest_fcf)}
            </p>
          </div>
        </div>

        <Separator />

        <div>
          <p className="text-xs text-muted-foreground mb-2">Assumptions</p>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="text-center p-2 bg-muted rounded-md">
              <p className="font-mono font-medium">
                {assumptions.growth_rate}%
              </p>
              <p className="text-muted-foreground">Growth Rate</p>
            </div>
            <div className="text-center p-2 bg-muted rounded-md">
              <p className="font-mono font-medium">
                {assumptions.discount_rate}%
              </p>
              <p className="text-muted-foreground">Discount Rate</p>
            </div>
            <div className="text-center p-2 bg-muted rounded-md">
              <p className="font-mono font-medium">
                {assumptions.terminal_growth_rate}%
              </p>
              <p className="text-muted-foreground">Terminal Growth</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
