"use client";

import { apiRequest } from "./api-client";
import type {
  ComponentInstruction,
  HeroSnapshot,
  SavedThesisFull,
  SavedThesisSummary,
} from "./types";

interface CreateRequest {
  ticker: string;
  title?: string | null;
  is_public?: boolean;
  hero_snapshot: HeroSnapshot;
  components_snapshot: ComponentInstruction[];
}

export function createSavedThesis(req: CreateRequest): Promise<SavedThesisFull> {
  return apiRequest<SavedThesisFull>("/api/saved-thesis", {
    method: "POST",
    body: req,
  });
}

export async function listSavedTheses(
  signal?: AbortSignal
): Promise<SavedThesisSummary[]> {
  const res = await apiRequest<{ items: SavedThesisSummary[] }>(
    "/api/saved-thesis",
    { signal }
  );
  return res.items;
}

export function getSavedThesis(id: string): Promise<SavedThesisFull> {
  return apiRequest<SavedThesisFull>(`/api/saved-thesis/${encodeURIComponent(id)}`);
}

export function deleteSavedThesis(id: string): Promise<void> {
  return apiRequest<void>(`/api/saved-thesis/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

/** Public, no-auth variant — used by the share route. */
export function getPublicThesis(id: string): Promise<SavedThesisFull> {
  return apiRequest<SavedThesisFull>(`/api/share/thesis/${encodeURIComponent(id)}`);
}
