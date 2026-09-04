import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

/**
 * The one way back (proposal §3.2, finding 8).
 *
 * Detail, Shelves and Add each wrote an identical ghost button; Triage wrote an
 * outline pill in its header actions; Import wrote a bare `<Link>` for the primary
 * screen and the words *"← Back to library"* in its own undo panel — four spellings
 * of the same control. This is the one, used everywhere a screen needs to return to
 * the library.
 */
export function BackToLibrary({ className }: { className?: string }) {
  return (
    <Link
      className={cn(
        "focus-ring inline-flex min-h-11 items-center rounded-full px-0 text-sm font-medium text-foreground transition-colors hover:text-primary",
        className,
      )}
      to="/"
    >
      ← Library
    </Link>
  );
}
