"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Metric {
  label: string;
  value: string;
  year: number;
  source: string;
}

interface MetricTableProps {
  title: string;
  metrics: Metric[];
}

export default function MetricTable({ title, metrics }: MetricTableProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-[13px] font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pb-2">
        <div className="divide-y divide-border/60">
          {metrics.map((m, i) => (
            <div
              key={i}
              className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0 group hover:bg-muted/30 -mx-2 px-2 rounded-lg transition-colors"
            >
              <span className="text-[13px] text-foreground/90">{m.label}</span>
              <div className="flex items-baseline gap-2">
                <span className="font-mono font-semibold text-[13px] tabular-nums">
                  {m.value}
                </span>
                <span className="text-[10px] text-muted-foreground/70 font-mono tabular-nums">
                  {m.year}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
