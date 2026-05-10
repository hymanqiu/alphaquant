"use client";

import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import { cn } from "@/lib/utils";

interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Props {
  ohlcv: OHLCVBar[];
  ma20: (number | null)[];
}

type Range = "3M" | "6M" | "1Y";

const RANGES: { id: Range; label: string; days: number }[] = [
  { id: "3M", label: "3M", days: 63 },
  { id: "6M", label: "6M", days: 126 },
  { id: "1Y", label: "1Y", days: 252 },
];

// Theme-aware colors read once on mount. We don't auto-react to theme switches
// (would need a MutationObserver on <html>); a page refresh re-applies.
function readChartColors() {
  const isDark =
    typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark");
  return {
    text: isDark ? "rgba(244, 244, 245, 0.55)" : "rgba(63, 63, 70, 0.75)",
    grid: isDark ? "rgba(244, 244, 245, 0.06)" : "rgba(24, 24, 27, 0.06)",
    crosshair: isDark ? "rgba(244, 244, 245, 0.4)" : "rgba(24, 24, 27, 0.35)",
    crosshairLabelBg: isDark ? "rgb(82 82 91)" : "rgb(82 82 91)",
  };
}

export default function PriceChartImpl({ ohlcv, ma20 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [range, setRange] = useState<Range>("1Y");

  useEffect(() => {
    if (!containerRef.current || ohlcv.length === 0) return;
    const container = containerRef.current;
    const colors = readChartColors();

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: colors.text,
        fontFamily: "var(--font-mono, ui-monospace, monospace)",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: colors.grid },
        horzLines: { color: colors.grid },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.06, bottom: 0.26 },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: false,
      },
      crosshair: {
        vertLine: {
          color: colors.crosshair,
          width: 1,
          style: 3,
          labelBackgroundColor: colors.crosshairLabelBg,
        },
        horzLine: {
          color: colors.crosshair,
          width: 1,
          style: 3,
          labelBackgroundColor: colors.crosshairLabelBg,
        },
      },
    });
    chartRef.current = chart;

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",        // emerald-500
      downColor: "#f43f5e",      // rose-500
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
    });
    candle.setData(
      ohlcv.map((b) => ({
        time: b.date as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );

    const ma = chart.addSeries(LineSeries, {
      color: "#a78bfa",          // violet-400 — distinct from candle colors
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    ma.setData(
      ohlcv.flatMap((b, i) => {
        const v = ma20[i];
        return v == null ? [] : [{ time: b.date as Time, value: v }];
      }),
    );

    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    volume.priceScale().applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
    });
    volume.setData(
      ohlcv.map((b) => ({
        time: b.date as Time,
        value: b.volume,
        color:
          b.close >= b.open
            ? "rgba(16, 185, 129, 0.4)"
            : "rgba(244, 63, 94, 0.4)",
      })),
    );

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [ohlcv, ma20]);

  // Range switch: do NOT recreate the chart — just zoom the time axis.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || ohlcv.length === 0) return;
    const days = RANGES.find((r) => r.id === range)?.days ?? 252;
    const startIdx = Math.max(0, ohlcv.length - days);
    chart.timeScale().setVisibleRange({
      from: ohlcv[startIdx].date as Time,
      to: ohlcv[ohlcv.length - 1].date as Time,
    });
  }, [range, ohlcv]);

  if (ohlcv.length === 0) {
    return (
      <div className="h-[260px] flex items-center justify-center text-[12px] text-muted-foreground">
        No price data available.
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-[10.5px] uppercase tracking-wider text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-emerald-500" />
            Up
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-rose-500" />
            Down
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-[2px] w-3 bg-violet-400" />
            MA20
          </span>
        </div>
        <div className="flex items-center gap-0.5 rounded-md bg-muted p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => setRange(r.id)}
              className={cn(
                "px-2.5 h-6 rounded text-[11px] font-medium tabular-nums transition-colors",
                range === r.id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="h-[260px] w-full" />
    </div>
  );
}
