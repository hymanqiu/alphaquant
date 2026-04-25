import { lazy, type ComponentType } from "react";

/* eslint-disable @typescript-eslint/no-explicit-any */
const registry: Record<string, ComponentType<any>> = {
  metric_table: lazy(() => import("./analysis/metric-table")),
  revenue_chart: lazy(() => import("./analysis/revenue-chart")),
  fcf_chart: lazy(() => import("./analysis/fcf-chart")),
  financial_health_card: lazy(() => import("./analysis/financial-health-card")),
  dcf_result_card: lazy(() => import("./analysis/dcf-result-card")),
  valuation_gauge: lazy(() => import("./analysis/valuation-gauge")),
  assumption_slider: lazy(() => import("./analysis/assumption-slider")),
  strategy_dashboard: lazy(() => import("./analysis/strategy-dashboard")),
  source_table: lazy(() => import("./analysis/source-table")),
  relative_valuation_card: lazy(() => import("./analysis/relative-valuation-card")),
  sentiment_card: lazy(() => import("./analysis/sentiment-card")),
  event_impact_card: lazy(() => import("./analysis/event-impact-card")),
  investment_thesis_card: lazy(() => import("./analysis/investment-thesis-card")),
  qualitative_insights_card: lazy(() => import("./analysis/qualitative-insights-card")),
  risk_factors_card: lazy(() => import("./analysis/risk-factors-card")),
  risk_yoy_diff_card: lazy(() => import("./analysis/risk-yoy-diff-card")),
  moat_analysis_card: lazy(() => import("./analysis/moat-analysis-card")),
  // Pro-locked teasers — emitted by Pro nodes for free-tier users.
  // All four point at the same shared component; the backend pre-fills
  // ``feature_label`` so the component knows which Pro feature is locked.
  investment_thesis_locked_card: lazy(() => import("./analysis/pro-locked-card")),
  qualitative_locked_card: lazy(() => import("./analysis/pro-locked-card")),
  risk_yoy_diff_locked_card: lazy(() => import("./analysis/pro-locked-card")),
  moat_locked_card: lazy(() => import("./analysis/pro-locked-card")),
};

export function getComponent(type: string): ComponentType<any> | null {
  return registry[type] ?? null;
}
