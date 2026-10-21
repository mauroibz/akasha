import type { HTMLAttributes } from "react";

import { AkashaMark } from "@/components/AkashaMark";

import { cn } from "@/lib/utils";

/** A quiet shape where content will be (Sprint 091). Reduced motion stops the pulse. */
export function Skeleton({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}

type Shape = "page" | "detail" | "list" | "grid" | "lines";

/**
 * A loading state: the page keeps its shape while it waits, and the sentence a
 * screen reader hears is the same one the page used to show (`role="status"`, one
 * live region, DEC-028). Replaces the bare "Loading…" text of D6.
 */
export function Loading({
  label,
  shape = "lines",
  className,
}: {
  label: string;
  shape?: Shape;
  className?: string;
}) {
  return (
    // `role="status"` alone, no `aria-live` attribute: a modal hides the rest of the
    // page from assistive technology except `[aria-live]` elements and their
    // ancestors, so the attribute would keep a whole page readable behind a dialog.
    <div role="status" className={cn("w-full", className)}>
      <span className="sr-only">{label}</span>
      {shape === "page" && (
        <div className="space-y-6">
          {/* The brand's point of light, breathing in its arch: the one place a
              whole page waits (Sprint 092). */}
          <AkashaMark size={36} breathing className="text-muted-foreground" />
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-10 w-72 max-w-full" />
          <Skeleton className="h-4 w-96 max-w-full" />
          <Lines count={4} />
        </div>
      )}
      {shape === "detail" && (
        <div className="grid gap-8 sm:grid-cols-[15rem_1fr]">
          <Skeleton className="aspect-[2/3] w-full max-w-60" />
          <div className="space-y-4">
            <Skeleton className="h-14 w-3/4" />
            <Skeleton className="h-4 w-48" />
            <Lines count={5} />
          </div>
        </div>
      )}
      {shape === "list" && (
        <div className="space-y-3">
          {Array.from({ length: 5 }, (_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="h-14 w-10 shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </div>
          ))}
        </div>
      )}
      {shape === "grid" && (
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-4 lg:grid-cols-6">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index} className="space-y-2">
              <Skeleton className="aspect-[2/3] w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      )}
      {shape === "lines" && <Lines count={3} />}
    </div>
  );
}

function Lines({ count }: { count: number }) {
  const widths = ["w-full", "w-11/12", "w-4/5", "w-2/3", "w-3/4"];
  return (
    <div className="space-y-2.5">
      {Array.from({ length: count }, (_, index) => (
        <Skeleton
          key={index}
          className={cn("h-4", widths[index % widths.length])}
        />
      ))}
    </div>
  );
}
