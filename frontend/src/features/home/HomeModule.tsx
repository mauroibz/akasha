import { useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * One module of Home (Sprint 130): a box with a heading and an optional right-hand
 * note, the library's own surface and border. Labelled by its heading, so each
 * module is a named region a screen reader can jump to.
 */
export function HomeModule({
  title,
  aside,
  className,
  children,
}: {
  title: ReactNode;
  aside?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      className={cn(
        "min-w-0 rounded-xl border border-border bg-surface p-4",
        className,
      )}
    >
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2
          id={headingId}
          className="font-display text-lg font-medium tracking-tight"
        >
          {title}
        </h2>
        {aside ? (
          <div className="min-w-0 truncate text-xs text-muted-foreground">
            {aside}
          </div>
        ) : null}
      </div>
      {children}
    </section>
  );
}
