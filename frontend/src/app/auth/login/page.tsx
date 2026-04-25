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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { useAuth } from "@/context/auth-context";
import { AuthApiError, googleStartUrl, sendMagicLink } from "@/lib/auth-api";
import { Loader2, Mail, KeyRound, Globe } from "lucide-react";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const { loginWithPassword } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [magicEmail, setMagicEmail] = useState("");
  const [magicSent, setMagicSent] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await loginWithPassword(email, password);
      router.replace(next);
    } catch (e) {
      const msg =
        e instanceof AuthApiError ? e.message : "Login failed";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleMagicSend(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMagicSent(null);
    setDevLink(null);
    setSubmitting(true);
    try {
      const result = await sendMagicLink({ email: magicEmail });
      setMagicSent(magicEmail);
      if (result.dev_link) setDevLink(result.dev_link);
    } catch (e) {
      const msg = e instanceof AuthApiError ? e.message : "Failed to send link";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-[18px]">Sign in to AlphaQuant</CardTitle>
          <p className="text-[12px] text-muted-foreground">
            Choose any sign-in method below.
          </p>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="password" className="space-y-4">
            <TabsList className="grid grid-cols-3 w-full">
              <TabsTrigger value="password" className="text-[12px]">
                <KeyRound className="h-3 w-3 mr-1" />
                Password
              </TabsTrigger>
              <TabsTrigger value="magic" className="text-[12px]">
                <Mail className="h-3 w-3 mr-1" />
                Magic link
              </TabsTrigger>
              <TabsTrigger value="google" className="text-[12px]">
                <Globe className="h-3 w-3 mr-1" />
                Google
              </TabsTrigger>
            </TabsList>

            <TabsContent value="password">
              <form onSubmit={handlePasswordSubmit} className="space-y-3">
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
                    Password
                  </label>
                  <Input
                    type="password"
                    autoComplete="current-password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
                <Button type="submit" disabled={submitting} className="w-full">
                  {submitting && <Loader2 className="h-3 w-3 mr-2 animate-spin" />}
                  Sign in
                </Button>
              </form>
              <p className="text-[11.5px] text-muted-foreground mt-3 text-center">
                No account?{" "}
                <Link
                  href={`/auth/register?next=${encodeURIComponent(next)}`}
                  className="text-[var(--brand)] hover:underline"
                >
                  Create one
                </Link>
              </p>
            </TabsContent>

            <TabsContent value="magic">
              {magicSent ? (
                <div className="space-y-3">
                  <p className="text-[12.5px] leading-relaxed">
                    A sign-in link has been sent to <b>{magicSent}</b>. Open
                    your inbox and click the link to continue. The link expires
                    in 15 minutes.
                  </p>
                  {devLink && (
                    <div className="rounded-md border bg-amber-500/5 ring-1 ring-amber-500/20 p-3">
                      <p className="text-[10px] uppercase tracking-wider font-medium text-amber-700 dark:text-amber-400 mb-1">
                        Dev fallback (no email provider configured)
                      </p>
                      <a
                        href={devLink}
                        className="text-[11px] text-[var(--brand)] hover:underline break-all"
                      >
                        {devLink}
                      </a>
                    </div>
                  )}
                </div>
              ) : (
                <form onSubmit={handleMagicSend} className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground">
                      Email
                    </label>
                    <Input
                      type="email"
                      required
                      value={magicEmail}
                      onChange={(e) => setMagicEmail(e.target.value)}
                    />
                  </div>
                  <Button type="submit" disabled={submitting} className="w-full">
                    {submitting && (
                      <Loader2 className="h-3 w-3 mr-2 animate-spin" />
                    )}
                    Email me a sign-in link
                  </Button>
                </form>
              )}
            </TabsContent>

            <TabsContent value="google">
              <p className="text-[12px] leading-relaxed text-muted-foreground mb-3">
                Sign in with your Google account. We only request your email
                and basic profile.
              </p>
              <a href={googleStartUrl}>
                <Button variant="outline" className="w-full">
                  <Globe className="h-3.5 w-3.5 mr-2" />
                  Continue with Google
                </Button>
              </a>
            </TabsContent>
          </Tabs>

          {error && (
            <p className="text-[12px] text-red-600 dark:text-red-400 mt-3">
              {error}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}
