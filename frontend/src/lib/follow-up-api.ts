"use client";

import { apiRequest } from "./api-client";
import type {
  ComponentInstruction,
  FollowUpAnswer,
  HeroSnapshot,
} from "./types";

interface FollowUpRequest {
  ticker: string;
  question: string;
  hero_snapshot: HeroSnapshot | null;
  components_snapshot: Pick<ComponentInstruction, "component_type" | "props">[];
}

export function askFollowUp(req: FollowUpRequest): Promise<FollowUpAnswer> {
  return apiRequest<FollowUpAnswer>("/api/follow-up", {
    method: "POST",
    body: req,
  });
}
