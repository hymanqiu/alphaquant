"use client";

import { useMemo } from "react";
import { ShieldAlert, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ComponentInstruction, SSEStatus } from "@/lib/types";

interface VerdictHeroProps {
  ticker: string;
  components: ComponentInstruction[];
  status: SSEStatus;
  onJumpToTab?: (tab: "risks") => void;
}

type SignalKind = "buy" | "hold" | "reduce" | "sell";

interface HeroFields {
  entityName: string | null;
  signalLabel: string | null;
  signalKind: SignalKind | null;
  marginOfSafety: number | null;
  upside: number | null;
  currentPrice: number | null;
  intrinsicValue: number | null;
  suggestedEntry: number | null;
  confidence: number | null;
  thesisHeadline: string | null;
  highSeverityRiskCount: number;
  totalRisksReported: boolean;
}

function recToKind(rec: string): SignalKind {
  if (rec === "Strong Buy" || rec === "Buy") return "buy";
  if (rec === "Hold") return "hold";
  if (rec === "Reduce") return "reduce";
  return "sell";
}

function strategyToKind(s: string): SignalKind {
  if (s === "Deep Value" || s === "Undervalued") return "buy";
  if (s === "Fair Value") return "hold";
  return "sell";
}

function deriveHero(components: ComponentInstruction[]): HeroFields {
  const fields: HeroFields = {
    entityName: null,
    signalLabel: null,
    signalKind: null,
    marginOfSafety: null,
    upside: null,
    currentPrice: null,
    intrinsicValue: null,
    suggestedEntry: null,
    confidence: null,
    thesisHeadline: null,
    highSeverityRiskCount: 0,
    totalRisksReported: false,
  };

  for (const c of components) {
    const p = c.props as Record<string, unknown>;
    switch (c.component_type) {
      case "investment_thesis_card": {
        const rec = p.recommendation as string | undefined;
        if (rec) {
          fields.signalLabel = rec;
          fields.signalKind = recToKind(rec);
        }
        if (typeof p.confidence === "number") fields.confidence = p.confidence;
        if (typeof p.thesis_headline === "string") fields.thesisHeadline = p.thesis_headline;
        if (typeof p.entity_name === "string" && !fields.entityName) fields.entityName = p.entity_name;
        break;
      }
      case "strategy_dashboard": {
        const sig = p.signal as string | undefined;
        if (sig && !fields.signalLabel) {
          fields.signalLabel = sig;
          fields.signalKind = strategyToKind(sig);
        }
        if (typeof p.margin_of_safety_pct === "number") fields.marginOfSafety = p.margin_of_safety_pct;
        if (typeof p.upside_pct === "number") fields.upside = p.upside_pct;
        if (typeof p.current_price === "number") fields.currentPrice = p.current_price;
        if (typeof p.intrinsic_value === "number") fields.intrinsicValue = p.intrinsic_value;
        if (typeof p.suggested_entry_price === "number") fields.suggestedEntry = p.suggested_entry_price;
        if (typeof p.entity_name === "string" && !fields.entityName) fields.entityName = p.entity_name;
        break;
      }
      case "risk_factors_card": {
        fields.totalRisksReported = true;
        const top = (p.top_risks ?? []) as Array<{ severity?: string }>;
        fields.highSeverityRiskCount = top.filter((r) => r.severity === "high").length;
        break;
      }
      case "valuation_gauge": {
        if (typeof p.intrinsic_value === "number" && fields.intrinsicValue == null)
          fields.intrinsicValue = p.intrinsic_value;
        if (typeof p.entity_name === "string" && !fields.entityName) fields.entityName = p.entity_name;
        break;
      }
    }
  }
  return fields;
}

function signalTheme(kind: SignalKind | null) {
  if (!kind) {
    return { bg: "bg-muted", ring: "ring-border", text: "text-muted-foreground", dot: "bg-muted-foreground/40" };
  }
  switch (kind) {
    case "buy":
      return {
        bg: "bg-emerald-500/12",
        ring: "ring-emerald-500/30",
        text: "text-emerald-700 dark:text-emerald-400",
        dot: "bg-emerald-500",
      };
    case "hold":
      return {
        bg: "bg-amber-500/12",
        ring: "ring-amber-500/30",
        text: "text-amber-700 dark:text-amber-400",
        dot: "bg-amber-500",
      };
    case "reduce":
      return {
        bg: "bg-orange-500/12",
        ring: "ring-orange-500/30",
        text: "text-orange-700 dark:text-orange-400",
        dot: "bg-orange-500",
      };
    case "sell":
      return {
        bg: "bg-red-500/12",
        ring: "ring-red-500/30",
        text: "text-red-700 dark:text-red-400",
        dot: "bg-red-500",
      };
  }
}

function confidenceLabel(c: number | null): { text: string; tone: string } {
  if (c == null) return { text: "—", tone: "text-muted-foreground" };
  const pct = Math.round(c * 100);
  if (c >= 0.7) return { text: `${pct}% · High`, tone: "text-emerald-600 dark:text-emerald-400" };
  if (c >= 0.45) return { text: `${pct}% · Med`, tone: "text-amber-600 dark:text-amber-400" };
  return { text: `${pct}% · Low`, tone: "text-orange-600 dark:text-orange-400" };
}

