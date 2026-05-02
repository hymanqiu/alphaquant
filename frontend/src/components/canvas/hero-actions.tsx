"use client";

import { useState } from "react";
import {
  Bookmark,
  BookmarkCheck,
  Share2,
  Check,
  Loader2,
} from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { useSavedTheses } from "@/context/saved-thesis-context";
import { cn } from "@/lib/utils";
import type { ComponentInstruction, HeroSnapshot } from "@/lib/types";

interface HeroActionsProps {
  ticker: string;
  hero: HeroSnapshot;
  components: ComponentInstruction[];
}

/**
 * Action buttons in the hero strip:
 *   - Save Thesis  (saves current canvas snapshot for revisit-diffing)
 *   - Share        (after save: copies /s/<id> URL)
 *
 * Free-tier / anonymous users see disabled buttons with a "Sign in" hint.
 * Watch button is added in v0.10 (Phase 3).
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
    </div>
  );
}

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
