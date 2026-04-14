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
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Metric</TableHead>
              <TableHead className="text-right">Value</TableHead>
              <TableHead className="text-right">Year</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {metrics.map((m, i) => (
              <TableRow key={i}>
                <TableCell className="font-medium">{m.label}</TableCell>
                <TableCell className="text-right font-mono">
                  {m.value}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {m.year}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
