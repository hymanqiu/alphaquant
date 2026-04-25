"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  BookOpen,
  ExternalLink,
  TrendingUp,
  AlertTriangle,
  Quote,
} from "lucide-react";

type Tone = "optimistic" | "neutral" | "cautious" | "negative";

interface QualitativeInsightsCardProps {
  entity_name: string;
  ticker: string;
  filing_date: string;
  accession_number: string;
  filing_url: string;
  tone: Tone;
  forward_guidance_summary: string;
  growth_drivers: string[];
  management_concerns: string[];
  notable_quotes: string[];
  rejected_quote_count?: number;
  confidence: number;
  mdna_char_count?: number;
  parser_strategy?: string;
}

function toneTheme(tone: Tone) {
  switch (tone) {
    case "optimistic":
      return {
        ring: "ring-emerald-500/30",
        bg: "bg-emerald-500/10",
        text: "text-emerald-700 dark:text-emerald-400",
        dot: "bg-emerald-500",
        label: "Optimistic",
      };
    case "neutral":
      return {
        ring: "ring-slate-500/20",
        bg: "bg-slate-500/10",
        text: "text-slate-700 dark:text-slate-400",
        dot: "bg-slate-500",
        label: "Neutral",
      };
    case "cautious":
      return {
        ring: "ring-amber-500/30",
        bg: "bg-amber-500/10",
        text: "text-amber-700 dark:text-amber-400",
        dot: "bg-amber-500",
        label: "Cautious",
      };
    case "negative":
      return {
        ring: "ring-red-500/30",
        bg: "bg-red-500/10",
        text: "text-red-700 dark:text-red-400",
        dot: "bg-red-500",
        label: "Negative",
      };
  }
}

function BulletList({
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
        <p
          className={cn(
            "text-[10.5px] uppercase tracking-wider font-medium inline-flex items-center gap-1.5",
            accent
          )}
        >
          <Icon className="h-2.5 w-2.5" />
          {title}
        </p>
        <p className="text-[11px] text-muted-foreground italic">None identified</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-muted/30 p-3.5 space-y-2.5">
      <p
        className={cn(
          "text-[10.5px] uppercase tracking-wider font-medium inline-flex items-center gap-1.5",
          accent
        )}
      >
        <Icon className="h-2.5 w-2.5" />
        {title}
      </p>
      <ul className="space-y-1.5">
        {items.map((item, idx) => (
          <li
            key={idx}
            className="text-[12px] leading-relaxed text-foreground/90 flex gap-2"
          >
            <span
              className={cn(
                "mt-[7px] h-1 w-1 rounded-full flex-shrink-0",
                accent.replace("text-", "bg-")
              )}
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function QualitativeInsightsCard({
  entity_name,
  filing_date,
  accession_number,
  filing_url,
  tone,
  forward_guidance_summary,
  growth_drivers,
  management_concerns,
  notable_quotes,
  rejected_quote_count,
  confidence,
}: QualitativeInsightsCardProps) {
  const theme = toneTheme(tone);
  const confidencePct = Math.round(confidence * 100);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                10-K Qualitative insights
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {entity_name} · MD&amp;A · filed {filing_date}
              </p>
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
              {theme.label} tone
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Forward guidance */}
        <div className="rounded-xl border bg-muted/20 p-3.5">
          <p className="text-[10.5px] uppercase tracking-wider font-medium text-muted-foreground mb-1.5">
            Forward guidance (from MD&amp;A)
          </p>
          <p className="text-[12.5px] leading-relaxed text-foreground/90">
            {forward_guidance_summary}
          </p>
        </div>

        {/* Growth drivers / Concerns */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <BulletList
            title="Growth drivers"
            icon={TrendingUp}
            items={growth_drivers}
            accent="text-emerald-600 dark:text-emerald-400"
          />
          <BulletList
            title="Management concerns"
            icon={AlertTriangle}
            items={management_concerns}
            accent="text-amber-600 dark:text-amber-400"
          />
        </div>

        {/* Notable quotes — verbatim, verified */}
        {notable_quotes.length > 0 && (
          <div className="rounded-xl border bg-muted/30 p-3.5 space-y-2.5">
            <p className="text-[10.5px] uppercase tracking-wider font-medium text-muted-foreground inline-flex items-center gap-1.5">
              <Quote className="h-2.5 w-2.5" />
              Verbatim quotes from MD&amp;A
            </p>
            <ul className="space-y-2">
              {notable_quotes.map((q, idx) => (
                <li
                  key={idx}
                  className="text-[12px] leading-relaxed italic text-foreground/85 border-l-2 border-muted-foreground/30 pl-3"
                >
                  &ldquo;{q}&rdquo;
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Footer: provenance */}
        <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground/80">
          <span className="italic">
            LLM extraction from 10-K MD&amp;A. All quotes verified verbatim
            {typeof rejected_quote_count === "number" && rejected_quote_count > 0
              ? ` (${rejected_quote_count} rejected)`
              : ""}
            .
          </span>
          <a
            href={filing_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[var(--brand)] hover:underline"
            title={accession_number}
          >
            source filing <ExternalLink className="h-2.5 w-2.5" />
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
