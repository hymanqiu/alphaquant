"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/context/auth-context";
import { listWatchlist, removeWatch, upsertWatch } from "@/lib/watchlist-api";
import type { WatchlistItem } from "@/lib/types";

interface WatchlistContextValue {
  items: WatchlistItem[];
  loading: boolean;
  refresh: () => Promise<void>;
  add: (ticker: string, target_mos_pct: number | null) => Promise<WatchlistItem>;
  remove: (ticker: string) => Promise<void>;
  isWatching: (ticker: string) => boolean;
  itemFor: (ticker: string) => WatchlistItem | undefined;
}

const WatchlistContext = createContext<WatchlistContextValue | null>(null);

export function WatchlistProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(false);

  // See SavedThesisProvider for the rationale — abort in-flight refresh on
  // status change so logout can't be clobbered by a late auth'd response.
  const inflightRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    inflightRef.current?.abort();

    if (status !== "authenticated") {
      setItems([]);
      return;
    }
    const controller = new AbortController();
    inflightRef.current = controller;
    setLoading(true);
    try {
      const fresh = await listWatchlist(controller.signal);
      if (!controller.signal.aborted) setItems(fresh);
    } catch {
      // AbortError or network failure — keep stale list.
    } finally {
      if (inflightRef.current === controller) {
        inflightRef.current = null;
        setLoading(false);
      }
    }
  }, [status]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    return () => {
      inflightRef.current?.abort();
    };
  }, []);

  const add = useCallback(
    async (ticker: string, target_mos_pct: number | null) => {
      const t = ticker.toUpperCase();
      const item = await upsertWatch(t, { target_mos_pct });
      setItems((prev) => {
        const filtered = prev.filter((i) => i.ticker !== t);
        return [item, ...filtered];
      });
      return item;
    },
    []
  );

  const remove = useCallback(async (ticker: string) => {
    const t = ticker.toUpperCase();
    await removeWatch(t);
    setItems((prev) => prev.filter((i) => i.ticker !== t));
  }, []);

  const isWatching = useCallback(
    (ticker: string) => {
      const t = ticker.toUpperCase();
      return items.some((i) => i.ticker === t);
    },
    [items]
  );

  const itemFor = useCallback(
    (ticker: string) => items.find((i) => i.ticker === ticker.toUpperCase()),
    [items]
  );

  const value = useMemo<WatchlistContextValue>(
    () => ({ items, loading, refresh, add, remove, isWatching, itemFor }),
    [items, loading, refresh, add, remove, isWatching, itemFor]
  );

  return (
    <WatchlistContext.Provider value={value}>
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist(): WatchlistContextValue {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error("useWatchlist must be used within WatchlistProvider");
  return ctx;
}
