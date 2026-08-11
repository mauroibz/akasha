import { useEffect, useRef, useState } from "react";
import { m, useAnimationControls } from "motion/react";

import { useMotionPresets } from "@/lib/motion";
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
  // The band the reader is currently pointing at, which is not yet a decision.
  // Only the colour follows it; the number keeps telling the truth.
  const [preview, setPreview] = useState<number | null>(null);
  const shown = preview ?? value;
  const presets = useMotionPresets();
  const pop = useAnimationControls();
  const committed = useRef(false);

  // Overshoot and settle when the value changes, whichever way it was set --
  // the panel, the clear button, or the number-key shortcut on a focused row,
  // all of which arrive here as a new `value`.
  useEffect(() => {
    if (!committed.current) {
      committed.current = true;
      return;
    }
    if (presets.commitPop.from) pop.set(presets.commitPop.from);
    void pop.start(presets.commitPop.to);
  }, [value, pop, presets]);

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
    <m.button
      type="button"
      animate={pop}
      whileTap={presets.press}
      className={cn(
        "min-h-11 rounded-lg border px-3 text-center font-medium transition-colors focus-ring",
        // A provisional score is an import's guess, not the owner's verdict, so
        // it is marked by an unfinished-looking border rather than by a colour
        // that would collide with the ramp.
        provisional ? "border-dashed border-primary/60" : "border-border",
        shown === null
          ? "text-muted-foreground"
          : scoreTextClass[scoreBand(shown)],
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
    </m.button>
  );

  const panel = (
    <div
      className="flex flex-col gap-1"
      data-score-panel=""
      role="group"
      aria-label={label}
      onPointerLeave={() => setPreview(null)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          setPreview(null);
      }}
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
              n === shown
                ? scoreFillClass[scoreBand(n)]
                : shown !== null && n < shown
                  ? scoreTrailClass[scoreBand(shown)]
                  : "bg-surface-raised text-muted-foreground hover:bg-surface-raised/70",
            )}
            aria-label={`Score ${n}`}
            aria-pressed={n === value}
            // Pointer and keyboard get the same preview: sweeping the segments
            // with arrow keys is how the picker is used without a mouse.
            onPointerEnter={() => setPreview(n)}
            onFocus={() => setPreview(n)}
            onClick={() => {
              setPreview(null);
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
          setPreview(null);
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
          // Enter only, and scaling up from 0.96 towards its resting box: the
          // panel can only ever be more contained than the box DEC-023 pins.
          // No exit -- the panel vanishing is the confirmation that the commit
          // landed, and an exiting node inside a recyclable virtual row is a
          // lifecycle hazard for no visible gain.
          <m.div
            className="absolute bottom-full right-0 z-20 mb-2 w-max rounded-xl border border-border bg-popover p-2 shadow-2xl"
            style={{ transformOrigin: "bottom right" }}
            initial={presets.panel.initial}
            animate={presets.panel.animate}
          >
            {panel}
          </m.div>
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
