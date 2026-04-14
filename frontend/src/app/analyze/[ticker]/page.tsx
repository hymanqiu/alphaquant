import { use } from "react";
import { AnalysisLayout } from "@/components/layout/analysis-layout";

export default function AnalyzePage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = use(params);

  return (
    <main className="flex-1 flex flex-col">
      <div className="border-b px-6 py-3 flex items-center gap-4">
        <a href="/" className="text-lg font-bold hover:opacity-80">
          AlphaQuant
        </a>
        <span className="text-muted-foreground">/</span>
        <span className="font-mono text-lg">{ticker.toUpperCase()}</span>
      </div>
      <AnalysisLayout ticker={ticker.toUpperCase()} />
    </main>
  );
}
