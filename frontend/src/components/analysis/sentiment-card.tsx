"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Newspaper, Users, Activity, FileText } from "lucide-react";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface ClassifiedArticle {
  headline: string;
  source?: string;
  url?: string;
  date?: string | number;
  sentiment: number;
  event_type: string;
  confidence: number;
  is_sec_filing?: boolean;
}

interface SentimentAdjustment {
  margin_of_safety_pct_delta: number;
  reasoning: string;
}

interface SentimentCardProps {
  ticker: string;
  overall_sentiment: number;
  sentiment_label: string;
  news_score: number | null;
  insider_score: number | null;
  insider_mspr: number | null;
  insider_net_change: number | null;
  sentiment_adjustment: SentimentAdjustment;
  articles: ClassifiedArticle[];
  article_count: number;
  llm_summary: string | null;
  key_events: string[];
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function sentimentColor(score: number): string {
  if (score < -0.5) return "oklch(0.62 0.2 25)";
  if (score < -0.2) return "oklch(0.7 0.15 50)";
  if (score > 0.5) return "oklch(0.68 0.17 150)";
  if (score > 0.2) return "oklch(0.72 0.14 140)";
  return "oklch(0.75 0.08 85)";
}

function sentimentTextColor(score: number): string {
  if (score < -0.5) return "text-red-600 dark:text-red-400";
  if (score < -0.2) return "text-red-500 dark:text-red-400";
  if (score > 0.5) return "text-emerald-600 dark:text-emerald-400";
  if (score > 0.2) return "text-emerald-500 dark:text-emerald-400";
  return "text-amber-600 dark:text-amber-400";
}

function eventTypeBadge(type: string, isSecFiling?: boolean): { label: string; color: string } {
  if (isSecFiling) {
    return { label: "SEC 8-K", color: "bg-slate-500/10 text-slate-700 dark:text-slate-300" };
  }
  const map: Record<string, { label: string; color: string }> = {
    earnings: { label: "Earnings", color: "bg-blue-500/10 text-blue-600 dark:text-blue-400" },
    guidance: { label: "Guidance", color: "bg-purple-500/10 text-purple-600 dark:text-purple-400" },
    ma: { label: "M&A", color: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
    regulatory: { label: "Regulatory", color: "bg-red-500/10 text-red-600 dark:text-red-400" },
    product: { label: "Product", color: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
    executive: { label: "Executive", color: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400" },
    macro: { label: "Macro", color: "bg-orange-500/10 text-orange-600 dark:text-orange-400" },
    analyst: { label: "Analyst", color: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400" },
    other: { label: "Other", color: "bg-gray-500/10 text-gray-600 dark:text-gray-400" },
  };
  return map[type] ?? map.other;
}

function sentimentDot(score: number): string {
  if (score < -0.3) return "bg-red-500";
  if (score < -0.1) return "bg-red-400";
  if (score > 0.3) return "bg-emerald-500";
  if (score > 0.1) return "bg-emerald-400";
  return "bg-amber-400";
}

function formatDate(d: string | number | undefined): string {
  if (d == null) return "";
  const date = typeof d === "number" ? new Date(d * 1000) : new Date(d);
  if (isNaN(date.getTime())) return String(d);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function SentimentGauge({ score, label }: { score: number; label: string }) {
  // Map score from [-1, 1] to [0, 1] for the semicircle
  const normalized = (score + 1) / 2;
  const angle = normalized * 180; // 0 to 180 degrees
  const color = sentimentColor(score);
  const textColor = sentimentTextColor(score);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-48 h-24">
        <svg viewBox="0 0 200 110" className="w-full h-full">
          {/* Background arc */}
          <path
            d="M 10 100 A 90 90 0 0 1 190 100"
            fill="none"
            stroke="var(--muted)"
            strokeWidth="8"
            strokeLinecap="round"
          />
          {/* Colored arc */}
          <path
            d="M 10 100 A 90 90 0 0 1 190 100"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${(normalized * 283).toFixed(0)} 283`}
          />
          {/* Needle */}
          <line
            x1="100"
            y1="100"
            x2={100 + 75 * Math.cos(((180 - angle) * Math.PI) / 180)}
            y2={100 - 75 * Math.sin(((180 - angle) * Math.PI) / 180)}
            stroke="var(--foreground)"
            strokeWidth="2"
            strokeLinecap="round"
          />
          {/* Center dot */}
          <circle cx="100" cy="100" r="4" fill="var(--foreground)" />
          {/* Labels */}
          <text x="10" y="108" className="fill-muted-foreground text-[9px]" textAnchor="start">
            Bearish
          </text>
          <text x="100" y="20" className="fill-muted-foreground text-[9px]" textAnchor="middle">
            Neutral
          </text>
          <text x="190" y="108" className="fill-muted-foreground text-[9px]" textAnchor="end">
            Bullish
          </text>
        </svg>
      </div>
      <div className="text-center">
        <p className={cn("text-[20px] font-semibold", textColor)}>
          {label}
        </p>
        <p className="text-[11px] text-muted-foreground font-mono tabular-nums">
          Score: {score.toFixed(2)}
        </p>
      </div>
    </div>
  );
}

function NewsBreakdown({
  articles,
  summary,
  keyEvents,
}: {
  articles: ClassifiedArticle[];
  summary: string | null;
  keyEvents: string[];
}) {
  if (articles.length === 0 && !summary) return null;

  // Count sentiment distribution
  const bullish = articles.filter((a) => a.sentiment > 0.1).length;
  const bearish = articles.filter((a) => a.sentiment < -0.1).length;
  const neutral = articles.length - bullish - bearish;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Newspaper className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
          News Breakdown
        </span>
      </div>

      {/* Sentiment distribution bar */}
      {articles.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex gap-0.5 h-2 rounded-full overflow-hidden">
            {bearish > 0 && (
              <div
                className="bg-red-500/70 rounded-l-full"
                style={{ width: `${(bearish / articles.length) * 100}%` }}
              />
            )}
            {neutral > 0 && (
              <div
                className="bg-amber-400/50"
                style={{ width: `${(neutral / articles.length) * 100}%` }}
              />
            )}
            {bullish > 0 && (
              <div
                className="bg-emerald-500/70 rounded-r-full"
                style={{ width: `${(bullish / articles.length) * 100}%` }}
              />
            )}
          </div>
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span className="text-red-500">{bearish} bearish</span>
            <span className="text-amber-500">{neutral} neutral</span>
            <span className="text-emerald-500">{bullish} bullish</span>
          </div>
        </div>
      )}

      {/* LLM summary */}
      {summary && (
        <p className="text-[11.5px] text-muted-foreground leading-relaxed">
          {summary}
        </p>
      )}

      {/* Key events */}
      {keyEvents.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
            Key Events
          </p>
          <ul className="space-y-1">
            {keyEvents.map((event, i) => (
              <li key={i} className="text-[11px] text-muted-foreground flex gap-2">
                <span className="text-foreground/40 shrink-0">•</span>
                <span>{event}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Article list */}
      {articles.length > 0 && (
        <div className="space-y-1.5 max-h-48 overflow-y-auto">
          {articles.slice(0, 10).map((article, i) => {
            const badge = eventTypeBadge(article.event_type, article.is_sec_filing);
            return (
              <div
                key={i}
                className="flex items-start gap-2 py-1.5 border-b border-border/40 last:border-0"
              >
                {article.is_sec_filing ? (
                  <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500 dark:text-slate-400" />
                ) : (
                  <span
                    className={cn(
                      "mt-1 h-2 w-2 rounded-full shrink-0",
                      sentimentDot(article.sentiment)
                    )}
                  />
                )}
                <div className="flex-1 min-w-0">
                  {article.url ? (
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11.5px] leading-snug line-clamp-2 text-foreground hover:text-primary hover:underline transition-colors"
                    >
                      {article.headline}
                    </a>
                  ) : (
                    <p className="text-[11.5px] leading-snug line-clamp-2">
                      {article.headline}
                    </p>
                  )}
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span
                      className={cn(
                        "text-[9px] font-medium px-1 py-0.5 rounded",
                        badge.color
                      )}
                    >
                      {badge.label}
                    </span>
                    {article.source && (
                      <span className="text-[9px] text-muted-foreground/70">
                        {article.source}
                      </span>
                    )}
                    <span className="text-[9px] text-muted-foreground/50">
                      {formatDate(article.date)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function InsiderSentiment({
  mspr,
  netChange,
  score,
}: {
  mspr: number | null;
  netChange: number | null;
  score: number | null;
}) {
  if (mspr == null && netChange == null) return null;

  // Map MSPR to a 0-100 position for the progress bar
  const msprPosition = mspr != null ? ((mspr + 1) / 2) * 100 : 50;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Users className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
          Insider Sentiment
        </span>
      </div>

      {mspr != null && (
        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between">
            <span className="text-[10.5px] text-muted-foreground">
              Monthly Share Purchase Ratio
            </span>
            <span
              className={cn(
                "font-mono font-semibold text-[13px] tabular-nums",
                mspr > 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : mspr < 0
                    ? "text-red-600 dark:text-red-400"
                    : "text-muted-foreground"
              )}
            >
              {mspr > 0 ? "+" : ""}
              {mspr.toFixed(4)}
            </span>
          </div>
          <div className="relative h-2 rounded-full bg-muted overflow-hidden">
            {/* Midpoint marker */}
            <div className="absolute inset-y-0 left-1/2 w-px bg-foreground/20 z-10" />
            {/* Filled bar */}
            <div
              className={cn(
                "absolute inset-y-0 rounded-full transition-all",
                mspr > 0 ? "bg-emerald-500" : "bg-red-500"
              )}
              style={{
                left: mspr >= 0 ? "50%" : `${msprPosition}%`,
                width: `${Math.abs(msprPosition - 50)}%`,
              }}
            />
          </div>
          <div className="flex justify-between text-[9px] text-muted-foreground/70">
            <span>Selling</span>
            <span>Buying</span>
          </div>
        </div>
      )}

      {netChange != null && (
        <div className="rounded-xl border bg-muted/30 p-3 space-y-1">
          <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
            Net Insider Change
          </p>
          <p
            className={cn(
              "font-mono font-semibold text-[18px] tabular-nums leading-none",
              netChange > 0
                ? "text-emerald-600 dark:text-emerald-400"
                : netChange < 0
                  ? "text-red-600 dark:text-red-400"
                  : "text-muted-foreground"
            )}
          >
            {netChange > 0 ? "+" : ""}
            {netChange.toLocaleString()} shares
          </p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export default function SentimentCard({
  overall_sentiment,
  sentiment_label,
  news_score,
  insider_score,
  insider_mspr,
  insider_net_change,
  sentiment_adjustment,
  articles,
  article_count,
  llm_summary,
  key_events,
}: SentimentCardProps) {
  const hasData =
    articles.length > 0 ||
    insider_mspr != null ||
    insider_net_change != null ||
    llm_summary != null;

  if (!hasData) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Event & Sentiment
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                No recent event data available
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-[12.5px] text-muted-foreground">
            No news or insider data found for this ticker in the last 30 days.
            Sentiment adjustment was not applied.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Event & Sentiment
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {article_count} articles analyzed · last 30 days
              </p>
            </div>
          </div>
          {sentiment_adjustment.margin_of_safety_pct_delta !== 0 && (
            <span
              className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] font-mono font-medium ring-1",
                sentiment_adjustment.margin_of_safety_pct_delta > 0
                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 ring-emerald-500/20"
                  : "bg-red-500/10 text-red-600 dark:text-red-400 ring-red-500/20"
              )}
            >
              MoS {sentiment_adjustment.margin_of_safety_pct_delta > 0 ? "+" : ""}
              {sentiment_adjustment.margin_of_safety_pct_delta}%
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Sentiment Gauge */}
        <SentimentGauge score={overall_sentiment} label={sentiment_label} />

        {/* Divider */}
        <div className="h-px bg-border" />

        {/* News Breakdown */}
        <NewsBreakdown
          articles={articles}
          summary={llm_summary}
          keyEvents={key_events}
        />

        {/* Insider Sentiment */}
        {(insider_mspr != null || insider_net_change != null) && (
          <>
            <div className="h-px bg-border" />
            <InsiderSentiment
              mspr={insider_mspr}
              netChange={insider_net_change}
              score={insider_score}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
}
