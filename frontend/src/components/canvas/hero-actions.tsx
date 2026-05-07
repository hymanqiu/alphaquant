"use client";

import { useState } from "react";
import {
  Bookmark,
  BookmarkCheck,
  Eye,
  EyeOff,
  Share2,
  Check,
  Loader2,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { useSavedTheses } from "@/context/saved-thesis-context";
import { useWatchlist } from "@/context/watchlist-context";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { ComponentInstruction, HeroSnapshot } from "@/lib/types";

interface HeroActionsProps {
  ticker: string;
  hero: HeroSnapshot;
  components: ComponentInstruction[];
}

/**
 * Triplet of action buttons in the hero strip:
 *   - Save Thesis  (saves current canvas snapshot for revisit-diffing)
 *   - Watch        (adds ticker to watchlist with optional MoS threshold)
 *   - Share        (only enabled after a save; copies /s/<id> URL)
 *
 * Free-tier users see disabled buttons with a "Sign in" hint.
 */
export function HeroActions({ ticker, hero, components }: HeroActionsProps) {
  const { status } = useAuth();
  const isAuthed = status === "authenticated";

  return (
    <div className="flex items-center gap-1.5 shrink-0">
      <SaveButton
        ticker={ticker}
        hero={hero}
        components={components}
        disabled={!isAuthed}
      />
      <WatchButton ticker={ticker} disabled={!isAuthed} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Save Thesis
// ---------------------------------------------------------------------------

function SaveButton({
  ticker,
  hero,
  components,
  disabled,
}: {
  ticker: string;
  hero: HeroSnapshot;
  components: ComponentInstruction[];
  disabled: boolean;
}) {
  const { items, save } = useSavedTheses();
  const [submitting, setSubmitting] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Already saved this ticker? Treat the most recent save as the "current" one.
  const existing = items.find((i) => i.ticker === ticker.toUpperCase());
  const isAlreadySaved = !!existing || !!savedId;
  const liveId = savedId ?? existing?.id ?? null;

  const handleSave = async () => {
    if (disabled || submitting) return;
    setSubmitting(true);
    try {
      const created = await save({
        ticker,
        hero_snapshot: hero,
        components_snapshot: components,
      });
      setSavedId(created.id);
    } catch (e) {
      console.warn("Save failed:", e);
    } finally {
      setSubmitting(false);
    }
  };

  const handleShare = async () => {
    if (!liveId) return;
    const url = `${window.location.origin}/s/${liveId}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("Copy share link:", url);
    }
  };

  if (isAlreadySaved) {
    return (
      <div className="flex items-center gap-1">
        <span
          title="Saved to your theses — diff vs current shows in sidebar on revisit"
          className="inline-flex items-center gap-1 px-2 h-7 rounded-lg bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-[11px] font-medium ring-1 ring-emerald-500/20"
        >
          <BookmarkCheck className="h-3 w-3" />
          Saved
        </span>
        <button
          type="button"
          onClick={handleShare}
          className="inline-flex items-center gap-1 px-2 h-7 rounded-lg bg-card border text-[11px] hover:bg-muted/60 transition-colors"
          title="Copy public share link"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-600" />
              Copied
            </>
          ) : (
            <>
              <Share2 className="h-3 w-3" />
              Share
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={handleSave}
      disabled={disabled || submitting}
      title={
        disabled
          ? "Sign in to save and share theses"
          : "Snapshot this thesis — see how it moves on revisit"
      }
      className={cn(
        "inline-flex items-center gap-1 px-2 h-7 rounded-lg text-[11px] font-medium ring-1 transition-colors",
        disabled
          ? "bg-muted/40 text-muted-foreground/60 ring-border cursor-not-allowed"
          : "bg-card text-foreground/80 ring-border hover:bg-muted/60"
      )}
    >
      {submitting ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <Bookmark className="h-3 w-3" />
      )}
      Save
    </button>
  );
}

// ---------------------------------------------------------------------------
// Watch (with threshold dialog)
// ---------------------------------------------------------------------------

function WatchButton({ ticker, disabled }: { ticker: string; disabled: boolean }) {
  const { isWatching, add, remove, itemFor } = useWatchlist();
  const [open, setOpen] = useState(false);
  const watching = isWatching(ticker);
  const current = itemFor(ticker);

  const handleToggle = async () => {
    if (disabled) return;
    if (watching) {
      try {
        await remove(ticker);
      } catch (e) {
        console.warn("Unwatch failed:", e);
      }
      return;
    }
    setOpen(true);
  };

  return (
    <>
      <button
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        title={
          disabled
            ? "Sign in to use the watchlist"
            : watching
            ? "Watching — click to remove"
            : "Add to watchlist"
        }
        className={cn(
          "inline-flex items-center gap-1 px-2 h-7 rounded-lg text-[11px] font-medium ring-1 transition-colors",
          disabled
            ? "bg-muted/40 text-muted-foreground/60 ring-border cursor-not-allowed"
            : watching
            ? "bg-amber-500/10 text-amber-700 dark:text-amber-400 ring-amber-500/25"
            : "bg-card text-foreground/80 ring-border hover:bg-muted/60"
        )}
      >
        {watching ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
        {watching
          ? current?.target_mos_pct != null
            ? `Watching ≥ ${current.target_mos_pct}%`
            : "Watching"
          : "Watch"}
      </button>

      {open && (
        <ThresholdDialog
          ticker={ticker}
          onClose={() => setOpen(false)}
          onConfirm={async (target) => {
            try {
              await add(ticker, target);
            } catch (e) {
              if (e instanceof ApiError && e.status === 401) {
                console.warn("Auth required");
              } else {
                console.warn("Watch failed:", e);
              }
            } finally {
              setOpen(false);
            }
          }}
        />
      )}
    </>
  );
}

// Backend constrains target_mos_pct to [-100, 100]; mirror that here so we
// don't silently drop a 422 from the server.
const TARGET_MIN = -100;
const TARGET_MAX = 100;

function ThresholdDialog({
  ticker,
  onClose,
  onConfirm,
}: {
  ticker: string;
  onClose: () => void;
  onConfirm: (target: number | null) => void;
}) {
  const [target, setTarget] = useState<string>("20");
  const [useThreshold, setUseThreshold] = useState(true);

  const parsed = parseFloat(target);
  const isValid = Number.isFinite(parsed) && parsed >= TARGET_MIN && parsed <= TARGET_MAX;
  const showRangeError = useThreshold && target !== "" && !isValid;

  const handleConfirm = () => {
    if (useThreshold && !isValid) return;
    onConfirm(useThreshold ? parsed : null);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl border bg-background shadow-2xl p-5 space-y-4 animate-in slide-in-from-bottom-2"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <h3 className="text-[14px] font-semibold">
            Watch <span className="font-mono">{ticker}</span>
          </h3>
          <p className="text-[11.5px] text-muted-foreground mt-0.5">
            Optionally set an alert threshold. Future check-ins will flag when the
            margin of safety crosses it.
          </p>
        </div>

        <label className="flex items-center gap-2 text-[12.5px] cursor-pointer">
          <input
            type="checkbox"
            checked={useThreshold}
            onChange={(e) => setUseThreshold(e.target.checked)}
            className="h-3.5 w-3.5"
          />
          <span>Alert when margin of safety ≥</span>
          <input
            type="number"
            step="0.1"
            min={TARGET_MIN}
            max={TARGET_MAX}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={!useThreshold}
            className={cn(
              "w-16 px-2 py-1 rounded-md border bg-card text-[12px] font-mono tabular-nums disabled:opacity-50",
              showRangeError && "border-destructive ring-1 ring-destructive/40"
            )}
          />
          <span>%</span>
        </label>

        {showRangeError && (
          <p className="text-[11px] text-destructive">
            Threshold must be between {TARGET_MIN} and {TARGET_MAX}.
          </p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="px-3 h-8 rounded-lg text-[12px] hover:bg-muted/60 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={useThreshold && !isValid}
            className="px-3 h-8 rounded-lg bg-foreground text-background text-[12px] font-medium hover:bg-foreground/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Add to watchlist
          </button>
        </div>
      </div>
    </div>
  );
}
