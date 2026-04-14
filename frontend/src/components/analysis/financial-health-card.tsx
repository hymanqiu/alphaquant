"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

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

function assessmentColor(assessment: string): string {
  switch (assessment) {
    case "Strong":
      return "bg-emerald-500";
    case "Moderate":
      return "bg-amber-500";
    case "Weak":
      return "bg-red-500";
    default:
      return "bg-gray-500";
  }
}

function MetricRow({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value: number | null;
  suffix?: string;
}) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-mono text-sm font-medium">
        {value != null ? `${value}${suffix}` : "N/A"}
      </span>
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
  const latestGrossMargin = margins.gross_margin.at(-1)?.value ?? null;
  const latestOpMargin = margins.operating_margin.at(-1)?.value ?? null;
  const latestNetMargin = margins.net_margin.at(-1)?.value ?? null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            {entity_name} - Financial Health
          </CardTitle>
          <Badge className={`${assessmentColor(assessment)} text-white`}>
            {assessment}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-x-8 gap-y-2">
          <MetricRow
            label="Interest Coverage"
            value={interest_coverage_ratio}
            suffix="x"
          />
          <MetricRow label="Debt/Equity" value={debt_to_equity} suffix="x" />
          <MetricRow label="ROE" value={roe} suffix="%" />
          <MetricRow
            label="Rev CAGR (3yr)"
            value={revenue_cagr_3yr}
            suffix="%"
          />
          <MetricRow
            label="Rev CAGR (5yr)"
            value={revenue_cagr_5yr}
            suffix="%"
          />
        </div>

        <Separator />

        <div>
          <p className="text-xs text-muted-foreground mb-2">
            Latest Margins
          </p>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <p className="text-lg font-mono font-medium">
                {latestGrossMargin != null ? `${latestGrossMargin}%` : "N/A"}
              </p>
              <p className="text-xs text-muted-foreground">Gross</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-mono font-medium">
                {latestOpMargin != null ? `${latestOpMargin}%` : "N/A"}
              </p>
              <p className="text-xs text-muted-foreground">Operating</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-mono font-medium">
                {latestNetMargin != null ? `${latestNetMargin}%` : "N/A"}
              </p>
              <p className="text-xs text-muted-foreground">Net</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
