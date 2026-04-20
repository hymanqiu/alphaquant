"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GitCompareArrows, Star, Info } from "lucide-react";
import { cn } from "@/lib/utils";

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
  sector?: string | null;
  industry?: string | null;
  recommended_multiples?: string[];
  industry_explanation?: string;
  dividend_yield?: number | null;
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
  p_ffo: "P/FFO",
  dividend_yield: "Div Yield",
};

const MULTIPLE_TOOLTIPS: Record<string, string> = {
  p_ffo: "Simplified FFO = Net Income + D&A (excludes property-sale gains)",
};

function formatValue(v: number | null | undefined, key?: string): string {
  if (v == null) return "—";
  if (key === "dividend_yield") return v.toFixed(2) + "%";
  return v.toFixed(2) + "x";
}

function formatDollar(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${v.toFixed(2)}`;
}

function percentileTheme(pct: number | null | undefined) {
  if (pct == null)
    return {
      text: "text-muted-foreground",
      bar: "bg-muted-foreground/40",
      stroke: "var(--muted-foreground)",
      fill: "color-mix(in oklab, var(--muted-foreground) 20%, transparent)",
      label: "Fair",
    };
  if (pct < 20)
    return {
      text: "text-emerald-600 dark:text-emerald-400",
      bar: "bg-emerald-500",
      stroke: "oklch(0.68 0.17 150)",
      fill: "color-mix(in oklab, oklch(0.68 0.17 150) 15%, transparent)",
      label: "Cheap",
    };
  if (pct < 50)
    return {
      text: "text-[var(--brand)]",
      bar: "bg-[var(--brand)]",
      stroke: "var(--brand)",
      fill: "color-mix(in oklab, var(--brand) 12%, transparent)",
      label: "Below avg",
    };
  if (pct < 80)
    return {
      text: "text-amber-600 dark:text-amber-400",
      bar: "bg-amber-500",
      stroke: "oklch(0.75 0.14 85)",
      fill: "color-mix(in oklab, oklch(0.75 0.14 85) 15%, transparent)",
      label: "Above avg",
    };
  return {
    text: "text-red-600 dark:text-red-400",
    bar: "bg-red-500",
    stroke: "oklch(0.62 0.2 25)",
    fill: "color-mix(in oklab, oklch(0.62 0.2 25) 15%, transparent)",
    label: "Expensive",
  };
}

function deltaTheme(delta: number | null): string {
  if (delta == null) return "text-muted-foreground";
  if (delta > 15) return "text-red-600 dark:text-red-400";
  if (delta > 5) return "text-amber-600 dark:text-amber-400";
  if (delta < -15) return "text-emerald-600 dark:text-emerald-400";
  if (delta < -5) return "text-[var(--brand)]";
  return "text-muted-foreground";
}

/* ------------------------------------------------------------------ */
/* Sub-sections                                                        */
/* ------------------------------------------------------------------ */

function PercentileTrack({
  pct,
  theme,
}: {
  pct: number;
  theme: ReturnType<typeof percentileTheme>;
}) {
  const clamped = Math.min(Math.max(pct, 0), 100);
  return (
    <div className="relative h-4 flex items-center">
      {/* Background rail */}
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-[3px] rounded-full bg-muted overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all"
          style={{
            width: `${clamped}%`,
            background: theme.stroke,
            opacity: 0.85,
          }}
        />
      </div>
      {/* Ticks at 25/50/75 */}
      {[25, 50, 75].map((p) => (
        <div
          key={p}
          className="absolute top-1/2 -translate-y-1/2 w-px h-[7px] bg-border"
          style={{ left: `${p}%` }}
        />
      ))}
      {/* Current position marker */}
      <div
        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
        style={{ left: `${clamped}%` }}
      >
        <div
          className="h-2.5 w-2.5 rounded-full ring-[2.5px] ring-background shadow-sm"
          style={{ backgroundColor: theme.stroke }}
        />
      </div>
    </div>
  );
}

function MultipleTile({
  mkey,
  value,
  percentile,
  delta,
  recommended,
}: {
  mkey: string;
  value: number | null;
  percentile: number | null | undefined;
  delta: number | null | undefined;
  recommended: boolean;
}) {
  const theme = percentileTheme(percentile);
  const tooltip = MULTIPLE_TOOLTIPS[mkey];

  return (
    <div
      title={tooltip}
      className={cn(
        "group relative rounded-xl border bg-card px-3.5 py-3 transition-all hover:shadow-sm",
        recommended
          ? "ring-1 ring-[var(--brand)]/30 border-[var(--brand)]/30"
          : "hover:border-foreground/20"
      )}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10.5px] text-muted-foreground uppercase tracking-wider font-medium">
          {MULTIPLE_LABELS[mkey]}
        </span>
        {recommended && (
          <span
            className="inline-flex items-center gap-0.5 text-[9px] font-medium text-[var(--brand)] bg-[var(--brand)]/10 px-1 py-0.5 rounded"
            aria-label="Industry-recommended multiple"
          >
            <Star className="h-2 w-2 fill-[var(--brand)]" strokeWidth={0} />
            <span>IND</span>
          </span>
        )}
      </div>
      {/* Value row */}
      <div className="flex items-baseline gap-1.5 mb-2.5">
        <span className="font-mono font-semibold text-[20px] tabular-nums leading-none tracking-tight">
          {formatValue(value, mkey)}
        </span>
        {delta != null && (
          <span
            className={cn(
              "text-[10.5px] font-mono font-medium tabular-nums",
              deltaTheme(delta)
            )}
          >
            {delta > 0 ? "+" : ""}
            {delta.toFixed(0)}%
          </span>
        )}
      </div>
      {/* Percentile track */}
      {percentile != null ? (
        <div className="space-y-1">
          <PercentileTrack pct={percentile} theme={theme} />
          <div className="flex items-center justify-between text-[10px] font-mono tabular-nums">
            <span className={cn("font-medium", theme.text)}>
              {theme.label}
            </span>
            <span className="text-muted-foreground/80">
              {percentile.toFixed(0)}<span className="text-muted-foreground/50">th</span>
            </span>
          </div>
        </div>
      ) : (
        <div className="h-[31px]" />
      )}
    </div>
  );
}

function HistoricalSparkline({
  series,
  currentValue,
  median,
  stroke,
  fill,
  gradientId,
}: {
  series: HistoricalEntry[];
  currentValue: number;
  median: number | null;
  stroke: string;
  fill: string;
  gradientId: string;
}) {
  const W = 260;
  const H = 44;
  const PAD_TOP = 4;
  const PAD_BOT = 4;

  // Build the plot set: historical series + current point appended at the end
  const sorted = [...series].sort((a, b) => a.year - b.year);
  const allValues = [
    ...sorted.map((s) => s.value),
    currentValue,
    ...(median != null ? [median] : []),
  ];
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;
  const plotH = H - PAD_TOP - PAD_BOT;

  const points = sorted.map((s, i) => {
    const x = (i / Math.max(sorted.length - 1, 1)) * (W - 12) + 6;
    const y = H - PAD_BOT - ((s.value - min) / range) * plotH;
    return { x, y };
  });

  const lastX = points[points.length - 1]?.x ?? 0;
  const lastY = points[points.length - 1]?.y ?? 0;
  const currentY = H - PAD_BOT - ((currentValue - min) / range) * plotH;
  const medianY =
    median != null ? H - PAD_BOT - ((median - min) / range) * plotH : null;

  // Smooth line via catmull-rom-ish approximation (straight segs are fine + look clean)
  const linePath =
    points.length > 1
      ? "M" + points.map((p) => `${p.x},${p.y}`).join(" L")
      : "";
  const areaPath =
    points.length > 1
      ? `${linePath} L${points[points.length - 1].x},${H - PAD_BOT} L${points[0].x},${H - PAD_BOT} Z`
      : "";

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="w-full h-11 overflow-visible"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
        </linearGradient>
      </defs>

      {/* Median reference line */}
      {medianY != null && (
        <line
          x1={0}
          x2={W}
          y1={medianY}
          y2={medianY}
          stroke="var(--muted-foreground)"
          strokeOpacity={0.35}
          strokeDasharray="2 3"
          strokeWidth={1}
        />
      )}

      {/* Area */}
      {areaPath && <path d={areaPath} fill={`url(#${gradientId})`} />}

      {/* Line */}
      {linePath && (
        <path
          d={linePath}
          fill="none"
          stroke={stroke}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.9}
        />
      )}

      {/* Historical points */}
      {points.slice(0, -1).map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={1.5}
          fill={stroke}
          opacity={0.4}
        />
      ))}

      {/* Connector from last historical to current */}
      {points.length > 0 && (
        <line
          x1={lastX}
          y1={lastY}
          x2={W - 6}
          y2={currentY}
          stroke={stroke}
          strokeWidth={1.5}
          strokeDasharray="3 3"
          opacity={0.5}
        />
      )}

      {/* Current value glow + dot */}
      <circle
        cx={W - 6}
        cy={currentY}
        r={6}
        fill={stroke}
        opacity={0.15}
      />
      <circle
        cx={W - 6}
        cy={currentY}
        r={3.5}
        fill={stroke}
        stroke="var(--background)"
        strokeWidth={2}
      />
    </svg>
  );
}

