"use client";

import Link from "next/link";
import { useAuth } from "@/context/auth-context";
import { useHistory } from "@/context/history-context";
import { useSavedTheses } from "@/context/saved-thesis-context";
import { useWatchlist } from "@/context/watchlist-context";
import {
  Plus,
  Check,
  Loader2,
  AlertCircle,
  PanelLeft,
  PanelLeftClose,
  Sparkles,
  LogIn,
  LogOut,
  Bookmark,
  Eye,
  X,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { HistoryEntry, SavedThesisSummary, WatchlistItem } from "@/lib/types";

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

function AuthSection({ collapsed }: { collapsed: boolean }) {
  const { user, status, isPro, logout } = useAuth();

  if (status === "loading") {
    return (
      <div className={cn("flex items-center gap-2 px-2.5 h-9 text-muted-foreground", collapsed && "justify-center")}>
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </div>
    );
  }

  if (status === "anonymous") {
    if (collapsed) {
      return (
        <Link
          href="/auth/login"
          aria-label="Sign in"
          className="flex h-9 items-center justify-center text-muted-foreground hover:text-foreground"
        >
          <LogIn className="h-4 w-4" />
        </Link>
      );
    }
    return (
      <div className="space-y-1">
        <Link
          href="/auth/login"
          className="w-full flex items-center gap-2 px-2.5 h-9 rounded-lg text-[13px] font-medium text-foreground hover:bg-sidebar-accent transition-colors"
        >
          <LogIn className="h-4 w-4 text-muted-foreground" />
          Sign in
        </Link>
        <Link
          href="/auth/register"
          className="w-full flex items-center gap-2 px-2.5 h-9 rounded-lg text-[12px] text-muted-foreground hover:bg-sidebar-accent hover:text-foreground transition-colors"
        >
          <span className="w-4" />
          Create account
        </Link>
      </div>
    );
  }

  // Authenticated
  const initial = (user?.display_name || user?.email || "?").charAt(0).toUpperCase();

  if (collapsed) {
    return (
      <button
        onClick={logout}
        title={`${user?.email} — click to sign out`}
        aria-label="Sign out"
        className="flex h-9 w-9 mx-auto items-center justify-center rounded-full bg-muted text-[12px] font-semibold hover:bg-sidebar-accent transition-colors"
      >
        {initial}
      </button>
    );
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 px-1">
        <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center text-[12px] font-semibold flex-shrink-0">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-medium truncate">
            {user?.display_name || user?.email}
          </p>
          <p className="text-[10px] text-muted-foreground truncate flex items-center gap-1">
            {isPro ? (
              <>
                <Sparkles className="h-2.5 w-2.5 text-amber-500" />
                <span className="font-medium text-amber-700 dark:text-amber-400">Pro</span>
              </>
            ) : (
              <span>Free tier</span>
            )}
            <span>·</span>
            <span className="truncate">{user?.email}</span>
          </p>
        </div>
      </div>
      <button
        onClick={logout}
        className="w-full flex items-center gap-2 px-2.5 h-8 rounded-lg text-[12px] text-muted-foreground hover:bg-sidebar-accent hover:text-foreground transition-colors"
      >
        <LogOut className="h-3.5 w-3.5" />
        Sign out
      </button>
    </div>
  );
}


function WatchlistSection({
  onSelectTicker,
}: {
  onSelectTicker: (ticker: string) => void;
}) {
  const { items, remove } = useWatchlist();
  if (items.length === 0) return null;
  return (
    <div className="mt-3 first:mt-1">
      <p className="px-2 py-1.5 text-[11px] font-medium text-muted-foreground/70 inline-flex items-center gap-1.5">
        <Eye className="h-2.5 w-2.5" />
        Watching
      </p>
      <div className="space-y-0.5">
        {items.map((item) => (
          <WatchlistRow
            key={item.id}
            item={item}
            onClick={() => onSelectTicker(item.ticker)}
            onRemove={() => remove(item.ticker).catch(() => {})}
          />
        ))}
      </div>
    </div>
  );
}

function WatchlistRow({
  item,
  onClick,
  onRemove,
}: {
  item: WatchlistItem;
  onClick: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="group flex items-center gap-1 pr-1 rounded-lg hover:bg-sidebar-accent/60">
      <button
        type="button"
        onClick={onClick}
        className="flex-1 flex items-center gap-2 px-2.5 h-8 text-[13px] text-left text-sidebar-foreground/80 hover:text-sidebar-foreground transition-colors"
        title={`Re-analyze ${item.ticker}`}
      >
        <span className="font-mono font-semibold text-[12px] shrink-0 tracking-tight">
          {item.ticker}
        </span>
        {item.target_mos_pct != null && (
          <span className="flex-1 text-[11px] text-muted-foreground truncate font-mono">
            ≥ {item.target_mos_pct}%
          </span>
        )}
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="opacity-0 group-hover:opacity-100 h-6 w-6 rounded text-muted-foreground hover:text-destructive transition-opacity flex items-center justify-center"
        aria-label={`Remove ${item.ticker} from watchlist`}
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

function SavedThesesSection() {
  const { items, remove } = useSavedTheses();
  if (items.length === 0) return null;
  return (
    <div className="mt-3 first:mt-1">
      <p className="px-2 py-1.5 text-[11px] font-medium text-muted-foreground/70 inline-flex items-center gap-1.5">
        <Bookmark className="h-2.5 w-2.5" />
        Saved theses
      </p>
      <div className="space-y-0.5">
        {items.map((thesis) => (
          <SavedThesisRow
            key={thesis.id}
            thesis={thesis}
            onRemove={() => remove(thesis.id).catch(() => {})}
          />
        ))}
      </div>
    </div>
  );
}

function SavedThesisRow({
  thesis,
  onRemove,
}: {
  thesis: SavedThesisSummary;
  onRemove: () => void;
}) {
  const ts = thesis.created_at ? Date.parse(thesis.created_at) : NaN;
  const age = Number.isFinite(ts) ? formatTime(ts) : "—";
  const signal = thesis.hero_snapshot.signalLabel;
  return (
    <div className="group flex items-center gap-1 pr-1 rounded-lg hover:bg-sidebar-accent/60">
      <Link
        href={thesis.is_public ? `/s/${thesis.id}` : "#"}
        target={thesis.is_public ? "_blank" : undefined}
        className={cn(
          "flex-1 flex items-center gap-2 px-2.5 h-8 text-[13px] text-left transition-colors",
          "text-sidebar-foreground/80 hover:text-sidebar-foreground"
        )}
        title={thesis.title || `${thesis.ticker} thesis snapshot from ${age}`}
      >
        <span className="font-mono font-semibold text-[12px] shrink-0 tracking-tight">
          {thesis.ticker}
        </span>
        <span className="flex-1 text-[11px] text-muted-foreground truncate">
          {signal ? `${signal} · ${age}` : age}
        </span>
        {thesis.is_public && (
          <ExternalLink className="h-2.5 w-2.5 text-muted-foreground/60" />
        )}
      </Link>
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onRemove();
        }}
        className="opacity-0 group-hover:opacity-100 h-6 w-6 rounded text-muted-foreground hover:text-destructive transition-opacity flex items-center justify-center"
        aria-label="Delete saved thesis"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
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

  // Watchlist click re-runs analysis on that ticker (synthesizes a history submit).
  const handleSelectTicker = (ticker: string) => {
    // Reuse the submit handler inside AppShell by going through the same code
    // path — we synthesize a fake HistoryEntry with no cache so it falls
    // through to handleSubmitTicker.
    onSelectHistory({
      id: `watch-${ticker}-${Date.now()}`,
      ticker,
      timestamp: Date.now(),
      status: "running",
    });
  };

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

      {/* Scrollable middle: Watchlist + Saved Theses + History */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-3">
          <WatchlistSection onSelectTicker={handleSelectTicker} />
          <SavedThesesSection />

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

      {/* Footer: auth section + tagline */}
      <div
        className={cn(
          "border-t border-sidebar-border shrink-0",
          collapsed ? "py-2" : "px-2 py-2 space-y-2"
        )}
      >
        <AuthSection collapsed={collapsed} />
        {!collapsed && (
          <p className="text-[10px] text-muted-foreground/70 leading-relaxed px-1">
            AI-powered SEC research. Data from EDGAR &amp; FMP.
          </p>
        )}
      </div>
    </aside>
  );
}
