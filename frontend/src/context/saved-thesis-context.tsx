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
import {
  createSavedThesis,
  deleteSavedThesis,
  listSavedTheses,
} from "@/lib/saved-thesis-api";
import type {
  ComponentInstruction,
  HeroSnapshot,
  SavedThesisFull,
  SavedThesisSummary,
} from "@/lib/types";

interface SavedThesisContextValue {
  items: SavedThesisSummary[];
  loading: boolean;
  refresh: () => Promise<void>;
  save: (input: {
    ticker: string;
    title?: string | null;
    is_public?: boolean;
    hero_snapshot: HeroSnapshot;
    components_snapshot: ComponentInstruction[];
  }) => Promise<SavedThesisFull>;
  remove: (id: string) => Promise<void>;
}

const SavedThesisContext = createContext<SavedThesisContextValue | null>(null);

export function SavedThesisProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const [items, setItems] = useState<SavedThesisSummary[]>([]);
  const [loading, setLoading] = useState(false);

  // Tracks the in-flight refresh request so we can abort it if status changes
  // (e.g. logout) — prevents stale auth'd data from clobbering anonymous state.
  const inflightRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    // Cancel any prior refresh still in-flight; its setState will be skipped.
    inflightRef.current?.abort();

    if (status !== "authenticated") {
      setItems([]);
      return;
    }
    const controller = new AbortController();
    inflightRef.current = controller;
    setLoading(true);
    try {
      const fresh = await listSavedTheses(controller.signal);
      // Guard against the post-await race: an even newer refresh could have
      // aborted between resolution and this line.
      if (!controller.signal.aborted) setItems(fresh);
    } catch {
      // AbortError or network failure — keep stale list, don't blank sidebar.
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

  // Abort any in-flight request on unmount so a late response can't setState
  // after this provider is gone.
  useEffect(() => {
    return () => {
      inflightRef.current?.abort();
    };
  }, []);

  const save = useCallback(
    async (input: {
      ticker: string;
      title?: string | null;
      is_public?: boolean;
      hero_snapshot: HeroSnapshot;
      components_snapshot: ComponentInstruction[];
    }) => {
      const created = await createSavedThesis(input);
      setItems((prev) => [
        {
          id: created.id,
          ticker: created.ticker,
          title: created.title,
          is_public: created.is_public,
          created_at: created.created_at,
          hero_snapshot: created.hero_snapshot,
        },
        ...prev,
      ]);
      return created;
    },
    []
  );

  const remove = useCallback(async (id: string) => {
    await deleteSavedThesis(id);
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value = useMemo<SavedThesisContextValue>(
    () => ({ items, loading, refresh, save, remove }),
    [items, loading, refresh, save, remove]
  );

  return (
    <SavedThesisContext.Provider value={value}>
      {children}
    </SavedThesisContext.Provider>
  );
}

export function useSavedTheses(): SavedThesisContextValue {
  const ctx = useContext(SavedThesisContext);
  if (!ctx) {
    throw new Error("useSavedTheses must be used within SavedThesisProvider");
  }
  return ctx;
}
