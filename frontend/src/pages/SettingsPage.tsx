import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import {
  readThemeChoice,
  saveThemeChoice,
  type ThemeChoice,
} from "@/lib/theme";
import { cn } from "@/lib/utils";

interface Option {
  value: ThemeChoice;
  label: string;
  hint: string;
  /** The two halves of the swatch: page and card colours, as the theme draws them. */
  halves: [Swatch, Swatch];
}

interface Swatch {
  page: string;
  card: string;
  text: string;
}

const INK: Swatch = { page: "#0D0C0A", card: "#2C2820", text: "#F3EFE6" };
const PAPER: Swatch = { page: "#F4F0E6", card: "#D8CDB6", text: "#1C1917" };

const OPTIONS: Option[] = [
  {
    value: "system",
    label: "Match my device",
    hint: "Paper by day, Ink at night",
    halves: [PAPER, INK],
  },
  {
    value: "paper",
    label: "Paper",
    hint: "Warm, like a page",
    halves: [PAPER, PAPER],
  },
  { value: "ink", label: "Ink", hint: "Dark, and warm", halves: [INK, INK] },
];

/**
 * Settings (Sprint 090). Appearance is its first section; export moves here when the
 * import screen is redrawn (proposal §5).
 */
export function SettingsPage() {
  const [choice, setChoice] = useState<ThemeChoice>(readThemeChoice);

  const choose = (value: ThemeChoice) => {
    setChoice(value);
    saveThemeChoice(value);
  };

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader eyebrow="Settings" title="Appearance" />
      <fieldset className="mt-8">
        <legend className="mb-4 font-semibold">Theme</legend>
        <div className="grid gap-4 sm:grid-cols-3">
          {OPTIONS.map((option) => (
            <label
              key={option.value}
              className={cn(
                "flex cursor-pointer flex-col gap-3 rounded-xl border bg-surface-raised p-3 transition-colors focus-within:ring-2 focus-within:ring-primary",
                choice === option.value
                  ? "border-primary"
                  : "border-border hover:border-muted-foreground",
              )}
            >
              <span
                aria-hidden="true"
                className="flex h-32 overflow-hidden rounded-lg border border-border"
              >
                {option.halves.map((half, index) => (
                  <span
                    key={index}
                    className="flex flex-1 flex-col gap-2 p-3"
                    style={{ background: half.page, color: half.text }}
                  >
                    <span className="font-display text-xl">Aa</span>
                    <span className="flex gap-1.5">
                      <span
                        className="h-10 w-7 rounded-sm"
                        style={{ background: half.card }}
                      />
                      <span
                        className="h-10 w-7 rounded-sm"
                        style={{ background: half.card }}
                      />
                    </span>
                  </span>
                ))}
              </span>
              <span className="flex items-center gap-3">
                <input
                  type="radio"
                  name="theme"
                  value={option.value}
                  checked={choice === option.value}
                  onChange={() => choose(option.value)}
                  className="h-4 w-4 accent-primary"
                />
                <span>
                  <span className="block font-medium">{option.label}</span>
                  <span className="block text-sm text-muted-foreground">
                    {option.hint}
                  </span>
                </span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <p className="mt-6 text-sm text-muted-foreground">
        Kept in this browser, so a phone and a laptop can differ. Covers, scores
        and the amber dot look the same in both.
      </p>
    </main>
  );
}
