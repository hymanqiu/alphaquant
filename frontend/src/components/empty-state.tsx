"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const EXAMPLE_TICKERS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN"];

interface EmptyStateProps {
  onSubmit: (ticker: string) => void;
}

export function EmptyState({ onSubmit }: EmptyStateProps) {
  const [input, setInput] = useState("");

  const handleSubmit = () => {
    const t = input.trim().toUpperCase();
    if (t) {
      onSubmit(t);
      setInput("");
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="w-full max-w-md space-y-6 text-center">
        <div className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight">
            Start an Analysis
          </h2>
          <p className="text-sm text-muted-foreground">
            Enter a ticker symbol to begin AI-powered deep value analysis
          </p>
        </div>

        <div className="flex gap-2">
          <Input
            placeholder="Enter ticker (e.g. NVDA)"
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            className="text-center"
          />
          <Button onClick={handleSubmit} disabled={!input.trim()}>
            <Send className="h-4 w-4" />
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
                onClick={() => onSubmit(t)}
              >
                {t}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
