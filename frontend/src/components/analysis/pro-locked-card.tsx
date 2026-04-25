"use client";

/**
 * Shared "locked preview" card emitted by all Pro-only nodes when the
 * caller is on the free tier. Each Pro node emits its own
 * ``<feature>_locked_card`` component_type, all of which the registry maps
 * to a thin specialization that pre-fills ``feature_label`` /
 * ``locked_icon`` and renders this same component.
 *
 * The card shows what the Pro feature would deliver and a CTA to upgrade.
 * Once auth + Stripe (Phase 2-F) is wired, "Upgrade" goes to the checkout
 * flow; today it links to a mailto/contact to surface manual promotion.
 */

import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Lock, Sparkles, ArrowRight } from "lucide-react";

interface ProLockedCardProps {
  /** Human-readable label for the gated feature, e.g. "Investment thesis". */
  feature_label: string;
  entity_name?: string | null;
  ticker?: string | null;
  /** Optional teaser values some Pro nodes pass through. */
  preview_signal?: string | null;
  preview_margin_of_safety_pct?: number | null;
  /** Stable reason code from the backend; "pro_required" today. */
  locked_reason?: string;
}

const FEATURE_BENEFITS: Record<string, string[]> = {
  "Investment thesis": [
    "Multi-paragraph research narrative grounded in your numbers",
    "Bull / bear / risk breakdown with explicit recommendation",
    "Confidence-scored output ready for client distribution",
  ],
  "10-K MD&A + Risk Factors analysis": [
    "Management tone, forward guidance, growth drivers",
    "Top 5 risks ranked by severity with verbatim citations",
    "Auditable quotes — every claim links back to the SEC filing",
  ],
  "Year-over-year 10-K risk diff": [
    "What's NEW in this year's risk factors vs. last year",
    "Escalated and de-escalated wording with side-by-side quotes",
    "Critical signal investors miss in routine 10-K reads",
  ],
  "Moat / 7 Powers scoring": [
    "Score on each Helmer power with verbatim evidence",
    "Wide / narrow / no-moat classification + thesis one-liner",
    "Hallucinated claims auto-demoted to keep scoring honest",
  ],
};

export default function ProLockedCard({
  feature_label,
  entity_name,
  ticker,
  preview_signal,
  preview_margin_of_safety_pct,
}: ProLockedCardProps) {
  const benefits = FEATURE_BENEFITS[feature_label] ?? [];

  return (
    <Card className="relative overflow-hidden">
      {/* Decorative gradient background */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at top right, oklch(0.93 0.04 270 / 0.4), transparent 60%)",
        }}
      />
      <CardHeader className="relative pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
              <Lock className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-[14px] font-semibold inline-flex items-center gap-1.5">
                {feature_label}
                <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 h-4 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 ring-1 ring-amber-500/20">
                  <Sparkles className="h-2 w-2" />
                  Pro
                </span>
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                {entity_name ?? ticker ?? "Locked feature preview"}
              </p>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="relative space-y-4">
        {/* Free-tier teaser when available */}
        {(preview_signal || preview_margin_of_safety_pct != null) && (
          <div className="rounded-xl border bg-muted/40 p-3">
            <p className="text-[10.5px] uppercase tracking-wider font-medium text-muted-foreground mb-1.5">
              Free-tier preview
            </p>
            <div className="flex items-center gap-3 text-[12px]">
              {preview_signal && (
                <span>
                  Signal:{" "}
                  <span className="font-semibold">{preview_signal}</span>
                </span>
              )}
              {typeof preview_margin_of_safety_pct === "number" && (
                <span>
                  Margin of safety:{" "}
                  <span
                    className={cn(
                      "font-mono font-semibold tabular-nums",
                      preview_margin_of_safety_pct >= 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-red-600 dark:text-red-400"
                    )}
                  >
                    {preview_margin_of_safety_pct > 0 ? "+" : ""}
                    {preview_margin_of_safety_pct.toFixed(1)}%
                  </span>
                </span>
              )}
            </div>
          </div>
        )}

        {/* What Pro unlocks */}
        {benefits.length > 0 && (
          <ul className="space-y-1.5">
            {benefits.map((b, idx) => (
              <li
                key={idx}
                className="text-[12px] leading-relaxed flex gap-2 text-foreground/85"
              >
                <span className="mt-[7px] h-1 w-1 rounded-full flex-shrink-0 bg-amber-500" />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        )}

        {/* Upgrade CTA */}
        <div className="rounded-xl border-2 border-dashed border-amber-500/30 bg-amber-500/5 p-3.5 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[12.5px] font-semibold leading-snug">
              Unlock {feature_label.toLowerCase()} with AlphaQuant Pro
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              All four LLM-powered Pro features included.
            </p>
          </div>
          <Link href="/account/upgrade">
            <Button size="sm" className="flex-shrink-0">
              Upgrade
              <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
