"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
  // Show latest year per metric
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
        <CardTitle className="text-base">
          {entity_name} - Data Sources (SEC EDGAR)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Metric</TableHead>
              <TableHead className="text-right">Value</TableHead>
              <TableHead className="text-right">Year</TableHead>
              <TableHead className="text-right">Filing</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displaySources.map((s, i) => (
              <TableRow key={i}>
                <TableCell className="font-medium">{s.metric}</TableCell>
                <TableCell className="text-right font-mono">
                  {formatValue(s.value)}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {s.calendar_year}
                </TableCell>
                <TableCell className="text-right">
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-500 hover:underline"
                  >
                    {s.form}
                  </a>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="text-xs text-muted-foreground mt-3">
          All data sourced from SEC EDGAR. Click filing links to verify.
        </p>
      </CardContent>
    </Card>
  );
}
