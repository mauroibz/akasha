import { ChevronDown } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A native `<select>` drawn in the theme (Sprint 091, D8).
 *
 * Native on purpose rather than Radix: on a phone the platform's own picker is the
 * better control, and the Triage rows hold dozens of these where a portal per row
 * would cost. Only the drawing changes: no browser chrome, the theme's surface and a
 * chevron that matches the rest of the icons.
 */
export const NativeSelect = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement> & { wrapperClassName?: string }
>(({ className, wrapperClassName, children, ...props }, ref) => (
  <span className={cn("relative inline-flex w-full", wrapperClassName)}>
    <select
      ref={ref}
      className={cn(
        "h-11 w-full appearance-none rounded-md border border-input bg-surface-raised pl-3 pr-9 text-base text-foreground focus-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
    <ChevronDown
      aria-hidden="true"
      className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
    />
  </span>
));
NativeSelect.displayName = "NativeSelect";
