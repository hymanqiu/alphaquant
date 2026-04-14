"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const EXAMPLE_TICKERS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN"];

export default function HomePage() {
  const [ticker, setTicker] = useState("");
  const router = useRouter();

  const handleAnalyze = () => {
    const t = ticker.trim().toUpperCase();
    if (t) {
      router.push(`/analyze/${t}`);
    }
  };

  return (
    <main className="flex-1 flex items-center justify-center p-8">
      <div className="w-full max-w-lg space-y-8 text-center">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight">AlphaQuant</h1>
          <p className="text-muted-foreground">
            AI-powered deep value analysis using SEC EDGAR data
          </p>
        </div>

        <div className="flex gap-2">
          <Input
            placeholder="Enter ticker symbol (e.g. NVDA)"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            className="text-center text-lg"
          />
          <Button onClick={handleAnalyze} disabled={!ticker.trim()}>
            Analyze
          </Button>
        </div>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">Quick start</p>
          <div className="flex flex-wrap justify-center gap-2">
            {EXAMPLE_TICKERS.map((t) => (
              <Button
                key={t}
                variant="outline"
                size="sm"
                onClick={() => router.push(`/analyze/${t}`)}
              >
                {t}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
