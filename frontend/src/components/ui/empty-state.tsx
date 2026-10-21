import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * An empty place, said once and with a way forward (Sprint 091, D7).
 *
 * The arch without its dot: the brand's "arch enclosing a single point of light"
 * (BRAND.md), with nothing in it yet. Always offers one next step when there is one.
 */
export function EmptyState({
  title,
  children,
  action,
  className,
}: {
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-12 text-center",
        className,
      )}
    >
      <svg
        width="56"
        height="56"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.4}
        strokeLinecap="round"
        aria-hidden="true"
        className="text-muted-foreground/60"
      >
        <path d="M4 21V10a8 8 0 0 1 16 0v11" />
      </svg>
      <h2 className="font-display text-2xl font-medium">{title}</h2>
      {children ? (
        <div className="max-w-md text-sm text-muted-foreground">{children}</div>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
