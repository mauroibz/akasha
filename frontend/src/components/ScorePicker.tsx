import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

interface ScorePickerProps {
  value: number | null;
  provisional?: boolean;
  onChange: (score: number | null) => void;
  label?: string;
  compact?: boolean;
}

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
        "min-h-11 rounded-lg border px-3 text-center focus-ring",
        provisional
          ? "border-amber-400/60 text-amber-200"
          : "border-zinc-700 text-zinc-200",
        value === null && "text-zinc-500",
        compact && "h-9 min-h-0 shrink-0 px-2 text-sm",
      )}
      aria-expanded={editing}
      aria-label={`${label}: ${value ?? "unscored"}`}
      onClick={() => setEditing((open) => !open)}
    >
      {value ?? "—"}
      {provisional && (
        <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-amber-400" />
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
              "w-8 rounded text-sm font-medium transition-colors focus-ring",
              compact ? "h-9" : "h-11",
              n === value
                ? "bg-fuchsia-500 text-zinc-950"
                : value !== null && n <= value
                  ? "bg-fuchsia-500/30 text-fuchsia-200"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700",
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
        className="self-start rounded text-xs text-zinc-500 hover:text-zinc-300 focus-ring"
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
          <div className="absolute bottom-full right-0 z-20 mb-2 w-max rounded-xl border border-zinc-700 bg-zinc-950 p-2 shadow-2xl">
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
