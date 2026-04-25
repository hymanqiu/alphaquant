"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  GitCompare,
  ExternalLink,
  Plus,
  Minus,
  ArrowUp,
  ArrowDown,
  ArrowRight,
} from "lucide-react";

type Category =
  | "regulatory"
  | "competitive"
  | "operational"
  | "financial"
  | "macro"
  | "technology"
  | "legal"
  | "concentration";

type ChangeKind = "new" | "removed" | "escalated" | "de_escalated";

interface RiskChange {
  kind: ChangeKind;
  category: Category;
  title: string;
  description: string;
  quote_current: string | null;
  quote_prior: string | null;
}

interface FilingRef {
  filing_date: string;
  accession_number: string;
  url: string;
}

interface RiskYoYDiffCardProps {
  entity_name: string;
  ticker: string;
  current_filing: FilingRef;
  prior_filing: FilingRef;
  summary: string;
  new_risks: RiskChange[];
  removed_risks: RiskChange[];
  escalated_risks: RiskChange[];
  de_escalated_risks: RiskChange[];
  rejected_change_count?: number;
  confidence: number;
}

const KIND_META: Record<
  ChangeKind,
  {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badgeBg: string;
    badgeText: string;
    badgeRing: string;
    dot: string;
  }
> = {
  new: {
    label: "New",
    icon: Plus,
    badgeBg: "bg-red-500/10",
    badgeText: "text-red-700 dark:text-red-400",
    badgeRing: "ring-red-500/30",
    dot: "bg-red-500",
  },
  removed: {
    label: "Removed",
    icon: Minus,
    badgeBg: "bg-slate-500/10",
    badgeText: "text-slate-700 dark:text-slate-400",
    badgeRing: "ring-slate-500/30",
    dot: "bg-slate-500",
  },
  escalated: {
    label: "Escalated",
    icon: ArrowUp,
    badgeBg: "bg-amber-500/10",
    badgeText: "text-amber-700 dark:text-amber-400",
    badgeRing: "ring-amber-500/30",
    dot: "bg-amber-500",
  },
  de_escalated: {
    label: "De-escalated",
    icon: ArrowDown,
    badgeBg: "bg-emerald-500/10",
    badgeText: "text-emerald-700 dark:text-emerald-400",
    badgeRing: "ring-emerald-500/30",
    dot: "bg-emerald-500",
  },
};

function ChangeQuoteBlock({
  label,
  quote,
  filing,
}: {
  label: string;
  quote: string | null;
  filing: FilingRef;
}) {
  if (!quote) return null;
  return (
    <div className="space-y-1">
      <p className="text-[9.5px] uppercase tracking-wider font-medium text-muted-foreground">
        {label} · filed {filing.filing_date}
      </p>
      <blockquote className="text-[11.5px] leading-relaxed italic text-foreground/80 border-l-2 border-muted-foreground/30 pl-2.5">
        &ldquo;{quote}&rdquo;
      </blockquote>
    </div>
  );
}

function ChangeItem({
  change,
  current_filing,
  prior_filing,
}: {
  change: RiskChange;
  current_filing: FilingRef;
  prior_filing: FilingRef;
}) {
  const meta = KIND_META[change.kind];
  const KindIcon = meta.icon;

  const showSideBySide =
    change.kind === "escalated" || change.kind === "de_escalated";

  return (
    <li className="rounded-xl border bg-muted/30 p-3 space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] font-semibold leading-snug">
            {change.title}
          </p>
          <p className="text-[10px] text-muted-foreground capitalize mt-0.5">
            {change.category}
          </p>
        </div>
        <div
          className={cn(
            "inline-flex items-center gap-1 px-2 h-5 rounded-full text-[10px] font-medium ring-1 flex-shrink-0",
            meta.badgeBg,
            meta.badgeText,
            meta.badgeRing
          )}
        >
          <KindIcon className="h-2.5 w-2.5" />
          {meta.label}
        </div>
      </div>

      <p className="text-[12px] leading-relaxed text-foreground/90">
        {change.description}
      </p>

      {showSideBySide ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          <ChangeQuoteBlock
            label="Prior wording"
            quote={change.quote_prior}
            filing={prior_filing}
          />
          <div className="hidden md:flex items-center justify-center -mx-1.5">
            <ArrowRight className="h-3 w-3 text-muted-foreground/60" />
          </div>
          <ChangeQuoteBlock
            label="Current wording"
            quote={change.quote_current}
            filing={current_filing}
          />
        </div>
      ) : change.kind === "new" ? (
        <ChangeQuoteBlock
          label="Quote from current filing"
          quote={change.quote_current}
          filing={current_filing}
        />
      ) : (
        <ChangeQuoteBlock
          label="Quote from prior filing"
          quote={change.quote_prior}
          filing={prior_filing}
        />
      )}
    </li>
  );
}

