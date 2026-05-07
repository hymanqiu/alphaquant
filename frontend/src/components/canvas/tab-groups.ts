import type { ComponentInstruction } from "@/lib/types";

export type TabId = "verdict" | "valuation" | "strategy" | "risks" | "sources";

export const TAB_ORDER: readonly TabId[] = [
  "verdict",
  "valuation",
  "strategy",
  "risks",
  "sources",
] as const;

export const TAB_LABELS: Record<TabId, string> = {
  verdict: "Verdict",
  valuation: "Valuation",
  strategy: "Strategy",
  risks: "Risks & Moat",
  sources: "Sources",
};

const TAB_BY_TYPE: Record<string, TabId> = {
  // Verdict — the answer + recommendation
  investment_thesis_card: "verdict",
  investment_thesis_locked_card: "verdict",
  qualitative_insights_card: "verdict",
  qualitative_locked_card: "verdict",
  strategy_dashboard: "verdict",

  // Valuation — numbers
  dcf_result_card: "valuation",
  valuation_gauge: "valuation",
  assumption_slider: "valuation",
  fcf_chart: "valuation",
  revenue_chart: "valuation",
  relative_valuation_card: "valuation",
  metric_table: "valuation",
  financial_health_card: "valuation",

  // Strategy — timing/sentiment
  sentiment_card: "strategy",
  event_impact_card: "strategy",

  // Risks & Moat
  risk_factors_card: "risks",
  risk_yoy_diff_card: "risks",
  risk_yoy_diff_locked_card: "risks",
  moat_analysis_card: "risks",
  moat_locked_card: "risks",

  // Sources
  source_table: "sources",
};

export function tabFor(componentType: string): TabId {
  return TAB_BY_TYPE[componentType] ?? "sources";
}

export type TabGroups = Record<TabId, ComponentInstruction[]>;

export function groupByTab(components: ComponentInstruction[]): TabGroups {
  const groups: TabGroups = {
    verdict: [],
    valuation: [],
    strategy: [],
    risks: [],
    sources: [],
  };
  for (const c of components) {
    groups[tabFor(c.component_type)].push(c);
  }
  return groups;
}
