"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Shield } from "lucide-react";
import { cn } from "@/lib/utils";

interface Margin {
  year: number;
  value: number;
}

interface FinancialHealthCardProps {
  entity_name: string;
  assessment: string;
  interest_coverage_ratio: number | null;
  debt_to_equity: number | null;
  roe: number | null;
  revenue_cagr_3yr: number | null;
  revenue_cagr_5yr: number | null;
  margins: {
    gross_margin: Margin[];
    operating_margin: Margin[];
    net_margin: Margin[];
  };
}

function assessmentTheme(assessment: string) {
  switch (assessment) {
    case "Strong":
      return {
        ring: "ring-emerald-500/20",
        bg: "bg-emerald-500/10",
        text: "text-emerald-700 dark:text-emerald-400",
        dot: "bg-emerald-500",
      };
    case "Moderate":
      return {
        ring: "ring-amber-500/20",
        bg: "bg-amber-500/10",
        text: "text-amber-700 dark:text-amber-400",
        dot: "bg-amber-500",
      };
    case "Weak":
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

function Metric({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value: number | null;
  suffix?: string;
}) {
  return (
    <div className="space-y-0.5">
      <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
        {label}
      </p>
      <p className="font-mono text-[15px] font-semibold tabular-nums">
        {value != null ? (
          <>
            {value}
            <span className="text-[11px] text-muted-foreground ml-0.5">
              {suffix}
            </span>
          </>
        ) : (
          <span className="text-muted-foreground/50">—</span>
        )}
      </p>
    </div>
  );
}

function MarginMini({
  label,
  value,
  data,
}: {
  label: string;
  value: number | null;
  data: Margin[];
}) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
          {label}
        </span>
        <span className="font-mono font-semibold text-[13px] tabular-nums">
          {value != null ? `${value}%` : "—"}
        </span>
      </div>
      {/* Sparkline-ish bars */}
      <div className="flex items-end gap-0.5 h-5">
        {data.map((d, i) => (
          <div
            key={i}
            className="flex-1 rounded-sm bg-gradient-to-t from-[var(--chart-1)]/30 to-[var(--chart-1)]"
            style={{
              height: `${Math.max((d.value / max) * 100, 4)}%`,
              opacity: 0.3 + (i / Math.max(data.length - 1, 1)) * 0.7,
            }}
            title={`${d.year}: ${d.value}%`}
          />
        ))}
      </div>
    </div>
  );
}

export default function FinancialHealthCard({
  entity_name,
  assessment,
  interest_coverage_ratio,
  debt_to_equity,
  roe,
  revenue_cagr_3yr,
  revenue_cagr_5yr,
  margins,
}: FinancialHealthCardProps) {
  const theme = assessmentTheme(assessment);
  const latestGross = margins.gross_margin.at(-1)?.value ?? null;
  const latestOp = margins.operating_margin.at(-1)?.value ?? null;
  const latestNet = margins.net_margin.at(-1)?.value ?? null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Shield className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Financial health
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
            {assessment}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Key ratios */}
        <div className="grid grid-cols-5 gap-4">
          <Metric
            label="Int. coverage"
            value={interest_coverage_ratio}
            suffix="x"
          />
          <Metric label="D/E" value={debt_to_equity} suffix="x" />
          <Metric label="ROE" value={roe} suffix="%" />
          <Metric label="Rev 3y" value={revenue_cagr_3yr} suffix="%" />
          <Metric label="Rev 5y" value={revenue_cagr_5yr} suffix="%" />
        </div>

        {/* Divider */}
        <div className="flex items-center gap-2">
          <Activity className="h-3 w-3 text-muted-foreground" />
          <span className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
            Margin trend
          </span>
          <div className="flex-1 h-px bg-border" />
        </div>

        {/* Margins with mini sparkbars */}
        <div className="grid grid-cols-3 gap-5">
          <MarginMini
            label="Gross"
            value={latestGross}
            data={margins.gross_margin}
          />
          <MarginMini
            label="Operating"
            value={latestOp}
            data={margins.operating_margin}
          />
          <MarginMini
            label="Net"
            value={latestNet}
            data={margins.net_margin}
          />
        </div>
      </CardContent>
    </Card>
  );
}
