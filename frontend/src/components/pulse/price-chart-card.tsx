"use client";

import dynamic from "next/dynamic";
import { LineChart } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface PriceChartCardProps {
  ticker: string;
  ohlcv: OHLCVBar[];
  ma20: (number | null)[];
}

// lightweight-charts touches `window` at import time; must skip SSR.
const PriceChartImpl = dynamic(() => import("./price-chart-impl"), {
  ssr: false,
  loading: () => <Skeleton className="h-[260px] w-full rounded-lg" />,
});

export default function PriceChartCard({
  ticker,
  ohlcv,
  ma20,
}: PriceChartCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2.5">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
            <LineChart className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <CardTitle className="text-[14px] font-semibold">
              Price action · {ticker}
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Daily candles with 20-day moving average
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <PriceChartImpl ohlcv={ohlcv} ma20={ma20} />
      </CardContent>
    </Card>
  );
}
