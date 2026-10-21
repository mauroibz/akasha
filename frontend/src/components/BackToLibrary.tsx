import { Link, useNavigate } from "react-router-dom";

import { cn } from "@/lib/utils";
import { navigateWithTransition } from "@/lib/viewTransition";

/**
 * The one way back (proposal §3.2, finding 8).
 *
 * Detail, Shelves and Add each wrote an identical ghost button; Triage wrote an
 * outline pill in its header actions; Import wrote a bare `<Link>` for the primary
 * screen and the words *"← Back to library"* in its own undo panel — four spellings
 * of the same control. This is the one, used everywhere a screen needs to return
 * somewhere.
 *
 * Most callers want the library and say nothing; a detail page opened *from*
 * somewhere (triage) names that place instead, so back returns the reader to the
 * screen they actually came from.
 */
export function BackToLibrary({
  className,
  to = "/",
  label = "Library",
}: {
  className?: string;
  to?: string;
  label?: string;
}) {
  const navigate = useNavigate();
  return (
    <Link
      className={cn(
        "focus-ring inline-flex min-h-11 items-center rounded-full px-0 text-sm font-medium text-foreground transition-colors hover:text-primary",
        className,
      )}
      to={to}
      // The cover shrinks back into its card (Sprint 092). A modified click
      // (new tab, new window) is left to the browser.
      onClick={(event) => {
        if (
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.button !== 0
        )
          return;
        event.preventDefault();
        navigateWithTransition(navigate, to);
      }}
    >
      ← {label}
    </Link>
  );
}
