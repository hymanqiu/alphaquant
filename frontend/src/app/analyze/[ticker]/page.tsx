"use client";

import { use } from "react";
import { AppShell } from "@/components/layout/app-shell";

export default function AnalyzePage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = use(params);

  return <AppShell initialTicker={ticker} />;
}
