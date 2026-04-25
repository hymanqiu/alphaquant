"use client";

import { API_BASE_URL } from "./constants";
import type { AuthSessionResponse, AuthUser } from "./types";

/** Standardized API error wrapping detail.error / detail.message shapes. */
export class AuthApiError extends Error {
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

async function parseError(res: Response): Promise<AuthApiError> {
  let body: ApiErrorBody = {};
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    // ignore
  }
  const detail = body.detail;
  if (typeof detail === "string") {
    return new AuthApiError(res.status, detail);
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    return new AuthApiError(
      res.status,
      String(detail.message ?? detail.error ?? `HTTP ${res.status}`),
      typeof detail.error === "string" ? detail.error : undefined
    );
  }
  return new AuthApiError(res.status, `HTTP ${res.status}`);
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    credentials: "include",
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

// --- Email/password ----------------------------------------------------------

export function registerEmail(payload: {
  email: string;
  password: string;
  display_name?: string;
}): Promise<AuthSessionResponse> {
  return postJson<AuthSessionResponse>("/api/auth/email/register", payload);
}

export function loginEmail(payload: {
  email: string;
  password: string;
}): Promise<AuthSessionResponse> {
  return postJson<AuthSessionResponse>("/api/auth/email/login", payload);
}

// --- Magic link --------------------------------------------------------------

export function sendMagicLink(payload: {
  email: string;
}): Promise<{ sent: true; dev_link?: string }> {
  return postJson("/api/auth/magic-link/send", payload);
}

export function verifyMagicLink(payload: {
  token: string;
}): Promise<AuthSessionResponse> {
  return postJson<AuthSessionResponse>("/api/auth/magic-link/verify", payload);
}

// --- Google OAuth (start = redirect, no JSON) --------------------------------

export const googleStartUrl = `${API_BASE_URL}/api/auth/google/start`;

// --- Session lifecycle -------------------------------------------------------

export async function fetchMe(): Promise<AuthUser | null> {
  try {
    const data = await getJson<{ user: AuthUser }>("/api/auth/me");
    return data.user;
  } catch (e) {
    if (e instanceof AuthApiError && e.status === 401) return null;
    throw e;
  }
}

export async function logout(): Promise<void> {
  await postJson("/api/auth/logout", {});
}
