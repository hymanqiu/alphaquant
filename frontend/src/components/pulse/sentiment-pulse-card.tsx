"use client";

import { useEffect, useId, useState } from "react";
import { Heart } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface SentimentPulseCardProps {
  ticker: string;
  fear_greed_value: number | null;
  fear_greed_label: string | null;
  put_call_ratio: number | null;
  insider_net_usd_90d: number | null;
  short_interest_pct: number | null;
  aaii_bull_minus_bear: number | null;
}

type Tone = "bull" | "bear" | "neutral" | "muted";

const TONE_TEXT: Record<Tone, string> = {
  bull: "text-emerald-700 dark:text-emerald-400",
  bear: "text-rose-700 dark:text-rose-400",
  neutral: "text-foreground",
  muted: "text-muted-foreground",
};

function fgTone(score: number | null): Tone {
  if (score === null) return "muted";
  if (score >= 55) return "bull";
  if (score < 45) return "bear";
  return "neutral";
}

function formatUSD(v: number | null): string {
  if (v === null) return "—";
  if (v === 0) return "$0";
  const abs = Math.abs(v);
  const sign = v > 0 ? "+" : "−";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

function signTone(v: number | null): Tone {
  if (v === null) return "muted";
  if (v > 0) return "bull";
  if (v < 0) return "bear";
  return "neutral";
}

// ---------------------------------------------------------------------------
// F&G half-circle gauge
// ---------------------------------------------------------------------------

function FearGreedGauge({
  score,
  label,
}: {
  score: number | null;
  label: string | null;
}) {
  const gradId = useId();
  const glowId = useId();

  // Initial rotation = -90° (pointer at left = score 0). Animate to target on mount.
  const target = score === null ? -90 : (score / 100) * 180 - 90;
  const [rotation, setRotation] = useState(-90);

  useEffect(() => {
    // Defer one frame so the transition fires from the initial state.
    const id = requestAnimationFrame(() => setRotation(target));
    return () => cancelAnimationFrame(id);
  }, [target]);

  const tone = fgTone(score);

  return (
    <div className="flex flex-col items-center gap-1.5">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
        Fear &amp; Greed Index
      </p>
      <svg
        viewBox="0 0 200 130"
        className="w-full max-w-[240px]"
        aria-label={
          score === null
            ? "Fear & Greed: data unavailable"
            : `Fear & Greed score ${score}, ${label ?? "n/a"}`
        }
      >
        <defs>
          <linearGradient
            id={gradId}
            x1="20"
            y1="0"
            x2="180"
            y2="0"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%" stopColor="#f43f5e" />     {/* rose-500 */}
            <stop offset="50%" stopColor="#f59e0b" />    {/* amber-500 */}
            <stop offset="100%" stopColor="#10b981" />   {/* emerald-500 */}
          </linearGradient>
          <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Arc track */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth="10"
          strokeLinecap="round"
        />

        {/* End labels */}
        <text
          x="14"
          y="120"
          textAnchor="start"
          className="fill-muted-foreground text-[9px] font-medium uppercase tracking-wider"
        >
          Fear
        </text>
        <text
          x="186"
          y="120"
          textAnchor="end"
          className="fill-muted-foreground text-[9px] font-medium uppercase tracking-wider"
        >
          Greed
        </text>

        {/* Pointer (only when we have a value) */}
        {score !== null && (
          <g
            style={{
              transform: `rotate(${rotation}deg)`,
              transformOrigin: "100px 100px",
              transformBox: "view-box",
              transition: "transform 850ms cubic-bezier(0.34, 1.56, 0.64, 1)",
            }}
          >
            <line
              x1="100"
              y1="100"
              x2="100"
              y2="32"
              className="stroke-foreground"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <circle
              cx="100"
              cy="32"
              r="4"
              className="fill-foreground"
              filter={`url(#${glowId})`}
            />
            <circle
              cx="100"
              cy="100"
              r="3"
              className="fill-background stroke-foreground"
              strokeWidth="1.5"
            />
          </g>
        )}
      </svg>
      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            "font-mono font-semibold tabular-nums leading-none text-[28px]",
            TONE_TEXT[tone],
          )}
        >
          {score === null ? "—" : score}
        </span>
        {label && (
          <span
            className={cn(
              "text-[12px] font-medium uppercase tracking-wider",
              TONE_TEXT[tone],
            )}
          >
            {label}
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Right-side metric rows
// ---------------------------------------------------------------------------

interface MetricRowSpec {
  label: string;
  value: string;
  tone: Tone;
}

function MetricRow({ spec }: { spec: MetricRowSpec }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border/40 last:border-0 py-2 first:pt-0 last:pb-0">
      <span className="text-[11px] text-muted-foreground">{spec.label}</span>
      <span
        className={cn(
          "font-mono font-semibold text-[13px] tabular-nums",
          TONE_TEXT[spec.tone],
        )}
      >
        {spec.value}
      </span>
    </div>
  );
}

export default function SentimentPulseCard({
  ticker,
  fear_greed_value,
  fear_greed_label,
  put_call_ratio,
  insider_net_usd_90d,
  short_interest_pct,
  aaii_bull_minus_bear,
}: SentimentPulseCardProps) {
  const rows: MetricRowSpec[] = [
    {
      label: "Put/Call ratio",
      value: put_call_ratio === null ? "—" : put_call_ratio.toFixed(2),
      tone: put_call_ratio === null ? "muted" : "neutral",
    },
    {
      label: "Insider net (90d)",
      value: formatUSD(insider_net_usd_90d),
      tone: signTone(insider_net_usd_90d),
    },
    {
      label: "Short interest",
      value:
        short_interest_pct === null ? "—" : `${short_interest_pct.toFixed(1)}%`,
      tone: short_interest_pct === null ? "muted" : "neutral",
    },
    {
      label: "AAII bull − bear",
      value:
        aaii_bull_minus_bear === null
          ? "—"
          : `${aaii_bull_minus_bear > 0 ? "+" : ""}${aaii_bull_minus_bear.toFixed(1)}`,
      tone: signTone(aaii_bull_minus_bear),
    },
  ];

  return (
    <Card>
      <CardHeader className="pb-2.5">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
            <Heart className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <CardTitle className="text-[14px] font-semibold">
              Sentiment pulse · {ticker}
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Crowd positioning & insider flow
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8 items-center">
          <div className="flex justify-center">
            <FearGreedGauge
              score={fear_greed_value}
              label={fear_greed_label}
            />
          </div>
          <div className="rounded-xl border bg-muted/30 px-4 py-1">
            {rows.map((r) => (
              <MetricRow key={r.label} spec={r} />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
