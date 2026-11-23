import { useState } from "react";

import {
  readThemeChoice,
  saveThemeChoice,
  THEMES,
  type ThemeChoice,
} from "@/lib/theme";
import { cn } from "@/lib/utils";

const paper = THEMES[0];
const ink = THEMES[1];

/**
 * The theme, as swatches (Sprint 148, DEC-193): *Match my device*, *Paper*, *Ink*
 * and the four presets. Each swatch is the theme's own page, card and accent, so
 * the choice is seen before it is made; choosing applies at once and is kept in
 * this browser. In Settings, and beside *Your media* while arranging the Library.
 */
export function ThemePicker({
  className,
  compact = false,
}: {
  className?: string;
  /** Without the hints: while arranging, where it is one control among several. */
  compact?: boolean;
}) {
  const [choice, setChoice] = useState<ThemeChoice>(readThemeChoice);
  const choose = (value: ThemeChoice) => {
    setChoice(value);
    saveThemeChoice(value);
  };
  const options: Array<{
    value: ThemeChoice;
    label: string;
    hint: string;
    halves: [(typeof THEMES)[number], (typeof THEMES)[number]];
  }> = [
    {
      value: "system",
      label: "Match my device",
      hint: "Paper by day, Ink at night",
      halves: [paper, ink],
    },
    ...THEMES.map((theme) => ({
      value: theme.id,
      label: theme.label,
      hint: theme.hint,
      halves: [theme, theme] as [typeof theme, typeof theme],
    })),
  ];
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className={cn(
        "grid gap-3",
        compact
          ? "grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))]"
          : "sm:grid-cols-2 lg:grid-cols-3",
        className,
      )}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={choice === option.value}
          onClick={() => choose(option.value)}
          className={cn(
            "flex min-h-11 items-center gap-3 rounded-xl border p-2.5 text-left transition-colors focus-ring",
            choice === option.value
              ? "border-primary bg-primary/10"
              : "border-border bg-surface hover:bg-accent",
          )}
        >
          {/* The swatch: the theme's page with a card and its accent on it. The
              colours are the themes' own, so they do not follow the theme on screen. */}
          <span
            aria-hidden="true"
            className="flex h-11 w-16 shrink-0 overflow-hidden rounded-md border border-border"
          >
            {option.halves.map((half, index) => (
              <span
                key={index}
                className="flex flex-1 items-end gap-1 p-1"
                style={{ background: half.page }}
              >
                <span
                  className="h-4 flex-1 rounded-sm"
                  style={{ background: half.card }}
                />
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: half.accent }}
                />
              </span>
            ))}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-medium">{option.label}</span>
            {!compact && (
              <span className="block truncate text-sm text-muted-foreground">
                {option.hint}
              </span>
            )}
          </span>
        </button>
      ))}
    </div>
  );
}
