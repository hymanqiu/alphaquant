"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Sparkles, ExternalLink } from "lucide-react";
import { VerdictHero } from "@/components/canvas/verdict-hero";
import { CanvasTabs } from "@/components/canvas/canvas-tabs";
import { groupByTab, type TabId } from "@/components/canvas/tab-groups";
import { getPublicThesis } from "@/lib/saved-thesis-api";
import { ApiError } from "@/lib/api-client";
import type { SavedThesisFull } from "@/lib/types";

/**
 * Public read-only view of a saved thesis. URL: /s/<id>
 *
 * No auth required — only works for theses where ``is_public=True`` on the
 * backend. The hero is rendered with status="complete" so streaming-only
 * affordances (skeletons, pulses) are off.
 */
export default function SharePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [thesis, setThesis] = useState<SavedThesisFull | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("verdict");

  useEffect(() => {
    let alive = true;
    getPublicThesis(id)
      .then((t) => {
        if (alive) setThesis(t);
      })
      .catch((e) => {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 404) {
          setError("This thesis is private or no longer available.");
        } else {
          setError("Failed to load thesis.");
        }
      });
    return () => {
      alive = false;
    };
  }, [id]);

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center p-8">
        <div className="text-center space-y-3 max-w-sm">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-muted/50 flex items-center justify-center">
            <ExternalLink className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-[14px] text-foreground">{error}</p>
          <Link
            href="/"
            className="text-[12px] text-[var(--brand)] hover:underline inline-flex items-center gap-1"
          >
            Run your own analysis on AlphaQuant →
          </Link>
        </div>
      </main>
    );
  }

  if (!thesis) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </main>
    );
  }

  const groups = groupByTab(thesis.components_snapshot);

  return (
    <main className="min-h-screen flex flex-col bg-surface">
      {/* Top banner — explains this is a shared snapshot */}
      <header className="h-12 px-4 border-b bg-background/80 backdrop-blur-md flex items-center gap-3 shrink-0">
        <Link
          href="/"
          className="flex items-center gap-2 text-[13px] font-semibold tracking-tight"
        >
          <span className="h-6 w-6 rounded-md bg-gradient-to-br from-[var(--brand)] to-[oklch(0.45_0.2_265)] flex items-center justify-center ring-1 ring-black/5">
            <Sparkles className="h-3 w-3 text-white" />
          </span>
          AlphaQuant
        </Link>
        <span className="text-[11px] text-muted-foreground">
          shared thesis · snapshot
          {thesis.created_at && ` · ${new Date(thesis.created_at).toLocaleDateString()}`}
        </span>
        <Link
          href="/"
          className="ml-auto text-[12px] text-[var(--brand)] hover:underline"
        >
          Run your own analysis →
        </Link>
      </header>

      <div className="flex-1 flex flex-col overflow-hidden">
        <VerdictHero
          ticker={thesis.ticker}
          components={thesis.components_snapshot}
          status="complete"
          onJumpToTab={setActiveTab}
          isSnapshotView
        />
        <CanvasTabs
          groups={groups}
          status="complete"
          thinkingMessages={[]}
          steps={[]}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />
      </div>
    </main>
  );
}
