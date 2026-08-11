import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import {
  scoreBand,
  scoreFillClass,
  scoreTextClass,
  scoreTrailClass,
} from "@/lib/score";

interface ScorePickerProps {
  value: number | null;
  provisional?: boolean;
  onChange: (score: number | null) => void;
  label?: string;
  compact?: boolean;
}

/**
 * Deliberately bespoke rather than a Radix `Popover` (DEC-026). Radix portals
 * its content to `document.body`; the compact panel is required to stay
 * geometrically inside its library card, which is the DEC-023 virtualization
 * contract and the exact defect Sprint 013 repaired. `frontend/e2e/library.spec.ts`
 * asserts that containment. Do not "finish the migration" here.
 */
export function ScorePicker({
  value,
  provisional,
  onChange,
  label = "Score",
  compact,
}: ScorePickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) return;
    const onClick = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      )
        setEditing(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setEditing(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [editing]);

  const trigger = (
    <button
      type="button"
      className={cn(
        "min-h-11 rounded-lg border px-3 text-center font-medium focus-ring",
        // A provisional score is an import's guess, not the owner's verdict, so
        // it is marked by an unfinished-looking border rather than by a colour
        // that would collide with the ramp.
        provisional ? "border-dashed border-primary/60" : "border-border",
        value === null
          ? "text-muted-foreground"
          : scoreTextClass[scoreBand(value)],
        compact && "h-9 min-h-0 shrink-0 px-2 text-sm",
      )}
      aria-expanded={editing}
      aria-label={`${label}: ${value ?? "unscored"}`}
      data-provisional={provisional ? "true" : "false"}
      onClick={() => setEditing((open) => !open)}
    >
      {value ?? "—"}
      {provisional && (
        <span
          aria-hidden="true"
          className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-primary"
        />
      )}
    </button>
  );

  const panel = (
    <div
      className="flex flex-col gap-1"
      data-score-panel=""
      role="group"
      aria-label={label}
    >
      {/* Compact mode wraps into two rows of five so the whole picker fits
          inside a library card at the narrowest supported viewport. */}
      <div className={compact ? "grid grid-cols-5 gap-1" : "flex gap-0.5"}>
        {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            type="button"
            className={cn(
              "w-8 rounded-md text-sm font-medium transition-colors focus-ring",
              compact ? "h-9" : "h-11",
              n === value
                ? scoreFillClass[scoreBand(n)]
                : value !== null && n < value
                  ? scoreTrailClass[scoreBand(value)]
                  : "bg-surface-raised text-muted-foreground hover:bg-surface-raised/70",
            )}
            aria-label={`Score ${n}`}
            aria-pressed={n === value}
            onClick={() => {
              onChange(n);
              setEditing(false);
            }}
          >
            {n}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="self-start rounded text-xs text-muted-foreground hover:text-foreground focus-ring"
        onClick={() => {
          onChange(null);
          setEditing(false);
        }}
      >
        Clear score
      </button>
    </div>
  );

  // Compact pickers live inside fixed-height virtual cards, so the expanded
  // panel is an overlay anchored above the trigger: it never changes the card's
  // layout box and cannot push neighbouring content around.
  if (compact)
    return (
      <div className="relative shrink-0" ref={containerRef}>
        {trigger}
        {editing && (
          <div className="absolute bottom-full right-0 z-20 mb-2 w-max rounded-xl border border-border bg-popover p-2 shadow-2xl">
            {panel}
          </div>
        )}
      </div>
    );

  if (!editing) return trigger;

  return (
    <div className="inline-flex" ref={containerRef}>
      {panel}
    </div>
  );
}
