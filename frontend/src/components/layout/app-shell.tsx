"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { ConversationPanel } from "@/components/conversation-panel";
import { AnalysisCanvas } from "@/components/analysis-canvas";
import { EmptyState } from "@/components/empty-state";
import type { TabId } from "@/components/canvas/tab-groups";
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
  const [isLive, setIsLive] = useState(!!initialTicker);

  const liveTicker = isLive ? ticker : null;
  const stream = useAnalysisStream(liveTicker);

  const cacheRef = useRef(new Map<string, CachedAnalysis>());
  const [cachedView, setCachedView] = useState<CachedAnalysis | null>(null);

  const [recalcResult, setRecalcResult] = useState<Record<string, unknown> | null>(null);

  const { addEntry, updateEntry } = useHistory();
  const entryIdRef = useRef<string | null>(null);
  const [activeEntryId, setActiveEntryId] = useState<string | null>(null);

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Conversation-panel layout is derived from displayStatus + this user-driven flag:
  //   streaming  → "expanded" (full panel)
  //   complete   → "rail"     (56px collapsed)
  //   complete + overlayOpen → rail + floating overlay panel
  const [overlayOpen, setOverlayOpen] = useState(false);

  // activeTab lives here so the conversation panel's Follow-up Q&A
  // tab_hint can switch the canvas tab from inside the overlay.
  const [activeTab, setActiveTab] = useState<TabId>("verdict");

  const statusRef = useRef(stream.status);
  useEffect(() => {
    statusRef.current = stream.status;
  }, [stream.status]);

  // ── Derived display values (live vs cached) ──

  const displayStatus: SSEStatus = isLive
    ? stream.status
    : cachedView
      ? "complete"
      : "idle";

  const displayThinkingMessages = isLive
    ? stream.thinkingMessages
    : cachedView?.thinkingMessages ?? EMPTY_MESSAGES;

  const displaySteps = isLive ? stream.steps : cachedView?.steps ?? EMPTY_STEPS;

  const displayVerdict = isLive ? stream.verdict : cachedView?.verdict ?? null;

  const displayError = isLive ? stream.error : null;

  const baseComponents = isLive
    ? stream.components
    : cachedView?.components ?? EMPTY_COMPONENTS;

  const displayComponents = useMemo(() => {
    if (!recalcResult) return baseComponents;

    return baseComponents.map((comp) => {
      switch (comp.component_type) {
        case "dcf_result_card":
          return {
            ...comp,
            props: {
              ...comp.props,
              intrinsic_value_per_share: recalcResult.intrinsic_value_per_share,
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
          return { ...comp, props: { ...comp.props, data: recalcResult.chart_data } };
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

  useEffect(() => {
    if (isLive && ticker && stream.status === "connecting" && !entryIdRef.current) {
      const id = addEntry(ticker);
      entryIdRef.current = id;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- side effect: addEntry mints an id we then expose via state
      setActiveEntryId(id);
    }
  }, [isLive, ticker, stream.status, addEntry]);

  useEffect(() => {
    if (!entryIdRef.current || !isLive) return;
    if (stream.status === "complete") {
      updateEntry(entryIdRef.current, {
        status: "complete",
        verdict: stream.verdict ?? undefined,
      });
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

  const cleanupPrevious = useCallback(() => {
    if (
      entryIdRef.current &&
      (statusRef.current === "connecting" || statusRef.current === "connected")
    ) {
      updateEntry(entryIdRef.current, { status: "error" });
    }
  }, [updateEntry]);

  // ── User actions ──

  const handleSubmitTicker = useCallback(
    (t: string) => {
      cleanupPrevious();
      setTicker(t.toUpperCase());
      setIsLive(true);
      setCachedView(null);
      setRecalcResult(null);
      entryIdRef.current = null;
      setActiveEntryId(null);
      setOverlayOpen(false);
      setActiveTab("verdict");
    },
    [cleanupPrevious]
  );

  const handleSelectHistory = useCallback(
    (entry: HistoryEntry) => {
      const cached = cacheRef.current.get(entry.id);
      if (cached && entry.status === "complete") {
        cleanupPrevious();
        setTicker(entry.ticker);
        setIsLive(false);
        setCachedView(cached);
        setRecalcResult(null);
        entryIdRef.current = entry.id;
        setActiveEntryId(entry.id);
        setOverlayOpen(false);
        setActiveTab("verdict");
      } else {
        handleSubmitTicker(entry.ticker);
      }
    },
    [cleanupPrevious, handleSubmitTicker]
  );

  const handleNewAnalysis = useCallback(() => {
    cleanupPrevious();
    setTicker(null);
    setIsLive(false);
    setCachedView(null);
    setRecalcResult(null);
    entryIdRef.current = null;
    setActiveEntryId(null);
    setOverlayOpen(false);
    setActiveTab("verdict");
  }, [cleanupPrevious]);

  const handleJumpToTab = useCallback((t: TabId) => {
    setActiveTab(t);
    setOverlayOpen(false);
  }, []);

  const handleRecalculate = useCallback(async (data: Record<string, unknown>) => {
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
  }, []);

  const isStreaming = displayStatus === "connecting" || displayStatus === "connected";
  const showRail = !isStreaming && ticker !== null;
  const showOverlay = showRail && overlayOpen;

  const panelCommonProps = {
    ticker,
    status: displayStatus,
    steps: displaySteps,
    thinkingMessages: displayThinkingMessages,
    verdict: displayVerdict,
    error: displayError,
    onSubmitTicker: handleSubmitTicker,
    components: displayComponents,
    onJumpToTab: handleJumpToTab,
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        activeEntryId={activeEntryId}
        onSelectHistory={handleSelectHistory}
        onNewAnalysis={handleNewAnalysis}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
      />
      <div className="flex flex-1 overflow-hidden relative">
        {ticker === null ? (
          <EmptyState onSubmit={handleSubmitTicker} />
        ) : (
          <>
            {/* Inline panel slot: full when streaming, rail when collapsed/overlay */}
            <ConversationPanel
              {...panelCommonProps}
              collapsed={showRail}
              onExpand={() => setOverlayOpen(true)}
            />

            {/* Overlay panel — floats next to the rail without pushing the canvas */}
            {showOverlay && (
              <>
                <button
                  type="button"
                  aria-label="Close conversation overlay"
                  className="absolute inset-0 z-10 bg-black/15 dark:bg-black/40 animate-in fade-in duration-150"
                  onClick={() => setOverlayOpen(false)}
                />
                <div className="absolute left-[56px] top-0 bottom-0 w-[420px] z-20 animate-in slide-in-from-left-3 fade-in duration-200">
                  <ConversationPanel
                    {...panelCommonProps}
                    collapsed={false}
                    showCloseButton
                    onClose={() => setOverlayOpen(false)}
                  />
                </div>
              </>
            )}

            <AnalysisCanvas
              key={activeEntryId ?? `idle-${ticker}`}
              ticker={ticker}
              components={displayComponents}
              thinkingMessages={displayThinkingMessages}
              steps={displaySteps}
              onRecalculate={handleRecalculate}
              status={displayStatus}
              activeTab={activeTab}
              onTabChange={setActiveTab}
            />
          </>
        )}
      </div>
    </div>
  );
}
