"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { ConversationPanel } from "@/components/conversation-panel";
import { AnalysisCanvas } from "@/components/analysis-canvas";
import { EmptyState } from "@/components/empty-state";
import { useAnalysisStream } from "@/hooks/use-analysis-stream";
import { useHistory } from "@/context/history-context";
import { API_BASE_URL } from "@/lib/constants";
import type {
  AnalysisStep,
  ComponentInstruction,
  HistoryEntry,
  SSEStatus,
  ThinkingMessage,
} from "@/lib/types";

interface AppShellProps {
  initialTicker?: string;
}

interface CachedAnalysis {
  thinkingMessages: ThinkingMessage[];
  components: ComponentInstruction[];
  steps: AnalysisStep[];
  verdict: string | null;
}

const EMPTY_MESSAGES: ThinkingMessage[] = [];
const EMPTY_COMPONENTS: ComponentInstruction[] = [];
const EMPTY_STEPS: AnalysisStep[] = [];

export function AppShell({ initialTicker }: AppShellProps) {
  const [ticker, setTicker] = useState<string | null>(
    initialTicker?.toUpperCase() ?? null
  );
  // isLive = true means a new SSE analysis is running; false = viewing cache or idle
  const [isLive, setIsLive] = useState(!!initialTicker);

  // SSE connection — only active when isLive && ticker is set
  const liveTicker = isLive ? ticker : null;
  const stream = useAnalysisStream(liveTicker);

  // --- Fix 1: In-memory cache for completed analyses ---
  const cacheRef = useRef(new Map<string, CachedAnalysis>());
  const [cachedView, setCachedView] = useState<CachedAnalysis | null>(null);

  // --- Fix 2: Raw recalc result, applied via useMemo (no stale closure) ---
  const [recalcResult, setRecalcResult] = useState<Record<
    string,
    unknown
  > | null>(null);

  // History tracking
  const { addEntry, updateEntry } = useHistory();
  const entryIdRef = useRef<string | null>(null);
  const [activeEntryId, setActiveEntryId] = useState<string | null>(null);

  // Sidebar collapse
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // --- Fix 3: statusRef so callbacks always see current status ---
  const statusRef = useRef(stream.status);
  statusRef.current = stream.status;

  // ── Derived display values (live vs cached) ──

  const displayStatus: SSEStatus = isLive
    ? stream.status
    : cachedView
      ? "complete"
      : "idle";

  const displayThinkingMessages = isLive
    ? stream.thinkingMessages
    : cachedView?.thinkingMessages ?? EMPTY_MESSAGES;

  const displaySteps = isLive
    ? stream.steps
    : cachedView?.steps ?? EMPTY_STEPS;

  const displayVerdict = isLive
    ? stream.verdict
    : cachedView?.verdict ?? null;

  const displayError = isLive ? stream.error : null;

  const baseComponents = isLive
    ? stream.components
    : cachedView?.components ?? EMPTY_COMPONENTS;

  // Fix 2: Apply recalc overrides via useMemo — always on top of latest baseComponents
  const displayComponents = useMemo(() => {
    if (!recalcResult) return baseComponents;

    return baseComponents.map((comp) => {
      switch (comp.component_type) {
        case "dcf_result_card":
          return {
            ...comp,
            props: {
              ...comp.props,
              intrinsic_value_per_share:
                recalcResult.intrinsic_value_per_share,
              enterprise_value: recalcResult.enterprise_value,
              terminal_value: recalcResult.terminal_value,
              pv_fcf_sum: recalcResult.pv_fcf_sum,
              assumptions: recalcResult.assumptions,
            },
          };
        case "valuation_gauge":
          return {
            ...comp,
            props: {
              ...comp.props,
              intrinsic_value: recalcResult.intrinsic_value_per_share,
            },
          };
        case "fcf_chart":
          return {
            ...comp,
            props: { ...comp.props, data: recalcResult.chart_data },
          };
        case "strategy_dashboard": {
          const iv = recalcResult.intrinsic_value_per_share as number | null;
          if (iv == null || iv <= 0) return comp;
          const cp = comp.props.current_price as number;
          const mosPct = ((iv - cp) / iv) * 100;
          const upside = ((iv - cp) / cp) * 100;
          const suggestedEntry = iv * 0.85;
          let signal: string;
          if (mosPct > 25) signal = "Deep Value";
          else if (mosPct > 10) signal = "Undervalued";
          else if (mosPct > -10) signal = "Fair Value";
          else signal = "Overvalued";
          return {
            ...comp,
            props: {
              ...comp.props,
              intrinsic_value: iv,
              margin_of_safety_pct: Math.round(mosPct * 10) / 10,
              suggested_entry_price: Math.round(suggestedEntry * 100) / 100,
              upside_pct: Math.round(upside * 10) / 10,
              signal,
            },
          };
        }
        default:
          return comp;
      }
    });
  }, [baseComponents, recalcResult]);

  // ── History entry lifecycle ──

  // Create history entry when live analysis starts connecting
  useEffect(() => {
    if (isLive && ticker && stream.status === "connecting" && !entryIdRef.current) {
      const id = addEntry(ticker);
      entryIdRef.current = id;
      setActiveEntryId(id);
    }
  }, [isLive, ticker, stream.status, addEntry]);

  // Update history entry + cache result when live analysis completes or errors
  useEffect(() => {
    if (!entryIdRef.current || !isLive) return;
    if (stream.status === "complete") {
      updateEntry(entryIdRef.current, {
        status: "complete",
        verdict: stream.verdict ?? undefined,
      });
      // Cache the completed result
      cacheRef.current.set(entryIdRef.current, {
        thinkingMessages: stream.thinkingMessages,
        components: stream.components,
        steps: stream.steps,
        verdict: stream.verdict,
      });
    } else if (stream.status === "error") {
      updateEntry(entryIdRef.current, { status: "error" });
    }
  }, [
    isLive,
    stream.status,
    stream.verdict,
    stream.thinkingMessages,
    stream.components,
    stream.steps,
    updateEntry,
  ]);

  // Fix 3: Clean up a previous entry that's still "running" before switching
  const cleanupPrevious = useCallback(() => {
    if (
      entryIdRef.current &&
      (statusRef.current === "connecting" || statusRef.current === "connected")
    ) {
      updateEntry(entryIdRef.current, { status: "error" });
    }
  }, [updateEntry]);

  // ── User actions ──

  // Start a brand-new live analysis (from input bar or re-analyze)
  const handleSubmitTicker = useCallback(
    (t: string) => {
      cleanupPrevious();
      setTicker(t.toUpperCase());
      setIsLive(true);
      setCachedView(null);
      setRecalcResult(null);
      entryIdRef.current = null;
      setActiveEntryId(null);
    },
    [cleanupPrevious]
  );

  // Fix 1: Click a sidebar history entry — restore from cache if available
  const handleSelectHistory = useCallback(
    (entry: HistoryEntry) => {
      const cached = cacheRef.current.get(entry.id);
      if (cached && entry.status === "complete") {
        // Restore cached result without SSE
        cleanupPrevious();
        setTicker(entry.ticker);
        setIsLive(false);
        setCachedView(cached);
        setRecalcResult(null);
        entryIdRef.current = entry.id;
        setActiveEntryId(entry.id);
      } else {
        // No cache — re-analyze
        handleSubmitTicker(entry.ticker);
      }
    },
    [cleanupPrevious, handleSubmitTicker]
  );

  // Reset to empty state
  const handleNewAnalysis = useCallback(() => {
    cleanupPrevious();
    setTicker(null);
    setIsLive(false);
    setCachedView(null);
    setRecalcResult(null);
    entryIdRef.current = null;
    setActiveEntryId(null);
  }, [cleanupPrevious]);

  // Fix 2: Recalculate handler — no dependencies on components (no stale closure)
  const handleRecalculate = useCallback(
    async (data: Record<string, unknown>) => {
      try {
        const resp = await fetch(`${API_BASE_URL}/api/recalculate-dcf`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        if (!resp.ok) return;
        setRecalcResult(await resp.json());
      } catch {
        // Silently fail — original components remain
      }
    },
    []
  );

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        activeEntryId={activeEntryId}
        onSelectHistory={handleSelectHistory}
        onNewAnalysis={handleNewAnalysis}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
      />
      <div className="flex flex-1 overflow-hidden">
        {ticker === null ? (
          <EmptyState onSubmit={handleSubmitTicker} />
        ) : (
          <>
            <ConversationPanel
              ticker={ticker}
              status={displayStatus}
              steps={displaySteps}
              thinkingMessages={displayThinkingMessages}
              verdict={displayVerdict}
              error={displayError}
              onSubmitTicker={handleSubmitTicker}
            />
            <AnalysisCanvas
              ticker={ticker}
              components={displayComponents}
              onRecalculate={handleRecalculate}
              status={displayStatus}
            />
          </>
        )}
      </div>
    </div>
  );
}
