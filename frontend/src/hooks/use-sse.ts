"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SSEEventData, SSEStatus } from "@/lib/types";

interface UseSSEOptions {
  url: string;
  enabled?: boolean;
}

interface UseSSEReturn {
  status: SSEStatus;
  events: SSEEventData[];
  error: string | null;
}

const EVENT_TYPES = [
  "agent_thinking",
  "component",
  "step_complete",
  "analysis_complete",
  "error",
] as const;

export function useSSE({ url, enabled = true }: UseSSEOptions): UseSSEReturn {
  const [status, setStatus] = useState<SSEStatus>("idle");
  const [events, setEvents] = useState<SSEEventData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      cleanup();
      setStatus("idle");
      return;
    }

    setStatus("connecting");
    setEvents([]);
    setError(null);

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      setStatus("connected");
    };

    es.onerror = () => {
      // EventSource auto-reconnects; only set error if closed
      if (es.readyState === EventSource.CLOSED) {
        setStatus("error");
        setError("Connection lost");
      }
    };

    // Register handlers for each known event type
    for (const type of EVENT_TYPES) {
      es.addEventListener(type, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as SSEEventData;
          setEvents((prev) => [...prev, data]);

          if (data.event === "analysis_complete") {
            setStatus("complete");
            es.close();
          }
          if (data.event === "error" && !data.recoverable) {
            setStatus("error");
            setError(data.message);
            es.close();
          }
        } catch {
          // Ignore malformed events
        }
      });
    }

    return cleanup;
  }, [url, enabled, cleanup]);

  return { status, events, error };
}
