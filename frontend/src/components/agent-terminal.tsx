"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ThinkingMessage } from "@/lib/types";

const NODE_COLORS: Record<string, string> = {
  fetch_sec_data: "bg-blue-500",
  financial_health_scan: "bg-emerald-500",
  dynamic_dcf: "bg-amber-500",
  strategy: "bg-rose-500",
  logic_trace: "bg-purple-500",
};

const NODE_LABELS: Record<string, string> = {
  fetch_sec_data: "SEC Fetch",
  financial_health_scan: "Health Scan",
  dynamic_dcf: "DCF Model",
  strategy: "Strategy",
  logic_trace: "Source Trace",
};

interface AgentTerminalProps {
  messages: ThinkingMessage[];
  isActive: boolean;
}

function TypewriterText({ text, onComplete }: { text: string; onComplete?: () => void }) {
  const [displayed, setDisplayed] = useState("");
  const indexRef = useRef(0);

  useEffect(() => {
    indexRef.current = 0;
    setDisplayed("");

    const interval = setInterval(() => {
      if (indexRef.current < text.length) {
        setDisplayed(text.slice(0, indexRef.current + 1));
        indexRef.current++;
      } else {
        clearInterval(interval);
        onComplete?.();
      }
    }, 15);

    return () => clearInterval(interval);
  }, [text, onComplete]);

  return <>{displayed}</>;
}

export function AgentTerminal({ messages, isActive }: AgentTerminalProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [completedCount, setCompletedCount] = useState(0);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, completedCount]);

  // Auto-complete old messages when new ones arrive
  useEffect(() => {
    if (messages.length > 1) {
      setCompletedCount(messages.length - 1);
    }
  }, [messages.length]);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${isActive ? "bg-green-500 animate-pulse" : "bg-gray-400"}`} />
          Agent Reasoning
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden px-4 pb-4">
        <div
          ref={scrollRef}
          className="h-full overflow-y-auto font-mono text-sm space-y-2 pr-2"
        >
          {messages.map((msg, i) => {
            const isLast = i === messages.length - 1;
            const isCompleted = i < completedCount;

            return (
              <div key={i} className={`flex gap-2 ${isCompleted ? "opacity-60" : ""}`}>
                <Badge
                  variant="secondary"
                  className={`${NODE_COLORS[msg.node] || "bg-gray-500"} text-white text-[10px] shrink-0 h-5`}
                >
                  {NODE_LABELS[msg.node] || msg.node}
                </Badge>
                <span className="text-muted-foreground leading-5">
                  {isLast && !isCompleted ? (
                    <>
                      <TypewriterText
                        text={msg.content}
                        onComplete={() => setCompletedCount(i + 1)}
                      />
                      {isActive && <span className="animate-pulse">|</span>}
                    </>
                  ) : (
                    msg.content
                  )}
                </span>
              </div>
            );
          })}
          {messages.length === 0 && isActive && (
            <div className="text-muted-foreground animate-pulse">
              Initializing analysis...
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
