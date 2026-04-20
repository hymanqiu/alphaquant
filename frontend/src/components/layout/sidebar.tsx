"use client";

import { useHistory } from "@/context/history-context";
import {
  Plus,
  Check,
  Loader2,
  AlertCircle,
  PanelLeft,
  PanelLeftClose,
  Sparkles,
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

function StatusDot({ status }: { status: string }) {
  switch (status) {
    case "running":
      return <Loader2 className="h-3 w-3 animate-spin text-[var(--brand)]" />;
    case "complete":
      return <Check className="h-3 w-3 text-emerald-500" />;
    case "error":
      return <AlertCircle className="h-3 w-3 text-destructive" />;
    default:
      return <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />;
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

function groupByDay(entries: HistoryEntry[]) {
  const groups: { label: string; items: HistoryEntry[] }[] = [];
  const now = Date.now();
  const DAY = 86_400_000;
  const buckets = {
    Today: [] as HistoryEntry[],
    Yesterday: [] as HistoryEntry[],
    "This week": [] as HistoryEntry[],
    Earlier: [] as HistoryEntry[],
  };
  for (const e of entries) {
    const diff = now - e.timestamp;
    if (diff < DAY) buckets.Today.push(e);
    else if (diff < 2 * DAY) buckets.Yesterday.push(e);
    else if (diff < 7 * DAY) buckets["This week"].push(e);
    else buckets.Earlier.push(e);
  }
  for (const [label, items] of Object.entries(buckets)) {
    if (items.length) groups.push({ label, items });
  }
  return groups;
}

export function Sidebar({
  activeEntryId,
  onSelectHistory,
  onNewAnalysis,
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  const { entries } = useHistory();
  const groups = groupByDay(entries);

  return (
    <aside
      className={cn(
        "shrink-0 bg-sidebar flex flex-col h-full transition-[width] duration-200 ease-out overflow-hidden",
        "border-r border-sidebar-border",
        collapsed ? "w-[56px]" : "w-[248px]"
      )}
    >
      {/* Brand row */}
      <div
        className={cn(
          "flex items-center h-14 px-3 shrink-0",
          collapsed ? "justify-center" : "justify-between"
        )}
      >
        {!collapsed && (
          <div className="flex items-center gap-2 min-w-0">
            <div className="relative h-7 w-7 rounded-lg bg-gradient-to-br from-[var(--brand)] to-[oklch(0.45_0.2_265)] flex items-center justify-center shadow-sm ring-1 ring-black/5">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="font-semibold text-[15px] tracking-tight truncate">
              AlphaQuant
            </span>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          className="text-muted-foreground hover:text-foreground"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* New Analysis */}
      <div className="px-2 pb-2 shrink-0">
        {collapsed ? (
          <Button
            variant="ghost"
            size="icon"
            className="mx-auto flex text-muted-foreground hover:text-foreground"
            onClick={onNewAnalysis}
            aria-label="New analysis"
          >
            <Plus className="h-4 w-4" />
          </Button>
        ) : (
          <button
            onClick={onNewAnalysis}
            className="w-full flex items-center gap-2 px-2.5 h-9 rounded-lg text-[13px] font-medium text-foreground hover:bg-sidebar-accent transition-colors"
          >
            <Plus className="h-4 w-4 text-muted-foreground" />
            New analysis
          </button>
        )}
      </div>

      {/* History */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-3">
          {entries.length === 0 && (
            <div className="px-2 py-6 text-center">
              <p className="text-xs text-muted-foreground">
                Your analyses will appear here
              </p>
            </div>
          )}
          {groups.map(({ label, items }) => (
            <div key={label} className="mt-3 first:mt-1">
              <p className="px-2 py-1.5 text-[11px] font-medium text-muted-foreground/70">
                {label}
              </p>
              <div className="space-y-0.5">
                {items.map((entry) => (
                  <button
                    key={entry.id}
                    onClick={() => onSelectHistory(entry)}
                    className={cn(
                      "group w-full flex items-center gap-2 px-2.5 h-8 rounded-lg text-[13px] text-left transition-colors",
                      activeEntryId === entry.id
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
                    )}
                  >
                    <span className="font-mono font-semibold text-[12px] shrink-0 tracking-tight">
                      {entry.ticker}
                    </span>
                    <span className="flex-1 text-[11px] text-muted-foreground truncate">
                      {formatTime(entry.timestamp)}
                    </span>
                    <StatusDot status={entry.status} />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer */}
      {!collapsed && (
        <div className="px-3 py-3 border-t border-sidebar-border shrink-0">
          <p className="text-[10px] text-muted-foreground/70 leading-relaxed">
            AI-powered SEC research.
            <br />
            Data sourced from EDGAR & FMP.
          </p>
        </div>
      )}
    </aside>
  );
}
