import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface PanelProps
  extends Omit<HTMLAttributes<HTMLElement>, "className"> {
  /** The panel's own heading. Absent means no header row at all. */
  heading?: ReactNode;
  headingId?: string;
  /** The right-hand stat slot — a count, a share, anything that names quantity. */
  stat?: ReactNode;
  className?: string;
  /**
   * The body wrapper's own classes. Defaults to one padding scale
   * (`px-4 pb-4`/`p-4`); a panel whose body is itself several differently-padded
   * regions — the insights card generalizes into exactly this — passes `""` and
   * keeps its own internal spacing instead of a second, fighting one.
   */
  bodyClassName?: string;
  children?: ReactNode;
}

/**
 * One box (proposal §3.1): `rounded-xl border border-border bg-surface`, an
 * optional heading row with a right-hand stat slot, one padding scale.
 *
 * The insights card generalized (deliverable 1) — `InsightsCard` now builds on
 * this rather than writing its own `rounded-xl border ...` idiom, and Detail,
 * Shelves, Import and Add's hand-built boxes (finding 7: two radii, three heading
 * styles, one of them an amber uppercase label that read as decoration rather
 * than as a heading) are replaced by it too. Amber marks quantity and active
 * state now; it does not mark "this is a heading" anywhere.
 */
export function Panel({
  heading,
  headingId,
  stat,
  className,
  bodyClassName,
  children,
  ...rest
}: PanelProps) {
  const hasHeader = heading !== undefined || stat !== undefined;
  return (
    <section
      className={cn("rounded-xl border border-border bg-surface", className)}
      {...rest}
    >
      {hasHeader && (
        <div className="flex items-baseline justify-between gap-3 px-4 pb-2 pt-4">
          {heading !== undefined && (
            <h2 id={headingId} className="text-sm font-semibold">
              {heading}
            </h2>
          )}
          {stat !== undefined && (
            <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
              {stat}
            </span>
          )}
        </div>
      )}
      <div
        className={cn(
          bodyClassName ?? (hasHeader ? "px-4 pb-4" : "p-4"),
        )}
      >
        {children}
      </div>
    </section>
  );
}
