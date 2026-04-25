"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  ShieldAlert,
  ExternalLink,
  Quote,
  Scale,
  Users,
  Cog,
  Coins,
  Globe2,
  Cpu,
  Gavel,
  Target,
} from "lucide-react";

type Severity = "high" | "medium" | "low";

type Category =
  | "regulatory"
  | "competitive"
  | "operational"
  | "financial"
  | "macro"
  | "technology"
  | "legal"
  | "concentration";

interface TopRisk {
  category: Category;
  title: string;
  description: string;
  severity: Severity;
  quote: string;
}

interface RiskFactorsCardProps {
  entity_name: string;
  ticker: string;
  filing_date: string;
  accession_number: string;
  filing_url: string;
  risk_categories: Partial<Record<Category, number>>;
  top_risks: TopRisk[];
  concentration_risk: string | null;
  rejected_risk_count?: number;
  confidence: number;
  risk_char_count?: number;
  parser_strategy?: string;
}

const CATEGORY_META: Record<
  Category,
  { label: string; icon: React.ComponentType<{ className?: string }>; tone: string }
> = {
  regulatory: { label: "Regulatory", icon: Scale, tone: "text-blue-700 dark:text-blue-400" },
  competitive: { label: "Competitive", icon: Users, tone: "text-purple-700 dark:text-purple-400" },
  operational: { label: "Operational", icon: Cog, tone: "text-slate-700 dark:text-slate-400" },
  financial: { label: "Financial", icon: Coins, tone: "text-emerald-700 dark:text-emerald-400" },
  macro: { label: "Macro", icon: Globe2, tone: "text-amber-700 dark:text-amber-400" },
  technology: { label: "Technology", icon: Cpu, tone: "text-cyan-700 dark:text-cyan-400" },
  legal: { label: "Legal", icon: Gavel, tone: "text-rose-700 dark:text-rose-400" },
  concentration: { label: "Concentration", icon: Target, tone: "text-orange-700 dark:text-orange-400" },
};

function severityTheme(severity: Severity) {
  switch (severity) {
    case "high":
      return {
        ring: "ring-red-500/30",
        bg: "bg-red-500/10",
        text: "text-red-700 dark:text-red-400",
        dot: "bg-red-500",
        label: "High",
      };
    case "medium":
      return {
        ring: "ring-amber-500/30",
        bg: "bg-amber-500/10",
        text: "text-amber-700 dark:text-amber-400",
        dot: "bg-amber-500",
        label: "Medium",
      };
    case "low":
      return {
        ring: "ring-slate-500/20",
        bg: "bg-slate-500/10",
        text: "text-slate-700 dark:text-slate-400",
        dot: "bg-slate-500",
        label: "Low",
      };
  }
}

export default function RiskFactorsCard({
  entity_name,
  filing_date,
  accession_number,
  filing_url,
  risk_categories,
  top_risks,
  concentration_risk,
  rejected_risk_count,
  confidence,
}: RiskFactorsCardProps) {
  const confidencePct = Math.round(confidence * 100);

  const categoryEntries = (Object.entries(risk_categories) as [Category, number][])
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <ShieldAlert className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                10-K Risk factors
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {entity_name} · Item 1A · filed {filing_date}
              </p>
            </div>
          </div>
          <span className="text-[10.5px] text-muted-foreground tabular-nums">
            {confidencePct}% confidence
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Category taxonomy */}
        {categoryEntries.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10.5px] uppercase tracking-wider font-medium text-muted-foreground">
              Risk taxonomy
            </p>
            <div className="flex flex-wrap gap-1.5">
              {categoryEntries.map(([cat, count]) => {
                const meta = CATEGORY_META[cat];
                const Icon = meta.icon;
                return (
                  <div
                    key={cat}
                    className={cn(
                      "inline-flex items-center gap-1.5 px-2 h-6 rounded-full text-[11px] font-medium bg-muted/60 ring-1 ring-border",
                      meta.tone
                    )}
                  >
                    <Icon className="h-2.5 w-2.5" />
                    {meta.label}
                    <span className="tabular-nums text-muted-foreground">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Concentration callout */}
        {concentration_risk && (
          <div className="rounded-xl border bg-orange-500/5 ring-1 ring-orange-500/20 p-3">
            <p className="text-[10.5px] uppercase tracking-wider font-medium text-orange-700 dark:text-orange-400 mb-1 inline-flex items-center gap-1.5">
              <Target className="h-2.5 w-2.5" />
              Concentration risk
            </p>
            <p className="text-[12px] leading-relaxed text-foreground/90">
              {concentration_risk}
            </p>
          </div>
        )}

        {/* Top risks list */}
        <div className="space-y-2.5">
          <p className="text-[10.5px] uppercase tracking-wider font-medium text-muted-foreground">
            Top risks (by management's own disclosure)
          </p>
          {top_risks.length === 0 ? (
            <p className="text-[11px] text-muted-foreground italic">
              No individual risks passed the verbatim-quote verifier.
            </p>
          ) : (
            <ul className="space-y-2.5">
              {top_risks.map((r, idx) => {
                const sev = severityTheme(r.severity);
                const catMeta = CATEGORY_META[r.category];
                const CatIcon = catMeta?.icon ?? ShieldAlert;
                return (
                  <li
                    key={idx}
                    className="rounded-xl border bg-muted/30 p-3 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <CatIcon
                          className={cn(
                            "h-3 w-3 flex-shrink-0",
                            catMeta?.tone ?? "text-muted-foreground"
                          )}
                        />
                        <p className="text-[12.5px] font-semibold leading-snug truncate">
                          {r.title}
                        </p>
                      </div>
                      <div
                        className={cn(
                          "inline-flex items-center gap-1 px-2 h-5 rounded-full text-[10px] font-medium ring-1 flex-shrink-0",
                          sev.bg,
                          sev.text,
                          sev.ring
                        )}
                      >
                        <span className={cn("h-1 w-1 rounded-full", sev.dot)} />
                        {sev.label}
                      </div>
                    </div>

                    <p className="text-[12px] leading-relaxed text-foreground/90">
                      {r.description}
                    </p>

                    <blockquote className="text-[11.5px] leading-relaxed italic text-foreground/70 border-l-2 border-muted-foreground/30 pl-2.5 inline-flex gap-1.5">
                      <Quote className="h-2.5 w-2.5 mt-0.5 flex-shrink-0 text-muted-foreground/60" />
                      <span>&ldquo;{r.quote}&rdquo;</span>
                    </blockquote>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Footer: provenance */}
        <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground/80">
          <span className="italic">
            LLM extraction from 10-K Item 1A. All quotes verified verbatim
            {typeof rejected_risk_count === "number" && rejected_risk_count > 0
              ? ` (${rejected_risk_count} unverifiable risks dropped)`
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