function ChangeBucket({
  title,
  items,
  kind,
  current_filing,
  prior_filing,
}: {
  title: string;
  items: RiskChange[];
  kind: ChangeKind;
  current_filing: FilingRef;
  prior_filing: FilingRef;
}) {
  const meta = KIND_META[kind];
  const Icon = meta.icon;
  return (
    <section className="space-y-2">
      <div className="flex items-center gap-1.5">
        <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
        <h3
          className={cn(
            "text-[10.5px] uppercase tracking-wider font-semibold inline-flex items-center gap-1",
            meta.badgeText
          )}
        >
          <Icon className="h-2.5 w-2.5" />
          {title}
          <span className="text-muted-foreground tabular-nums font-normal">
            ({items.length})
          </span>
        </h3>
      </div>
      {items.length === 0 ? (
        <p className="text-[11px] text-muted-foreground italic pl-3">
          None identified.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((c, idx) => (
            <ChangeItem
              key={idx}
              change={c}
              current_filing={current_filing}
              prior_filing={prior_filing}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

export default function RiskYoYDiffCard({
  entity_name,
  current_filing,
  prior_filing,
  summary,
  new_risks,
  removed_risks,
  escalated_risks,
  de_escalated_risks,
  rejected_change_count,
  confidence,
}: RiskYoYDiffCardProps) {
  const confidencePct = Math.round(confidence * 100);
  const totalChanges =
    new_risks.length +
    removed_risks.length +
    escalated_risks.length +
    de_escalated_risks.length;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <GitCompare className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold">
                Year-over-year risk shift
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {entity_name} · {prior_filing.filing_date} → {current_filing.filing_date}
              </p>
            </div>
          </div>
          <span className="text-[10.5px] text-muted-foreground tabular-nums">
            {confidencePct}% confidence
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Top-line summary */}
        <div className="rounded-xl border bg-muted/20 p-3.5">
          <p className="text-[10.5px] uppercase tracking-wider font-medium text-muted-foreground mb-1.5">
            What changed
          </p>
          <p className="text-[12.5px] leading-relaxed text-foreground/90">
            {summary}
          </p>
        </div>

        {totalChanges === 0 ? (
          <p className="text-[12px] text-muted-foreground italic">
            No material year-over-year changes identified after verbatim-quote
            verification.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-4">
            <ChangeBucket
              title="Newly added"
              kind="new"
              items={new_risks}
              current_filing={current_filing}
              prior_filing={prior_filing}
            />
            <ChangeBucket
              title="Escalated"
              kind="escalated"
              items={escalated_risks}
              current_filing={current_filing}
              prior_filing={prior_filing}
            />
            <ChangeBucket
              title="Removed"
              kind="removed"
              items={removed_risks}
              current_filing={current_filing}
              prior_filing={prior_filing}
            />
            <ChangeBucket
              title="De-escalated"
              kind="de_escalated"
              items={de_escalated_risks}
              current_filing={current_filing}
              prior_filing={prior_filing}
            />
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground/80 pt-1">
          <span className="italic">
            Both quotes verified verbatim against their year's 10-K
            {typeof rejected_change_count === "number" && rejected_change_count > 0
              ? ` (${rejected_change_count} unverifiable changes dropped)`
              : ""}
            .
          </span>
          <div className="flex items-center gap-3">
            <a
              href={prior_filing.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[var(--brand)] hover:underline"
              title={prior_filing.accession_number}
            >
              prior 10-K <ExternalLink className="h-2.5 w-2.5" />
            </a>
            <a
              href={current_filing.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[var(--brand)] hover:underline"
              title={current_filing.accession_number}
            >
              current 10-K <ExternalLink className="h-2.5 w-2.5" />
            </a>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
