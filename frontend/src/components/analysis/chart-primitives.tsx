"use client";

import type { ReactNode } from "react";

/** Format a dollar value compactly (e.g. $1.2B, $450M). */
export function formatCompactDollar(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(0)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

interface TooltipRow {
  label: string;
  value: string;
  color?: string;
  muted?: boolean;
}

interface GlassTooltipProps {
  title?: ReactNode;
  rows: TooltipRow[];
}

/** Glass-style tooltip used by Recharts charts. */
export function GlassTooltip({ title, rows }: GlassTooltipProps) {
  return (
    <div className="chart-tooltip text-[11px] min-w-[140px]">
      {title && (
        <div className="text-muted-foreground/80 font-medium mb-1.5">
          {title}
        </div>
      )}
      <div className="space-y-1">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-1.5">
              {r.color && (
                <span
                  className="h-2 w-2 rounded-sm shrink-0"
                  style={{ backgroundColor: r.color }}
                />
              )}
              <span
                className={
                  r.muted ? "text-muted-foreground" : "text-foreground"
                }
              >
                {r.label}
              </span>
            </span>
            <span className="font-mono font-semibold tabular-nums">
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Shared axis tick style props for Recharts. */
export const axisTickStyle = {
  fill: "var(--muted-foreground)",
  fontSize: 11,
  fontFamily: "var(--font-mono, ui-monospace, monospace)",
};

/** Base cartesian grid props for a subtle, modern feel. */
export const gridProps = {
  strokeDasharray: "3 5",
  stroke: "var(--border)",
  strokeOpacity: 0.7,
  vertical: false,
};
