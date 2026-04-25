"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  fetchMe,
  loginEmail,
  logout as apiLogout,
  registerEmail,
  verifyMagicLink,
} from "@/lib/auth-api";
import type { AuthUser } from "@/lib/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  isPro: boolean;
  refresh: () => Promise<void>;
  loginWithPassword: (email: string, password: string) => Promise<AuthUser>;
  registerWithPassword: (
    email: string,
    password: string,
    displayName?: string
  ) => Promise<AuthUser>;
  completeMagicLink: (token: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const refresh = useCallback(async () => {
    try {
      const u = await fetchMe();
      setUser(u);
      setStatus(u ? "authenticated" : "anonymous");
    } catch {
      // Network / 5xx — fall back to anonymous, surface via console.
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const loginWithPassword = useCallback(
    async (email: string, password: string) => {
      const { user: u } = await loginEmail({ email, password });
      setUser(u);
      setStatus("authenticated");
      return u;
    },
    []
  );

  const registerWithPassword = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const { user: u } = await registerEmail({
        email,
        password,
        display_name: displayName,
      });
      setUser(u);
      setStatus("authenticated");
      return u;
    },
    []
  );

  const completeMagicLink = useCallback(async (token: string) => {
    const { user: u } = await verifyMagicLink({ token });
    setUser(u);
    setStatus("authenticated");
    return u;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      isPro: user?.tier === "pro" || user?.tier === "admin",
      refresh,
      loginWithPassword,
      registerWithPassword,
      completeMagicLink,
      logout,
    }),
    [
      user,
      status,
      refresh,
      loginWithPassword,
      registerWithPassword,
      completeMagicLink,
      logout,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
