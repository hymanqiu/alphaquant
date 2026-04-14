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
};

export function getComponent(type: string): ComponentType<any> | null {
  return registry[type] ?? null;
}
