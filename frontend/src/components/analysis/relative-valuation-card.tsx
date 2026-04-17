"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface HistoricalEntry {
  year: number;
  value: number;
}

interface HistoricalStat {
  series: HistoricalEntry[];
  median: number | null;
  average: number | null;
  count: number;
}

interface PeerRow {
  ticker: string;
  peRatio?: number | null;
  pbRatio?: number | null;
  priceToSalesRatio?: number | null;
  evToRevenue?: number | null;
  evToFreeCashFlow?: number | null;
  pegRatio?: number | null;
}

interface RelativeValuationCardProps {
  entity_name: string;
  ticker: string;
  price_available: boolean;
  market_cap?: number | null;
  enterprise_value?: number | null;
  current_multiples: Record<string, number | null>;
  historical_stats: Record<string, HistoricalStat>;
  percentiles: Record<string, number | null>;
  peer_comparison: {
    peer_data_available: boolean;
    peers?: string[];
    peer_medians?: Record<string, number | null>;
    peer_table?: PeerRow[];
    deltas?: Record<string, number | null>;
  } | null;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const MULTIPLE_LABELS: Record<string, string> = {
  pe: "P/E",
  pb: "P/B",
  ps: "P/S",
  ev_to_revenue: "EV/Revenue",
  ev_to_ebit: "EV/EBIT",
  ev_to_fcf: "EV/FCF",
  peg: "PEG",
};

function formatValue(v: number | null | undefined): string {
  if (v == null) return "N/A";
  return v.toFixed(2) + "x";
}

function formatDollar(v: number | null | undefined): string {
  if (v == null) return "N/A";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${v.toFixed(2)}`;
}

/**
 * Color for a multiple value based on its historical percentile.
 * Lower percentile = cheaper = green. Higher = expensive = red.
 */
function percentileColor(pct: number | null | undefined): string {
  if (pct == null) return "bg-gray-400";
  if (pct < 20) return "bg-emerald-500";
  if (pct < 50) return "bg-blue-500";
  if (pct < 80) return "bg-amber-500";
  return "bg-red-500";
}

function deltaBadgeColor(delta: number | null): string {
  if (delta == null) return "";
  if (delta > 15) return "text-red-600";
  if (delta > 5) return "text-amber-600";
  if (delta < -15) return "text-emerald-600";
  if (delta < -5) return "text-blue-600";
  return "";
}

/* ------------------------------------------------------------------ */
/* Sub-sections                                                        */
/* ------------------------------------------------------------------ */

function CurrentMultiplesGrid({
  multiples,
  percentiles,
  deltas,
}: {
  multiples: Record<string, number | null>;
  percentiles: Record<string, number | null>;
  deltas: Record<string, number | null>;
}) {
  const entries = Object.entries(multiples).filter(
    ([key]) => key in MULTIPLE_LABELS,
  );

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {entries.map(([key, value]) => {
        const pct = percentiles[key];
        const delta = deltas[key];
        return (
          <div
            key={key}
            className="p-3 rounded-md border bg-muted/30 space-y-1"
          >
            <p className="text-xs text-muted-foreground">
              {MULTIPLE_LABELS[key]}
            </p>
            <div className="flex items-baseline gap-2">
              <span className="text-lg font-mono font-bold">
                {formatValue(value)}
              </span>
              {delta != null && (
                <span
                  className={`text-xs font-mono ${deltaBadgeColor(delta)}`}
                >
                  {delta > 0 ? "+" : ""}
                  {delta.toFixed(0)}%
                </span>
              )}
            </div>
            {pct != null && (
              <div className="flex items-center gap-1.5">
                <div
                  className={`h-1.5 rounded-full ${percentileColor(pct)}`}
                  style={{ width: `${Math.min(pct, 100)}%`, minWidth: 4 }}
                />
                <span className="text-[10px] text-muted-foreground">
                  {pct.toFixed(0)}pctl
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function HistoricalPercentileBars({
  multiples,
  historicalStats,
  percentiles,
}: {
  multiples: Record<string, number | null>;
  historicalStats: Record<string, HistoricalStat>;
  percentiles: Record<string, number | null>;
}) {
  const keys = Object.keys(MULTIPLE_LABELS).filter(
    (k) => multiples[k] != null && historicalStats[k]?.count >= 3,
  );

  if (keys.length === 0) return null;

  return (
    <div className="space-y-3">
      {keys.map((key) => {
        const stat = historicalStats[key];
        const val = multiples[key]!;
        const pct = percentiles[key];
        const median = stat.median;

        return (
          <div key={key}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium">
                {MULTIPLE_LABELS[key]}: {formatValue(val)}
              </span>
              {pct != null && (
                <span className="text-xs text-muted-foreground">
                  {pct.toFixed(0)}th percentile
                  {median != null && ` (${stat.count}yr median: ${formatValue(median)})`}
                </span>
              )}
            </div>
            <div className="relative h-3 rounded-full bg-muted overflow-hidden">
              <div
                className={`absolute top-0 left-0 h-full rounded-full transition-all ${percentileColor(pct)}`}
                style={{ width: `${Math.min(pct ?? 0, 100)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PeerComparisonTable({
  ticker,
  currentMultiples,
  peerTable,
  peerMedians,
  deltas,
}: {
  ticker: string;
  currentMultiples: Record<string, number | null>;
  peerTable: PeerRow[];
  peerMedians: Record<string, number | null>;
  deltas: Record<string, number | null>;
}) {
  if (!peerTable || peerTable.length === 0) return null;

  const columns = [
    { key: "ticker", label: "Ticker" },
    { key: "peRatio", label: "P/E" },
    { key: "pbRatio", label: "P/B" },
    { key: "priceToSalesRatio", label: "P/S" },
    { key: "evToRevenue", label: "EV/Rev" },
  ] as const;

  // Map from our internal keys to FMP peer metric keys
  const multipleToFmpKey: Record<string, string> = {
    pe: "peRatio",
    pb: "pbRatio",
    ps: "priceToSalesRatio",
    ev_to_revenue: "evToRevenue",
  };
  const fmpToDeltaKey: Record<string, string> = {
    peRatio: "pe",
    pbRatio: "pb",
    priceToSalesRatio: "ps",
    evToRevenue: "ev_to_revenue",
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            {columns.map((col) => (
              <th key={col.key} className="pb-2 pr-4">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {/* Target company row — shows absolute values + delta */}
          <tr className="border-b bg-primary/5 font-medium">
            <td className="py-2 pr-4">
              {ticker}
              <Badge variant="outline" className="ml-1 text-[10px] px-1">
                Target
              </Badge>
            </td>
            {columns.slice(1).map((col) => {
              // Find the company's absolute value from current_multiples
              const internalKey = Object.entries(multipleToFmpKey)
                .find(([, fmp]) => fmp === col.key)?.[0];
              const absVal = internalKey ? currentMultiples[internalKey] : null;
              const deltaKey = fmpToDeltaKey[col.key];
              const delta = deltas[deltaKey];
              return (
                <td key={col.key} className="py-2 pr-4 font-mono">
                  {formatValue(absVal)}
                  {delta != null && (
                    <span className={`ml-1 text-xs ${deltaBadgeColor(delta)}`}>
                      ({delta > 0 ? "+" : ""}{delta.toFixed(0)}%)
                    </span>
                  )}
                </td>
              );
            })}
          </tr>
          {/* Peer rows */}
          {peerTable.map((row) => (
            <tr key={row.ticker} className="border-b">
              <td className="py-2 pr-4">{row.ticker}</td>
              {columns.slice(1).map((col) => (
                <td key={col.key} className="py-2 pr-4 font-mono text-muted-foreground">
                  {formatValue(row[col.key] as number | null)}
                </td>
              ))}
            </tr>
          ))}
          {/* Peer median row */}
          {peerMedians && (
            <tr className="border-t font-bold bg-muted/30">
              <td className="py-2 pr-4">Peer Median</td>
              {columns.slice(1).map((col) => (
                <td key={col.key} className="py-2 pr-4 font-mono">
                  {formatValue(peerMedians[col.key] as number | null)}
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export default function RelativeValuationCard({
  entity_name,
  ticker,
  price_available,
  market_cap,
  enterprise_value,
  current_multiples,
  historical_stats,
  percentiles,
  peer_comparison,
}: RelativeValuationCardProps) {
  const deltas = peer_comparison?.deltas ?? {};

  if (!price_available) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {entity_name} - Relative Valuation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Market price data unavailable. Relative valuation requires live
            price data from FMP API (set AQ_FMP_API_KEY).
          </p>
        </CardContent>
      </Card>
    );
  }

  const hasHistorical =
    Object.keys(historical_stats).length > 0 &&
    Object.values(historical_stats).some((s) => s.count >= 3);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            {entity_name} - Relative Valuation
          </CardTitle>
          <div className="flex gap-2 text-xs text-muted-foreground">
            {market_cap && (
              <span>MCap: {formatDollar(market_cap)}</span>
            )}
            {enterprise_value && (
              <span>EV: {formatDollar(enterprise_value)}</span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Section A — Current Multiples Grid */}
        <CurrentMultiplesGrid
          multiples={current_multiples}
          percentiles={percentiles}
          deltas={deltas}
        />

        {/* Section B — Historical Percentile Bars */}
        {hasHistorical && (
          <>
            <Separator />
            <div>
              <p className="text-xs text-muted-foreground mb-3">
                Historical Percentile Analysis
              </p>
              <HistoricalPercentileBars
                multiples={current_multiples}
                historicalStats={historical_stats}
                percentiles={percentiles}
              />
            </div>
          </>
        )}

        {/* Section C — Peer Comparison Table */}
        {peer_comparison?.peer_data_available &&
          peer_comparison.peer_table &&
          peer_comparison.peer_table.length > 0 && (
            <>
              <Separator />
              <div>
                <p className="text-xs text-muted-foreground mb-3">
                  Peer Comparison ({peer_comparison.peers?.length ?? 0} peers)
                </p>
                <PeerComparisonTable
                  ticker={ticker}
                  currentMultiples={current_multiples}
                  peerTable={peer_comparison.peer_table}
                  peerMedians={peer_comparison.peer_medians ?? {}}
                  deltas={deltas}
                />
              </div>
            </>
          )}
      </CardContent>
    </Card>
  );
}
