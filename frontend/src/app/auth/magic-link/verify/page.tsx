"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/context/auth-context";
import { AuthApiError } from "@/lib/auth-api";
import { Loader2 } from "lucide-react";

function VerifyInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { completeMagicLink } = useAuth();
  const [status, setStatus] = useState<"verifying" | "success" | "error">(
    "verifying"
  );
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setStatus("error");
      setMessage("No token in URL.");
      return;
    }
    let cancelled = false;
    completeMagicLink(token)
      .then(() => {
        if (cancelled) return;
        setStatus("success");
        // Brief pause so users see confirmation, then redirect home.
        setTimeout(() => router.replace("/"), 600);
      })
      .catch((e) => {
        if (cancelled) return;
        setStatus("error");
        setMessage(
          e instanceof AuthApiError ? e.message : "Verification failed."
        );
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-[16px]">Verifying sign-in link</CardTitle>
        </CardHeader>
        <CardContent>
          {status === "verifying" && (
            <p className="text-[12.5px] text-muted-foreground inline-flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" />
              Checking your link...
            </p>
          )}
          {status === "success" && (
            <p className="text-[12.5px] text-emerald-600 dark:text-emerald-400">
              Signed in successfully. Redirecting…
            </p>
          )}
          {status === "error" && (
            <p className="text-[12.5px] text-red-600 dark:text-red-400">
              {message}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function VerifyMagicLinkPage() {
  return (
    <Suspense fallback={null}>
      <VerifyInner />
    </Suspense>
  );
}
