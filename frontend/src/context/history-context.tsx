"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { HistoryEntry } from "@/lib/types";

const STORAGE_KEY = "alphaquant:history";
const MAX_ENTRIES = 50;

interface HistoryContextValue {
  entries: HistoryEntry[];
  addEntry: (ticker: string) => string;
  updateEntry: (
    id: string,
    updates: Partial<Pick<HistoryEntry, "status" | "verdict">>
  ) => void;
  removeEntry: (id: string) => void;
}

const HistoryContext = createContext<HistoryContextValue | null>(null);

function loadHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(entries: HistoryEntry[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // quota exceeded — silently ignore
  }
}

export function HistoryProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setEntries(loadHistory());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) saveHistory(entries);
  }, [entries, hydrated]);

  const addEntry = useCallback((ticker: string) => {
    const id = `${ticker}-${Date.now()}`;
    const entry: HistoryEntry = {
      id,
      ticker: ticker.toUpperCase(),
      timestamp: Date.now(),
      status: "running",
    };
    setEntries((prev) => [entry, ...prev].slice(0, MAX_ENTRIES));
    return id;
  }, []);

  const updateEntry = useCallback(
    (
      id: string,
      updates: Partial<Pick<HistoryEntry, "status" | "verdict">>
    ) => {
      setEntries((prev) =>
        prev.map((e) => (e.id === id ? { ...e, ...updates } : e))
      );
    },
    []
  );

  const removeEntry = useCallback((id: string) => {
    setEntries((prev) => prev.filter((e) => e.id !== id));
  }, []);

  return (
    <HistoryContext.Provider
      value={{ entries, addEntry, updateEntry, removeEntry }}
    >
      {children}
    </HistoryContext.Provider>
  );
}

export function useHistory() {
  const ctx = useContext(HistoryContext);
  if (!ctx) throw new Error("useHistory must be used within HistoryProvider");
  return ctx;
}
