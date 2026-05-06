"use client";

import { Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MarketContextCardProps {
  ticker: string;
  spy_change_pct: number | null;
  vix: number | null;
  treasury_10y_pct: number | null;
  dxy: number | null;
  sector_etf_symbol: string;
  sector_change_pct: number | null;
}

type Tone = "bull" | "bear" | "neutral" | "muted";

const VALUE_COLOR: Record<Tone, string> = {
  bull: "text-emerald-700 dark:text-emerald-400",
  bear: "text-rose-700 dark:text-rose-400",
  neutral: "text-foreground",
  muted: "text-muted-foreground",
};

function toneFromPct(pct: number | null): Tone {
  if (pct === null) return "muted";
  if (pct > 0) return "bull";
  if (pct < 0) return "bear";
  return "neutral";
}

function formatPct(pct: number | null): string {
  if (pct === null) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function formatNumber(v: number | null, decimals: number, suffix = ""): string {
  if (v === null) return "—";
  return `${v.toFixed(decimals)}${suffix}`;
}

interface TileSpec {
  key: string;
  label: string;
  value: string;
  tone: Tone;
}

function MarketTile({ spec }: { spec: TileSpec }) {
  return (
    <div className="rounded-xl border bg-muted/30 px-3 py-2.5 space-y-1">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">
        {spec.label}
      </p>
      <p
        className={cn(
          "font-mono font-semibold text-[16px] tabular-nums leading-none",
          VALUE_COLOR[spec.tone],
        )}
      >
        {spec.value}
      </p>
    </div>
  );
}

export default function MarketContextCard({
  ticker,
  spy_change_pct,
  vix,
  treasury_10y_pct,
  dxy,
  sector_etf_symbol,
  sector_change_pct,
}: MarketContextCardProps) {
  const tiles: TileSpec[] = [
    {
      key: "spy",
      label: "SPY",
      value: formatPct(spy_change_pct),
      tone: toneFromPct(spy_change_pct),
    },
    {
      key: "vix",
      label: "VIX",
      value: formatNumber(vix, 1),
      tone: vix === null ? "muted" : "neutral",
    },
    {
      key: "tnx",
      label: "10Y yield",
      value: formatNumber(treasury_10y_pct, 2, "%"),
      tone: treasury_10y_pct === null ? "muted" : "neutral",
    },
    {
      key: "dxy",
      label: "DXY",
      value: formatNumber(dxy, 1),
      tone: dxy === null ? "muted" : "neutral",
    },
    {
      key: "sector",
      label: sector_etf_symbol,
      value: formatPct(sector_change_pct),
      tone: toneFromPct(sector_change_pct),
    },
  ];

  return (
    <Card>
      <CardHeader className="pb-2.5">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
            <Globe className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <CardTitle className="text-[14px] font-semibold">
              Market context · {ticker}
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Broader tape, rates, dollar, and sector pulse
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {tiles.map((t) => (
            <MarketTile key={t.key} spec={t} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
