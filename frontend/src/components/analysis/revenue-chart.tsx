"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  LabelList,
  type TooltipProps,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp } from "lucide-react";
import {
  GlassTooltip,
  axisTickStyle,
  formatCompactDollar,
  gridProps,
} from "./chart-primitives";

interface RevenueChartProps {
  entity_name: string;
  data: Array<{ year: number; revenue: number }>;
}

function CustomTooltip({
  active,
  payload,
  label,
}: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value as number;
  return (
    <GlassTooltip
      title={`FY ${label}`}
      rows={[
        {
          label: "Revenue",
          value: formatCompactDollar(value),
          color: "var(--chart-1)",
        },
      ]}
    />
  );
}

export default function RevenueChart({
  entity_name,
  data,
}: RevenueChartProps) {
  // Compute CAGR to show alongside the title
  const first = data[0];
  const last = data[data.length - 1];
  const years = data.length > 1 ? last.year - first.year : 0;
  const cagr =
    first && last && first.revenue > 0 && years > 0
      ? (Math.pow(last.revenue / first.revenue, 1 / years) - 1) * 100
      : null;
  const latest = last?.revenue ?? 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-0.5 min-w-0">
            <CardTitle className="text-[13px] font-medium text-muted-foreground">
              Revenue history
            </CardTitle>
            <div className="flex items-baseline gap-2.5">
              <span className="text-2xl font-semibold font-mono tracking-tight">
                {formatCompactDollar(latest)}
              </span>
              {cagr != null && (
                <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 bg-emerald-500/10 px-1.5 py-0.5 rounded-md">
                  <TrendingUp className="h-2.5 w-2.5" />
                  {cagr >= 0 ? "+" : ""}
                  {cagr.toFixed(1)}% CAGR
                </span>
              )}
            </div>
            <p className="text-[11px] text-muted-foreground/70 mt-0.5">
              {entity_name} · {data.length}y
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={data}
            margin={{ top: 20, right: 8, left: 0, bottom: 4 }}
          >
            <defs>
              <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={1} />
                <stop
                  offset="100%"
                  stopColor="var(--chart-1)"
                  stopOpacity={0.35}
                />
              </linearGradient>
            </defs>
            <CartesianGrid {...gridProps} />
            <XAxis
              dataKey="year"
              tick={axisTickStyle}
              axisLine={false}
              tickLine={false}
              dy={6}
            />
            <YAxis
              tickFormatter={formatCompactDollar}
              tick={axisTickStyle}
              axisLine={false}
              tickLine={false}
              width={56}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: "var(--muted)", opacity: 0.4 }}
            />
            <Bar
              dataKey="revenue"
              fill="url(#revenueFill)"
              radius={[6, 6, 2, 2]}
              maxBarSize={52}
            >
              <LabelList
                dataKey="revenue"
                position="top"
                formatter={(v: number) => formatCompactDollar(v)}
                style={{
                  fill: "var(--foreground)",
                  fontSize: 10,
                  fontFamily:
                    "var(--font-mono, ui-monospace, monospace)",
                  fontWeight: 600,
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
