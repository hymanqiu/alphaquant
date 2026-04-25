"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  Castle,
  ExternalLink,
  Quote,
  TrendingUp,
  Globe,
  Sparkles,
  Lock,
  Award,
  Gem,
  Cog,
} from "lucide-react";

type PowerName =
  | "scale_economies"
  | "network_effects"
  | "counter_positioning"
  | "switching_costs"
  | "branding"
  | "cornered_resource"
  | "process_power";

type Classification = "wide" | "narrow" | "none";

interface Power {
  power: PowerName;
  score: number;
  rationale: string;
  evidence_quote: string | null;
}

interface MoatAnalysisCardProps {
  entity_name: string;
  ticker: string;
  filing_date: string;
  accession_number: string;
  filing_url: string;
  powers: Power[];
  overall_moat_score: number;
  moat_classification: Classification;
  primary_powers: PowerName[];
  thesis_one_liner: string;
  demoted_power_count?: number;
  confidence: number;
}

const POWER_META: Record<
  PowerName,
  { label: string; icon: React.ComponentType<{ className?: string }>; tone: string }
> = {
  scale_economies: {
    label: "Scale economies",
    icon: TrendingUp,
    tone: "text-blue-700 dark:text-blue-400",
  },
  network_effects: {
    label: "Network effects",
    icon: Globe,
    tone: "text-purple-700 dark:text-purple-400",
  },
  counter_positioning: {
    label: "Counter-positioning",
    icon: Sparkles,
    tone: "text-cyan-700 dark:text-cyan-400",
  },
  switching_costs: {
    label: "Switching costs",
    icon: Lock,
    tone: "text-orange-700 dark:text-orange-400",
  },
  branding: {
    label: "Branding",
    icon: Award,
    tone: "text-rose-700 dark:text-rose-400",
  },
  cornered_resource: {
    label: "Cornered resource",
    icon: Gem,
    tone: "text-amber-700 dark:text-amber-400",
  },
  process_power: {
    label: "Process power",
    icon: Cog,
    tone: "text-slate-700 dark:text-slate-400",
  },
};

function classificationTheme(c: Classification) {
  switch (c) {
    case "wide":
      return {
        ring: "ring-emerald-500/30",
        bg: "bg-emerald-500/10",
        text: "text-emerald-700 dark:text-emerald-400",
        dot: "bg-emerald-500",
        label: "Wide moat",
      };
    case "narrow":
      return {
        ring: "ring-amber-500/30",
        bg: "bg-amber-500/10",
        text: "text-amber-700 dark:text-amber-400",
        dot: "bg-amber-500",
        label: "Narrow moat",
      };
    case "none":
      return {
        ring: "ring-slate-500/20",
        bg: "bg-slate-500/10",
        text: "text-slate-700 dark:text-slate-400",
        dot: "bg-slate-500",
        label: "No moat",
      };
  }
}

function scoreBarColor(score: number): string {
  if (score >= 7) return "bg-emerald-500";
  if (score >= 5) return "bg-amber-500";
  if (score >= 3) return "bg-slate-400";
  return "bg-slate-300 dark:bg-slate-700";
}

function PowerRow({ p, isPrimary }: { p: Power; isPrimary: boolean }) {
  const meta = POWER_META[p.power];
  const Icon = meta.icon;
  const widthPct = Math.min(100, Math.max(0, (p.score / 10) * 100));
  const isDemoted = p.score === 0 && p.rationale.startsWith("[demoted]");

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          <Icon className={cn("h-3 w-3 flex-shrink-0", meta.tone)} />
          <p
            className={cn(
              "text-[12px] truncate",
              isPrimary ? "font-semibold" : "font-medium"
            )}
          >
            {meta.label}
          </p>
          {isPrimary && (
            <span className="text-[9px] uppercase tracking-wider px-1 h-4 inline-flex items-center rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-500/20">
              primary
            </span>
          )}
        </div>
        <span
          className={cn(
            "font-mono text-[11px] tabular-nums font-semibold",
            isDemoted && "text-muted-foreground/60 line-through"
          )}
        >
          {p.score.toFixed(1)}
          <span className="text-muted-foreground/60 font-normal">/10</span>
        </span>
      </div>

      <div className="relative h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-full transition-all",
            scoreBarColor(p.score)
          )}
          style={{ width: `${widthPct}%` }}
        />
      </div>

      {p.score > 0 && (
        <p className="text-[11px] text-muted-foreground leading-relaxed pt-0.5">
          {p.rationale}
        </p>
      )}

      {p.evidence_quote && (
        <blockquote className="text-[10.5px] leading-relaxed italic text-foreground/70 border-l-2 border-muted-foreground/30 pl-2 inline-flex gap-1.5 mt-1">
          <Quote className="h-2.5 w-2.5 mt-0.5 flex-shrink-0 text-muted-foreground/60" />
          <span>&ldquo;{p.evidence_quote}&rdquo;</span>
        </blockquote>
      )}
    </div>
  );
}

export default function MoatAnalysisCard({
  entity_name,
  filing_date,
  accession_number,
  filing_url,
  powers,
  overall_moat_score,
  moat_classification,
  primary_powers,
  thesis_one_liner,
  demoted_power_count,
  confidence,
}: MoatAnalysisCardProps) {
  const theme = classificationTheme(moat_classification);
  const confidencePct = Math.round(confidence * 100);
  const overallPct = Math.min(100, Math.max(0, (overall_moat_score / 10) * 100));
  const primarySet = new Set(primary_powers);

  // Sort powers by score descending for the list
  const sortedPowers = [...powers].sort((a, b) => b.score - a.score);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Castle className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Economic moat · 7 Powers
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {entity_name} · Item 1 Business · filed {filing_date}
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
              {theme.label}
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Overall score + thesis */}
        <div className="rounded-xl border bg-muted/20 p-3.5 space-y-2.5">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-[10.5px] uppercase tracking-wider font-medium text-muted-foreground">
              Overall moat strength (max of 7 powers)
            </p>
            <span className="font-mono font-semibold text-[16px] tabular-nums">
              {overall_moat_score.toFixed(1)}
              <span className="text-muted-foreground/60 font-normal text-[12px]">
                /10
              </span>
            </span>
          </div>
          <div className="relative h-2 rounded-full bg-muted overflow-hidden">
            <div
              className={cn(
                "absolute inset-y-0 left-0 rounded-full transition-all",
                scoreBarColor(overall_moat_score)
              )}
              style={{ width: `${overallPct}%` }}
            />
          </div>
          <p className="text-[12.5px] leading-relaxed text-foreground/90 pt-1">
            {thesis_one_liner}
          </p>
        </div>

        {/* 7 powers list */}
        <div className="space-y-3.5">
          <p className="text-[10.5px] uppercase tracking-wider font-medium text-muted-foreground">
            Power-by-power scoring
          </p>
          {sortedPowers.map((p) => (
            <PowerRow key={p.power} p={p} isPrimary={primarySet.has(p.power)} />
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground/80 pt-1">
          <span className="italic">
            Hamilton Helmer&rsquo;s 7 Powers framework. Quotes verified verbatim
            {typeof demoted_power_count === "number" && demoted_power_count > 0
              ? ` (${demoted_power_count} unverifiable claim${demoted_power_count > 1 ? "s" : ""} demoted)`
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
