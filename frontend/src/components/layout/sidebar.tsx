"use client";

import { useHistory } from "@/context/history-context";
import {
  Plus,
  TrendingUp,
  Check,
  Loader2,
  AlertCircle,
  PanelLeft,
  PanelLeftClose,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { HistoryEntry } from "@/lib/types";

interface SidebarProps {
  activeEntryId: string | null;
  onSelectHistory: (entry: HistoryEntry) => void;
  onNewAnalysis: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
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
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  const { entries } = useHistory();

  return (
    <aside
      className={cn(
        "shrink-0 border-r bg-sidebar flex flex-col h-full transition-all duration-300 ease-in-out overflow-hidden",
        collapsed ? "w-[60px]" : "w-[260px]"
      )}
    >
      {/* Brand + Toggle */}
      <div className="px-3 py-4 border-b">
        <div className="flex items-center justify-between">
          <div
            className={cn(
              "flex items-center gap-2 min-w-0",
              collapsed && "justify-center w-full"
            )}
          >
            <TrendingUp className="h-5 w-5 text-primary shrink-0" />
            {!collapsed && (
              <span className="font-bold text-lg whitespace-nowrap">
                AlphaQuant
              </span>
            )}
          </div>
          {!collapsed && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              onClick={onToggleCollapse}
            >
              <PanelLeftClose className="h-4 w-4" />
            </Button>
          )}
        </div>
        {!collapsed && (
          <p className="text-xs text-muted-foreground mt-1">
            AI Investment Research
          </p>
        )}
        {collapsed && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 mx-auto mt-2"
            onClick={onToggleCollapse}
          >
            <PanelLeft className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* New Analysis */}
      <div className="px-3 py-3">
        {collapsed ? (
          <Button
            variant="outline"
            size="icon"
            className="mx-auto flex"
            onClick={onNewAnalysis}
          >
            <Plus className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            variant="outline"
            className="w-full justify-start gap-2"
            onClick={onNewAnalysis}
          >
            <Plus className="h-4 w-4" />
            New Analysis
          </Button>
        )}
      </div>

      {/* History */}
      {!collapsed && (
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
      )}
    </aside>
  );
}
