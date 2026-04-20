"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, ExternalLink } from "lucide-react";

interface SourceEntry {
  metric: string;
  calendar_year: number;
  value: number;
  form: string;
  filed: string;
  accession: string;
  url: string;
}

interface SourceTableProps {
  entity_name: string;
  sources: SourceEntry[];
}

function formatValue(value: number): string {
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) < 100) return `$${value.toFixed(2)}`;
  return `$${value.toLocaleString()}`;
}

export default function SourceTable({
  entity_name,
  sources,
}: SourceTableProps) {
  const latestByMetric = new Map<string, SourceEntry>();
  for (const s of sources) {
    const existing = latestByMetric.get(s.metric);
    if (!existing || s.calendar_year > existing.calendar_year) {
      latestByMetric.set(s.metric, s);
    }
  }
  const displaySources = Array.from(latestByMetric.values());

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <CardTitle className="text-[14px] font-semibold">
              Data sources
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              {entity_name} · SEC EDGAR filings
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-3 py-2 bg-muted/40 text-[10.5px] font-medium text-muted-foreground uppercase tracking-wider">
            <span>Metric</span>
            <span className="text-right">Value</span>
            <span className="text-right">Year</span>
            <span className="text-right">Filing</span>
          </div>
          <div className="divide-y divide-border/60">
            {displaySources.map((s, i) => (
              <div
                key={i}
                className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-3 py-2.5 items-center hover:bg-muted/30 transition-colors"
              >
                <span className="text-[13px] text-foreground/90">
                  {s.metric}
                </span>
                <span className="text-right font-mono font-semibold text-[13px] tabular-nums">
                  {formatValue(s.value)}
                </span>
                <span className="text-right font-mono text-[12px] text-muted-foreground tabular-nums">
                  {s.calendar_year}
                </span>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-mono text-[var(--brand)] hover:underline"
                >
                  {s.form}
                  <ExternalLink className="h-2.5 w-2.5" />
                </a>
              </div>
            ))}
          </div>
        </div>
        <p className="text-[10.5px] text-muted-foreground/70 mt-2.5">
          All data sourced from SEC EDGAR. Click a filing to verify.
        </p>
      </CardContent>
    </Card>
  );
}
