"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
} from "lucide-react";

type Recommendation = "Strong Buy" | "Buy" | "Hold" | "Reduce" | "Sell";

interface InvestmentThesisCardProps {
  ticker: string;
  entity_name: string;
  thesis_headline: string;
  recommendation: Recommendation;
  bull_points: string[];
  bear_points: string[];
  key_risks: string[];
  action_summary: string;
  confidence: number;
}

function recommendationTheme(rec: Recommendation) {
  switch (rec) {
    case "Strong Buy":
      return {
        ring: "ring-emerald-500/30",
        bg: "bg-emerald-500/10",
        text: "text-emerald-700 dark:text-emerald-400",
        dot: "bg-emerald-500",
      };
    case "Buy":
      return {
        ring: "ring-emerald-500/20",
        bg: "bg-emerald-500/10",
        text: "text-emerald-600 dark:text-emerald-400",
        dot: "bg-emerald-500",
      };
    case "Hold":
      return {
        ring: "ring-amber-500/20",
        bg: "bg-amber-500/10",
        text: "text-amber-700 dark:text-amber-400",
        dot: "bg-amber-500",
      };
    case "Reduce":
      return {
        ring: "ring-orange-500/20",
        bg: "bg-orange-500/10",
        text: "text-orange-700 dark:text-orange-400",
        dot: "bg-orange-500",
      };
    case "Sell":
      return {
        ring: "ring-red-500/20",
        bg: "bg-red-500/10",
        text: "text-red-700 dark:text-red-400",
        dot: "bg-red-500",
      };
  }
}

function PointList({
  title,
  icon: Icon,
  items,
  accent,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: string[];
  accent: string;
}) {
  if (!items?.length) {
    return (
      <div className="rounded-xl border bg-muted/30 p-3.5 space-y-2">
        <p className={cn("text-[10.5px] uppercase tracking-wider font-medium inline-flex items-center gap-1.5", accent)}>
          <Icon className="h-2.5 w-2.5" />
          {title}
        </p>
        <p className="text-[11px] text-muted-foreground italic">None identified</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-muted/30 p-3.5 space-y-2.5">
      <p className={cn("text-[10.5px] uppercase tracking-wider font-medium inline-flex items-center gap-1.5", accent)}>
        <Icon className="h-2.5 w-2.5" />
        {title}
      </p>
      <ul className="space-y-1.5">
        {items.map((item, idx) => (
          <li
            key={idx}
            className="text-[12px] leading-relaxed text-foreground/90 flex gap-2"
          >
            <span className={cn("mt-[7px] h-1 w-1 rounded-full flex-shrink-0", accent.replace("text-", "bg-"))} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function InvestmentThesisCard({
  entity_name,
  thesis_headline,
  recommendation,
  bull_points,
  bear_points,
  key_risks,
  action_summary,
  confidence,
}: InvestmentThesisCardProps) {
  const theme = recommendationTheme(recommendation);
  const confidencePct = Math.round(confidence * 100);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Investment thesis
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">{entity_name}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10.5px] text-muted-foreground tabular-nums">
              {confidencePct}% confidence
            </span>
            <div
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 h-6 rounded-full text-[11px] font-medium ring-1",
                theme.bg,
                theme.text,
                theme.ring
              )}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", theme.dot)} />
              {recommendation}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Headline */}
        <p className="text-[15px] leading-snug font-semibold text-foreground">
          {thesis_headline}
        </p>

        {/* Three-column: Bull / Bear / Risks */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <PointList
            title="Bull case"
            icon={TrendingUp}
            items={bull_points}
            accent="text-emerald-600 dark:text-emerald-400"
          />
          <PointList
            title="Bear case"
            icon={TrendingDown}
            items={bear_points}
            accent="text-red-600 dark:text-red-400"
          />
          <PointList
            title="Key risks"
            icon={ShieldAlert}
            items={key_risks}
            accent="text-amber-600 dark:text-amber-400"
          />
        </div>

        {/* Action summary callout */}
        <div
          className={cn(
            "rounded-xl p-3.5 text-[12.5px] leading-relaxed border",
            theme.bg,
            theme.text,
            theme.ring
          )}
        >
          {action_summary}
        </div>

        <p className="text-[10px] text-muted-foreground/70 italic">
          LLM-synthesized narrative. Review the underlying quantitative analysis before acting.
        </p>
      </CardContent>
    </Card>
  );
}
