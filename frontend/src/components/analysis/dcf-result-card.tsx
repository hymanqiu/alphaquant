"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Calculator, TrendingUp, Percent, Clock } from "lucide-react";

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

function Stat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="space-y-0.5">
      <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
        {label}
      </p>
      <p className="font-mono font-semibold text-[14px] tabular-nums">{value}</p>
    </div>
  );
}

export default function DCFResultCard({
  entity_name,
  intrinsic_value_per_share,
  enterprise_value,
  terminal_value,
  pv_fcf_sum,
  assumptions,
}: DCFResultCardProps) {
  // Terminal/EV ratio — tells you how "front loaded" the valuation is
  const terminalPct =
    enterprise_value > 0 ? (terminal_value / enterprise_value) * 100 : 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
            <Calculator className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <CardTitle className="text-[14px] font-semibold">
              DCF valuation
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">{entity_name}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {intrinsic_value_per_share != null && (
          <div className="relative rounded-xl p-5 overflow-hidden bg-gradient-to-br from-[var(--brand)]/8 via-transparent to-transparent border border-[var(--brand)]/15">
            <div className="absolute inset-0 bg-grid opacity-30 pointer-events-none" />
            <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1.5">
              Intrinsic value per share
            </p>
            <div className="flex items-baseline gap-2">
              <span className="text-[36px] font-semibold font-mono tracking-tight tabular-nums leading-none">
                ${intrinsic_value_per_share.toFixed(2)}
              </span>
              <span className="text-[12px] text-muted-foreground">/ share</span>
            </div>
          </div>
        )}

        {/* Breakdown */}
        <div className="grid grid-cols-2 gap-4">
          <Stat label="Enterprise value" value={formatLarge(enterprise_value)} />
          <Stat label="PV of FCFs" value={formatLarge(pv_fcf_sum)} />
          <Stat label="Terminal value" value={formatLarge(terminal_value)} />
          <Stat label="Latest FCF" value={formatLarge(assumptions.latest_fcf)} />
        </div>

        {/* Terminal share bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px]">
            <span className="text-muted-foreground">
              Terminal share of EV
            </span>
            <span className="font-mono font-medium tabular-nums">
              {terminalPct.toFixed(0)}%
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-[var(--chart-1)] to-[var(--chart-2)]"
              style={{ width: `${Math.min(terminalPct, 100)}%` }}
            />
          </div>
        </div>

        {/* Assumptions */}
        <div>
          <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider mb-2">
            Assumptions
          </p>
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-lg border bg-muted/30 px-2.5 py-2 space-y-0.5">
              <div className="flex items-center gap-1 text-muted-foreground">
                <TrendingUp className="h-2.5 w-2.5" />
                <span className="text-[10px] uppercase tracking-wider">
                  Growth
                </span>
              </div>
              <p className="font-mono font-semibold text-[13px] tabular-nums">
                {assumptions.growth_rate}%
              </p>
            </div>
            <div className="rounded-lg border bg-muted/30 px-2.5 py-2 space-y-0.5">
              <div className="flex items-center gap-1 text-muted-foreground">
                <Percent className="h-2.5 w-2.5" />
                <span className="text-[10px] uppercase tracking-wider">
                  WACC
                </span>
              </div>
              <p className="font-mono font-semibold text-[13px] tabular-nums">
                {assumptions.discount_rate}%
              </p>
            </div>
            <div className="rounded-lg border bg-muted/30 px-2.5 py-2 space-y-0.5">
              <div className="flex items-center gap-1 text-muted-foreground">
                <Clock className="h-2.5 w-2.5" />
                <span className="text-[10px] uppercase tracking-wider">
                  Terminal
                </span>
              </div>
              <p className="font-mono font-semibold text-[13px] tabular-nums">
                {assumptions.terminal_growth_rate}%
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
