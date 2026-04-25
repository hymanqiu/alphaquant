"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/auth-context";
import { AuthApiError } from "@/lib/auth-api";
import { Loader2 } from "lucide-react";

function RegisterInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const { registerWithPassword } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await registerWithPassword(email, password, displayName || undefined);
      router.replace(next);
    } catch (e) {
      const msg =
        e instanceof AuthApiError
          ? e.code === "email_taken"
            ? "An account with that email already exists."
            : e.message
          : "Sign up failed";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-[18px]">Create your account</CardTitle>
          <p className="text-[12px] text-muted-foreground">
            Free tier: 3 analyses per day. Pro features unlock with subscription.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="space-y-1">
              <label className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground">
                Email
              </label>
              <Input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground">
                Display name (optional)
              </label>
              <Input
                type="text"
                autoComplete="name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground">
                Password (8+ chars)
              </label>
              <Input
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting && <Loader2 className="h-3 w-3 mr-2 animate-spin" />}
              Sign up
            </Button>
          </form>

          {error && (
            <p className="text-[12px] text-red-600 dark:text-red-400 mt-3">
              {error}
            </p>
          )}

          <p className="text-[11.5px] text-muted-foreground mt-4 text-center">
            Already have an account?{" "}
            <Link
              href={`/auth/login?next=${encodeURIComponent(next)}`}
              className="text-[var(--brand)] hover:underline"
            >
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterInner />
    </Suspense>
  );
}
