"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  TrendingUp,
  FileText,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface ParameterAdjustment {
  type: string;
  value: number;
  reasoning: string;
}

interface ImpactfulArticle {
  headline: string;
  source?: string;
  url?: string;
  date?: string | number;
  event_type?: string;
  sentiment?: number;
}

interface EventImpactCardProps {
  ticker: string;
  original_assumptions: {
    growth_rate: number;
    terminal_growth_rate: number;
    discount_rate: number;
    latest_fcf: number;
  };
  parameter_adjustments: Record<string, ParameterAdjustment | null>;
  adjusted_assumptions: {
    growth_rate: number;
    terminal_growth_rate: number;
    discount_rate: number;
    latest_fcf: number;
  };
  recalculated_dcf: {
    intrinsic_value_per_share: number | null;
    enterprise_value: number;
  } | null;
  impactful_articles: ImpactfulArticle[];
  summary: string;
  confidence: number;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function formatDelta(original: number, adjusted: number, unit: string) {
  const delta = adjusted - original;
  if (Math.abs(delta) < 0.005) return null;

  const isPositive = delta > 0;
  const Icon = isPositive ? ArrowUp : ArrowDown;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-[11px] font-mono font-medium",
        isPositive
          ? "text-emerald-600 dark:text-emerald-400"
          : "text-red-600 dark:text-red-400"
      )}
    >
      <Icon className="h-3 w-3" />
      {isPositive ? "+" : ""}
      {delta.toFixed(1)}
      {unit}
    </span>
  );
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.7) return "text-emerald-600 dark:text-emerald-400";
  if (confidence >= 0.4) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function confidenceLabel(confidence: number): string {
  if (confidence >= 0.7) return "High";
  if (confidence >= 0.4) return "Medium";
  return "Low";
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

function ParameterComparison({
  label,
  original,
  adjusted,
  unit,
  reasoning,
}: {
  label: string;
  original: number;
  adjusted: number;
  unit: string;
  reasoning?: string;
}) {
  const delta = formatDelta(original, adjusted, unit);
  if (!delta) return null;

  return (
    <div className="flex items-center justify-between py-2 border-b border-border/40 last:border-0">
      <div className="flex items-center gap-2">
        <span className="text-[11.5px] text-muted-foreground min-w-[130px]">
          {label}
        </span>
        {reasoning && (
          <span className="text-[10px] text-muted-foreground/60 line-clamp-1 max-w-[200px]" title={reasoning}>
            {reasoning}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-[11px] font-mono text-muted-foreground tabular-nums">
          {original.toFixed(1)}{unit}
        </span>
        <ArrowRight className="h-3 w-3 text-muted-foreground/40" />
        <span className="text-[11px] font-mono font-medium text-foreground tabular-nums">
          {adjusted.toFixed(1)}{unit}
        </span>
        {delta}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export default function EventImpactCard({
  original_assumptions,
  parameter_adjustments,
  adjusted_assumptions,
  recalculated_dcf,
  impactful_articles,
  summary,
  confidence,
}: EventImpactCardProps) {
  const hasAdjustments = Object.values(parameter_adjustments).some(
    (v) => v !== null
  );

  if (!hasAdjustments && impactful_articles.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Event Impact Analysis
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                No material impact detected on valuation
              </p>
            </div>
          </div>
        </CardHeader>
      </Card>
    );
  }

  // Calculate intrinsic value change
  const hasNewIntrinsic =
    recalculated_dcf?.intrinsic_value_per_share != null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Event Impact Analysis
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {impactful_articles.length} impactful event{impactful_articles.length !== 1 ? "s" : ""} detected
              </p>
            </div>
          </div>
          <span
            className={cn(
              "text-[11px] font-mono font-medium",
              confidenceColor(confidence)
            )}
          >
            {confidenceLabel(confidence)} confidence ({(confidence * 100).toFixed(0)}%)
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Summary */}
        {summary && (
          <p className="text-[12px] text-muted-foreground leading-relaxed">
            {summary}
          </p>
        )}

        {/* Parameter comparison table */}
        {hasAdjustments && (
          <div className="space-y-0">
            <ParameterComparison
              label="FCF Growth Rate"
              original={original_assumptions.growth_rate}
              adjusted={adjusted_assumptions.growth_rate}
              unit="%"
              reasoning={parameter_adjustments.growth_rate?.reasoning}
            />
            <ParameterComparison
              label="Terminal Growth Rate"
              original={original_assumptions.terminal_growth_rate}
              adjusted={adjusted_assumptions.terminal_growth_rate}
              unit="%"
              reasoning={parameter_adjustments.terminal_growth_rate?.reasoning}
            />
            <ParameterComparison
              label="Discount Rate (WACC)"
              original={original_assumptions.discount_rate}
              adjusted={adjusted_assumptions.discount_rate}
              unit="%"
              reasoning={parameter_adjustments.discount_rate?.reasoning}
            />
          </div>
        )}

        {/* Intrinsic value comparison */}
        {hasNewIntrinsic && (
          <div className="rounded-xl border bg-muted/30 p-3 space-y-1">
            <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
              Recalculated Intrinsic Value
            </p>
            <p className="font-mono font-semibold text-[18px] tabular-nums text-foreground">
              ${recalculated_dcf!.intrinsic_value_per_share!.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              <span className="text-[11px] text-muted-foreground font-normal ml-1.5">/share</span>
            </p>
          </div>
        )}

        {/* Impactful articles */}
        {impactful_articles.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[10.5px] text-muted-foreground uppercase tracking-wider">
              Triggering Events
            </p>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {impactful_articles.map((article, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 py-1.5 border-b border-border/40 last:border-0"
                >
                  <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    {article.url ? (
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] leading-snug line-clamp-2 text-foreground hover:text-primary hover:underline transition-colors"
                      >
                        {article.headline}
                      </a>
                    ) : (
                      <p className="text-[11px] leading-snug line-clamp-2">
                        {article.headline}
                      </p>
                    )}
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {article.source && (
                        <span className="text-[9px] text-muted-foreground/70">
                          {article.source}
                        </span>
                      )}
                      {article.date != null && formatDate(article.date) && (
                        <span className="text-[9px] text-muted-foreground/50">
                          {formatDate(article.date)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
