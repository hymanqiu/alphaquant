"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
  type TooltipProps,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  GlassTooltip,
  axisTickStyle,
  formatCompactDollar,
  gridProps,
} from "./chart-primitives";

interface FCFChartProps {
  entity_name: string;
  data: Array<{ year: number; fcf: number; type: "historical" | "projected" }>;
}

function CustomTooltip({
  active,
  payload,
  label,
}: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as {
    fcf: number;
    type: "historical" | "projected";
  };
  const isProjected = row.type === "projected";
  return (
    <GlassTooltip
      title={`FY ${label}`}
      rows={[
        {
          label: isProjected ? "Projected FCF" : "Free cash flow",
          value: formatCompactDollar(row.fcf),
          color: isProjected ? "var(--chart-3)" : "var(--chart-1)",
        },
      ]}
    />
  );
}

export default function FCFChart({ entity_name, data }: FCFChartProps) {
  const lastHist = [...data].reverse().find((d) => d.type === "historical");
  const firstProj = data.find((d) => d.type === "projected");
  // Reference line sits between last historical and first projected year
  const splitX =
    lastHist && firstProj
      ? (lastHist.year + firstProj.year) / 2
      : null;

  const projectedCount = data.filter((d) => d.type === "projected").length;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-0.5 min-w-0">
            <CardTitle className="text-[13px] font-medium text-muted-foreground">
              Free cash flow
            </CardTitle>
            <p className="text-[11px] text-muted-foreground/70">
              {entity_name} · historical {data.length - projectedCount}y +{" "}
              {projectedCount}y projection
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span
                className="w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: "var(--chart-1)" }}
              />
              Historical
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span
                className="w-2.5 h-2.5 rounded-sm border border-dashed"
                style={{
                  backgroundColor: "color-mix(in oklab, var(--chart-3) 50%, transparent)",
                  borderColor: "var(--chart-3)",
                }}
              />
              Projected
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={data}
            margin={{ top: 12, right: 8, left: 0, bottom: 4 }}
          >
            <defs>
              <linearGradient id="fcfHist" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={1} />
                <stop
                  offset="100%"
                  stopColor="var(--chart-1)"
                  stopOpacity={0.35}
                />
              </linearGradient>
              <linearGradient id="fcfProj" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-3)" stopOpacity={0.85} />
                <stop
                  offset="100%"
                  stopColor="var(--chart-3)"
                  stopOpacity={0.15}
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
            {splitX != null && (
              <ReferenceLine
                x={splitX}
                stroke="var(--border)"
                strokeDasharray="4 4"
                label={{
                  value: "Projection →",
                  position: "top",
                  fill: "var(--muted-foreground)",
                  fontSize: 10,
                }}
              />
            )}
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: "var(--muted)", opacity: 0.4 }}
            />
            <Bar
              dataKey="fcf"
              radius={[6, 6, 2, 2]}
              maxBarSize={44}
            >
              {data.map((entry, i) => (
                <Cell
                  key={i}
                  fill={
                    entry.type === "historical"
                      ? "url(#fcfHist)"
                      : "url(#fcfProj)"
                  }
                  stroke={
                    entry.type === "projected" ? "var(--chart-3)" : undefined
                  }
                  strokeDasharray={
                    entry.type === "projected" ? "3 3" : undefined
                  }
                  strokeWidth={entry.type === "projected" ? 1 : 0}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
