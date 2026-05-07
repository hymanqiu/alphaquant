"use client";

import { apiRequest } from "./api-client";
import type { WatchlistItem } from "./types";

interface UpsertRequest {
  target_mos_pct?: number | null;
}

export async function listWatchlist(
  signal?: AbortSignal
): Promise<WatchlistItem[]> {
  const res = await apiRequest<{ items: WatchlistItem[] }>("/api/watchlist", {
    signal,
  });
  return res.items;
}

export function upsertWatch(
  ticker: string,
  body: UpsertRequest
): Promise<WatchlistItem> {
  return apiRequest<WatchlistItem>(`/api/watchlist/${encodeURIComponent(ticker)}`, {
    method: "PUT",
    body,
  });
}

export function removeWatch(ticker: string): Promise<void> {
  return apiRequest<void>(`/api/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE",
  });
}
