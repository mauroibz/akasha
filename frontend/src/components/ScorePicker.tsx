import { useEffect, useRef, useState } from "react";
import { m, useAnimationControls } from "motion/react";

import { useMotionPresets } from "@/lib/motion";
import { cn } from "@/lib/utils";
import {
  scoreBand,
  scoreChipClass,
  scoreFillClass,
  scoreTrailClass,
} from "@/lib/score";

interface ScorePickerProps {
  value: number | null;
  provisional?: boolean;
  onChange: (score: number | null) => void;
  label?: string;
  compact?: boolean;
  /**
   * Wall-card mode (Sprint 072): the chip keeps the compact overlay — the
   * panel must stay geometrically inside its card (DEC-023) — but grows to the
   * full 44px target with a ~18px numeral, and the panel opens centred above
   * the chip instead of right-aligned, because the chip no longer sits at the
   * card edge but on the cover's bottom scrim.
   */
  onCover?: boolean;
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
  onCover,
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
        // that would collide with the ramp. On a filled chip that border is
        // knocked out of the fill, the way the numeral is: the accent is amber,
        // and amber is the 4-6 band, so accent-on-fill disappears exactly where
        // a reader most needs to see it. With no score there is no fill to knock
        // out of, and the accent is the legible choice.
        provisional
          ? shown === null
            ? "border-dashed border-primary/60"
            : "border-dashed border-background/80"
          : "border-border",
        scoreChipClass(shown),
        compact && "h-9 min-h-0 shrink-0 px-2 text-sm",
        // The wall card's chip is the full touch target the sprint asks for
        // (AC4): 44px tall with a numeral large enough to read from the room.
        // Listed after the compact clause so it wins on both chips it applies
        // to — the wall card is compact (overlay) *and* on the cover.
        onCover && "h-11 min-h-11 min-w-11 px-2.5 text-lg",
      )}
      aria-expanded={editing}
      // The dashed border and the dot say "provisional" to someone who already
      // knows what they mean. Everyone else — including every screen reader —
      // needs the word.
      aria-label={`${label}: ${value ?? "unscored"}${
        provisional ? " (provisional)" : ""
      }`}
      title={
        provisional
          ? "Provisional score, carried from the import. Setting a score confirms it."
          : undefined
      }
      data-provisional={provisional ? "true" : "false"}
      onClick={() => setEditing((open) => !open)}
    >
      {value ?? "—"}
      {provisional && (
        <span
          aria-hidden="true"
          className={cn(
            "ml-1 inline-block h-1.5 w-1.5 rounded-full",
            value === null ? "bg-primary" : "bg-background",
          )}
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
              // Wall cards can be 190px: five full-width segments would make
              // the panel wider than the card, so they step down half a size.
              onCover && "w-7",
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
      // The wrapper is the panel's positioning context on a library row —
      // right-anchored above the chip. On a wall card it is *not* positioned:
      // the grid card's `data-card-controls` container is, so the panel opens
      // centred above the *card*, not above the chip. Centring over the chip
      // pushes the panel past the card edge — the chip sits off-centre because
      // the status beside it is wider — and re-testing the containment
      // per-view afterwards becomes the fix here.
      <div
        className={cn("shrink-0", !onCover && "relative")}
        ref={containerRef}
      >
        {trigger}
        {editing && (
          // Enter only, and scaling up from 0.96 towards its resting box: the
          // panel can only ever be more contained than the box DEC-023 pins.
          // No exit -- the panel vanishing is the confirmation that the commit
          // landed, and an exiting node inside a recyclable virtual row is a
          // lifecycle hazard for no visible gain.
          //
          // The positioning wrapper owns the placement (right-anchored on a
          // row, centred above the chip on a wall card) so motion's inline
          // scale transform on the panel itself can't knock it off-centre.
          <div
            className={cn(
              "absolute bottom-full z-20 mb-2",
              onCover ? "left-1/2 -translate-x-1/2" : "right-0",
            )}
          >
            <m.div
              className="w-max rounded-xl border border-border bg-popover p-2 shadow-2xl"
              style={{
                transformOrigin: onCover ? "bottom center" : "bottom right",
              }}
              initial={presets.panel.initial}
              animate={presets.panel.animate}
            >
              {panel}
            </m.div>
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
