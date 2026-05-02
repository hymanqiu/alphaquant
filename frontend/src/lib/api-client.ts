"use client";

import { API_BASE_URL } from "./constants";

/** Standardized API error wrapping FastAPI's `{"detail": ...}` shapes. */
export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

interface ApiErrorBody {
  detail?:
    | string
    | { error?: string; message?: string; [k: string]: unknown }
    | Array<unknown>;
}

async function parseError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody = {};
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    // ignore non-JSON error bodies
  }
  const detail = body.detail;
  if (typeof detail === "string") {
    return new ApiError(res.status, detail);
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    return new ApiError(
      res.status,
      String(detail.message ?? detail.error ?? `HTTP ${res.status}`),
      typeof detail.error === "string" ? detail.error : undefined
    );
  }
  return new ApiError(res.status, `HTTP ${res.status}`);
}

interface RequestOpts {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  /** Pass an AbortSignal to cancel the request — used by contexts to avoid
   *  stale-data races when status changes mid-flight (e.g. logout). */
  signal?: AbortSignal;
}

export async function apiRequest<T>(
  path: string,
  opts: RequestOpts = {}
): Promise<T> {
  const { method = "GET", body, signal } = opts;
  const init: RequestInit = {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    signal,
  };
  if (body !== undefined) init.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok) throw await parseError(res);

  // 204 No Content (DELETE) returns nothing.
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