function HistoricalSparklines({
  multiples,
  historicalStats,
  percentiles,
}: {
  multiples: Record<string, number | null>;
  historicalStats: Record<string, HistoricalStat>;
  percentiles: Record<string, number | null>;
}) {
  const keys = Object.keys(MULTIPLE_LABELS).filter(
    (k) => multiples[k] != null && historicalStats[k]?.count >= 3
  );
  if (keys.length === 0) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
      {keys.map((key) => {
        const stat = historicalStats[key];
        const val = multiples[key]!;
        const pct = percentiles[key];
        const median = stat.median;
        const theme = percentileTheme(pct);
        const firstYear = stat.series[0]?.year;
        const lastHistYear = stat.series[stat.series.length - 1]?.year;

        return (
          <div
            key={key}
            className="rounded-xl border bg-card/60 px-3.5 py-3 space-y-2 hover:border-foreground/15 transition-colors"
          >
            <div className="flex items-baseline justify-between gap-3">
              <div className="flex items-baseline gap-2 min-w-0">
                <span className="text-[12px] font-medium">
                  {MULTIPLE_LABELS[key]}
                </span>
                <span className="font-mono font-semibold text-[13px] tabular-nums">
                  {formatValue(val, key)}
                </span>
              </div>
              {pct != null && (
                <span
                  className={cn(
                    "text-[10px] font-mono tabular-nums shrink-0 px-1.5 py-0.5 rounded",
                    theme.text
                  )}
                  style={{ backgroundColor: theme.fill }}
                >
                  {pct.toFixed(0)}
                  <span className="opacity-60">th pctl</span>
                </span>
              )}
            </div>
            <HistoricalSparkline
              series={stat.series}
              currentValue={val}
              median={median}
              stroke={theme.stroke}
              fill={theme.fill}
              gradientId={`spark-${key}`}
            />
            <div className="flex items-center justify-between text-[10px] text-muted-foreground/80 font-mono tabular-nums">
              <span>{firstYear ?? ""}</span>
              <span className="text-muted-foreground/60">
                {median != null && (
                  <>
                    median {formatValue(median, key)}
                    <span className="mx-1">·</span>
                  </>
                )}
                {stat.count}y
              </span>
              <span>{lastHistYear ?? ""} · now</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PeerTable({
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
  const columns = [
    { key: "ticker", label: "Ticker" },
    { key: "peRatio", label: "P/E" },
    { key: "pbRatio", label: "P/B" },
    { key: "priceToSalesRatio", label: "P/S" },
    { key: "evToRevenue", label: "EV/Rev" },
  ] as const;

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
    <div className="rounded-lg border overflow-hidden">
      <div className="grid grid-cols-5 gap-0 px-3 py-2 bg-muted/40 text-[10.5px] font-medium text-muted-foreground uppercase tracking-wider">
        {columns.map((c, i) => (
          <span key={c.key} className={cn(i === 0 ? "text-left" : "text-right")}>
            {c.label}
          </span>
        ))}
      </div>
      <div className="divide-y divide-border/60">
        {/* Target */}
        <div className="grid grid-cols-5 gap-0 px-3 py-2.5 items-center bg-[var(--brand)]/5">
          <span className="flex items-center gap-1.5 text-[13px] font-semibold">
            <span className="font-mono">{ticker}</span>
            <span className="text-[9px] text-[var(--brand)] bg-[var(--brand)]/10 px-1 py-0.5 rounded">
              Target
            </span>
          </span>
          {columns.slice(1).map((col) => {
            const internalKey = Object.entries(multipleToFmpKey).find(
              ([, fmp]) => fmp === col.key
            )?.[0];
            const absVal = internalKey ? currentMultiples[internalKey] : null;
            const deltaKey = fmpToDeltaKey[col.key];
            const delta = deltas[deltaKey];
            return (
              <span
                key={col.key}
                className="text-right font-mono text-[13px] tabular-nums"
              >
                {formatValue(absVal)}
                {delta != null && (
                  <span className={cn("ml-1 text-[10px]", deltaTheme(delta))}>
                    ({delta > 0 ? "+" : ""}
                    {delta.toFixed(0)}%)
                  </span>
                )}
              </span>
            );
          })}
        </div>
        {/* Peers */}
        {peerTable.map((row) => (
          <div
            key={row.ticker}
            className="grid grid-cols-5 gap-0 px-3 py-2 items-center hover:bg-muted/30 transition-colors"
          >
            <span className="font-mono text-[13px]">{row.ticker}</span>
            {columns.slice(1).map((col) => (
              <span
                key={col.key}
                className="text-right font-mono text-[12.5px] text-muted-foreground tabular-nums"
              >
                {formatValue(row[col.key] as number | null)}
              </span>
            ))}
          </div>
        ))}
        {/* Median */}
        {peerMedians && (
          <div className="grid grid-cols-5 gap-0 px-3 py-2.5 items-center bg-muted/30 font-semibold">
            <span className="text-[12px]">Peer median</span>
            {columns.slice(1).map((col) => (
              <span
                key={col.key}
                className="text-right font-mono text-[13px] tabular-nums"
              >
                {formatValue(peerMedians[col.key] as number | null)}
              </span>
            ))}
          </div>
        )}
      </div>
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
  sector,
  industry,
  recommended_multiples,
  industry_explanation,
}: RelativeValuationCardProps) {
  const deltas = peer_comparison?.deltas ?? {};
  const recommendedKeys = new Set(recommended_multiples ?? []);

  if (!price_available) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <GitCompareArrows className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Relative valuation
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {entity_name}
                {sector && ` · ${sector}`}
                {industry && ` · ${industry}`}
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-[12.5px] text-muted-foreground">
            Market price data unavailable. Relative valuation requires live
            price data from FMP API (set AQ_FMP_API_KEY).
          </p>
        </CardContent>
      </Card>
    );
  }

  const multipleEntries = Object.entries(current_multiples).filter(
    ([key, value]) => {
      if (!(key in MULTIPLE_LABELS)) return false;
      if ((key === "p_ffo" || key === "dividend_yield") && value == null)
        return false;
      return true;
    }
  );

  const hasHistorical =
    Object.keys(historical_stats).length > 0 &&
    Object.values(historical_stats).some((s) => s.count >= 3);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <GitCompareArrows className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Relative valuation
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {entity_name}
                {sector && ` · ${sector}`}
                {industry && ` · ${industry}`}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-0.5 text-[10.5px] text-muted-foreground">
            {market_cap && (
              <span>
                MCap <span className="font-mono font-medium text-foreground ml-1">{formatDollar(market_cap)}</span>
              </span>
            )}
            {enterprise_value && (
              <span>
                EV <span className="font-mono font-medium text-foreground ml-1">{formatDollar(enterprise_value)}</span>
              </span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Industry banner */}
        {industry_explanation && recommendedKeys.size > 0 && (
          <div className="rounded-xl border border-[var(--brand)]/20 bg-[var(--brand)]/5 p-3 space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <Info className="h-3 w-3 text-[var(--brand)] shrink-0" />
              <span className="text-[11px] font-medium text-foreground">
                Recommended for this industry:
              </span>
              {Array.from(recommendedKeys).map((k) => (
                <span
                  key={k}
                  className="inline-flex items-center gap-1 text-[10.5px] font-medium bg-[var(--brand)] text-white px-1.5 py-0.5 rounded-md"
                >
                  <Star className="h-2 w-2 fill-white" strokeWidth={0} />
                  {MULTIPLE_LABELS[k] ?? k}
                </span>
              ))}
            </div>
            <p className="text-[11.5px] text-muted-foreground leading-relaxed">
              {industry_explanation}
            </p>
          </div>
        )}

        {/* Current multiples grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {multipleEntries.map(([key, value]) => (
            <MultipleTile
              key={key}
              mkey={key}
              value={value}
              percentile={percentiles[key]}
              delta={deltas[key]}
              recommended={recommendedKeys.has(key)}
            />
          ))}
        </div>

        {/* Historical */}
        {hasHistorical && (
          <div className="space-y-2.5 pt-1">
            <div className="flex items-center gap-2">
              <span className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
                Historical trend
              </span>
              <div className="flex-1 h-px bg-border" />
              <span className="text-[10px] text-muted-foreground/70">
                dashed = median · large dot = current
              </span>
            </div>
            <HistoricalSparklines
              multiples={current_multiples}
              historicalStats={historical_stats}
              percentiles={percentiles}
            />
          </div>
        )}

        {/* Peers */}
        {peer_comparison?.peer_data_available &&
          peer_comparison.peer_table &&
          peer_comparison.peer_table.length > 0 && (
            <div className="space-y-2.5 pt-1">
              <div className="flex items-center gap-2">
                <span className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
                  Peer comparison
                </span>
                <span className="text-[10px] text-muted-foreground/70">
                  ({peer_comparison.peers?.length ?? 0} peers)
                </span>
                <div className="flex-1 h-px bg-border" />
              </div>
              <PeerTable
                ticker={ticker}
                currentMultiples={current_multiples}
                peerTable={peer_comparison.peer_table}
                peerMedians={peer_comparison.peer_medians ?? {}}
                deltas={deltas}
              />
            </div>
          )}
      </CardContent>
    </Card>
  );
}
