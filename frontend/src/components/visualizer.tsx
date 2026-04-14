"use client";

import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { getComponent } from "@/components/component-registry";
import type { ComponentInstruction } from "@/lib/types";

interface VisualizerProps {
  components: ComponentInstruction[];
  onRecalculate?: (data: Record<string, unknown>) => void;
}

export function Visualizer({ components, onRecalculate }: VisualizerProps) {
  if (components.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {components.map((instruction) => {
        const Component = getComponent(instruction.component_type);
        if (!Component) {
          return (
            <div
              key={instruction.id}
              className="p-4 border border-dashed rounded-lg text-muted-foreground text-sm"
            >
              Unknown component: {instruction.component_type}
            </div>
          );
        }
        return (
          <Suspense
            key={instruction.id}
            fallback={<Skeleton className="h-48 w-full rounded-lg" />}
          >
            <Component {...instruction.props} onRecalculate={onRecalculate} />
          </Suspense>
        );
      })}
    </div>
  );
}