function HeroChip({
  label,
  value,
  valueClass,
  pulse = false,
}: {
  label: string;
  value: string;
  valueClass?: string;
  pulse?: boolean;
}) {
  return (
    <div className="rounded-xl border bg-card/60 px-3 py-2 min-w-0">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p
        className={cn(
          "font-mono font-semibold text-[18px] tabular-nums leading-tight mt-0.5",
          valueClass,
          pulse && "animate-pulse"
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function VerdictHero({ ticker, components, status, onJumpToTab }: VerdictHeroProps) {
  const f = useMemo(() => deriveHero(components), [components]);
  const isStreaming = status === "connecting" || status === "connected";
  const theme = signalTheme(f.signalKind);
  const conf = confidenceLabel(f.confidence);

  const mosClass =
    f.marginOfSafety == null
      ? "text-muted-foreground"
      : f.marginOfSafety >= 0
      ? "text-emerald-600 dark:text-emerald-400"
      : "text-red-600 dark:text-red-400";

  const fmtPct = (n: number | null) =>
    n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
  const fmtPrice = (n: number | null) => (n == null ? "—" : `$${n.toFixed(2)}`);

  return (
    <div className="shrink-0 bg-background/85 backdrop-blur-md border-b">
      <div className="max-w-5xl mx-auto px-6 py-4 space-y-3">
        {/* Top row: ticker + entity */}
        <div className="flex items-baseline gap-2.5 min-w-0">
          <span className="font-mono font-bold text-[18px] tracking-tight">{ticker}</span>
          {f.entityName && (
            <span className="text-[12px] text-muted-foreground truncate">· {f.entityName}</span>
          )}
          {f.currentPrice != null && (
            <span className="ml-auto font-mono text-[13px] tabular-nums text-foreground/80">
              {fmtPrice(f.currentPrice)}
              <span className="text-[11px] text-muted-foreground ml-1">market</span>
            </span>
          )}
        </div>

        {/* Stats row: signal · MoS · confidence · risks */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
          {/* Signal pill */}
          <div
            className={cn(
              "rounded-xl ring-1 px-3 py-2 flex items-center gap-2 min-w-0",
              theme.bg,
              theme.ring,
              theme.text,
              !f.signalLabel && "animate-pulse"
            )}
          >
            <span className={cn("h-2 w-2 rounded-full shrink-0", theme.dot)} />
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wider opacity-80">Signal</p>
              <p className="font-semibold text-[15px] truncate">{f.signalLabel ?? "Analyzing…"}</p>
            </div>
          </div>

          {/* Margin of safety */}
          <HeroChip
            label="Margin of safety"
            value={fmtPct(f.marginOfSafety)}
            valueClass={mosClass}
            pulse={f.marginOfSafety == null}
          />

          {/* Confidence */}
          <HeroChip
            label="Confidence"
            value={conf.text}
            valueClass={cn("text-[14px]", conf.tone)}
            pulse={f.confidence == null && isStreaming}
          />

          {/* Risk badge — clickable to risks tab */}
          <button
            type="button"
            onClick={() => onJumpToTab?.("risks")}
            disabled={!f.totalRisksReported}
            className={cn(
              "rounded-xl border px-3 py-2 text-left transition-colors min-w-0",
              f.highSeverityRiskCount > 0
                ? "bg-red-500/8 border-red-500/30 hover:bg-red-500/12"
                : f.totalRisksReported
                ? "bg-emerald-500/8 border-emerald-500/25"
                : "bg-card/60 animate-pulse",
              f.totalRisksReported ? "cursor-pointer" : "cursor-default"
            )}
            title={f.totalRisksReported ? "Jump to Risks & Moat tab" : undefined}
          >
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground inline-flex items-center gap-1">
              <ShieldAlert className="h-2.5 w-2.5" />
              Material risks
            </p>
            <p
              className={cn(
                "font-mono font-semibold text-[16px] tabular-nums leading-tight mt-0.5 inline-flex items-center gap-1",
                f.highSeverityRiskCount > 0
                  ? "text-red-600 dark:text-red-400"
                  : f.totalRisksReported
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-muted-foreground"
              )}
            >
              {f.totalRisksReported ? (
                <>
                  {f.highSeverityRiskCount} high
                  {f.totalRisksReported && f.highSeverityRiskCount > 0 && (
                    <ArrowRight className="h-3 w-3 opacity-70" />
                  )}
                </>
              ) : (
                "—"
              )}
            </p>
          </button>
        </div>

        {/* Thesis headline */}
        {(f.thesisHeadline || isStreaming) && (
          <p
            className={cn(
              "text-[13px] leading-snug text-foreground/90",
              !f.thesisHeadline && "italic text-muted-foreground animate-pulse"
            )}
          >
            {f.thesisHeadline ?? "Synthesizing thesis…"}
          </p>
        )}

        {/* Entry/exit strip */}
        {(f.suggestedEntry != null || f.intrinsicValue != null) && (
          <div className="flex items-center gap-3 text-[11.5px] text-muted-foreground font-mono tabular-nums pt-0.5">
            {f.suggestedEntry != null && (
              <span>
                <span className="opacity-70">Buy &lt;</span>{" "}
                <span className="text-foreground/90 font-semibold">{fmtPrice(f.suggestedEntry)}</span>
              </span>
            )}
            {f.intrinsicValue != null && (
              <>
                <span className="opacity-40">·</span>
                <span>
                  <span className="opacity-70">IV</span>{" "}
                  <span className="text-foreground/90 font-semibold">{fmtPrice(f.intrinsicValue)}</span>
                </span>
              </>
            )}
            {f.upside != null && (
              <>
                <span className="opacity-40">·</span>
                <span>
                  <span className="opacity-70">Upside</span>{" "}
                  <span
                    className={cn(
                      "font-semibold",
                      f.upside >= 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-red-600 dark:text-red-400"
                    )}
                  >
                    {fmtPct(f.upside)}
                  </span>
                </span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
