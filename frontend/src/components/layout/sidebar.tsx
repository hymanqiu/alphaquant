"use client";

import { useHistory } from "@/context/history-context";
import { Plus, TrendingUp, Check, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { HistoryEntry } from "@/lib/types";

interface SidebarProps {
  activeEntryId: string | null;
  onSelectHistory: (entry: HistoryEntry) => void;
  onNewAnalysis: () => void;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "running":
      return <Loader2 className="h-3 w-3 animate-spin text-blue-500" />;
    case "complete":
      return <Check className="h-3 w-3 text-emerald-500" />;
    case "error":
      return <AlertCircle className="h-3 w-3 text-red-500" />;
    default:
      return null;
  }
}

function formatTime(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return new Date(timestamp).toLocaleDateString();
}

export function Sidebar({
  activeEntryId,
  onSelectHistory,
  onNewAnalysis,
}: SidebarProps) {
  const { entries } = useHistory();

  return (
    <aside className="w-[260px] shrink-0 border-r bg-sidebar flex flex-col h-full">
      {/* Brand */}
      <div className="px-4 py-4 border-b">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          <span className="font-bold text-lg">AlphaQuant</span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          AI Investment Research
        </p>
      </div>

      {/* New Analysis */}
      <div className="px-3 py-3">
        <Button
          variant="outline"
          className="w-full justify-start gap-2"
          onClick={onNewAnalysis}
        >
          <Plus className="h-4 w-4" />
          New Analysis
        </Button>
      </div>

      {/* History */}
      <div className="flex-1 overflow-y-auto px-2">
        <p className="px-2 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          History
        </p>
        {entries.length === 0 && (
          <p className="px-2 py-4 text-xs text-muted-foreground text-center">
            No analyses yet
          </p>
        )}
        <div className="space-y-0.5">
          {entries.map((entry) => (
            <button
              key={entry.id}
              onClick={() => onSelectHistory(entry)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors ${
                activeEntryId === entry.id
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "hover:bg-sidebar-accent/50 text-sidebar-foreground"
              }`}
            >
              <span className="font-mono font-medium shrink-0">
                {entry.ticker}
              </span>
              <span className="flex-1 text-xs text-muted-foreground truncate">
                {formatTime(entry.timestamp)}
              </span>
              <StatusIcon status={entry.status} />
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
