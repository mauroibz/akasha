/**
 * The DEC-026 score ramp: red-400 for 1-3, amber-400 for 4-6, lime-400 for 7-8,
 * emerald-400 for 9-10.
 *
 * It applies everywhere a score is shown — the picker segments and the score
 * text on library and triage rows — so that the colour means the same thing
 * wherever the eye lands. Class names are spelled out rather than composed at
 * runtime because Tailwind only emits classes it can find as literals.
 */
export type ScoreBand = "low" | "mid" | "high" | "top";

export function scoreBand(score: number): ScoreBand {
  if (score <= 3) return "low";
  if (score <= 6) return "mid";
  if (score <= 8) return "high";
  return "top";
}

/** Score text, for list rows and the collapsed picker trigger. */
export const scoreTextClass: Record<ScoreBand, string> = {
  low: "text-score-low",
  mid: "text-score-mid",
  high: "text-score-high",
  top: "text-score-top",
};

/** The selected segment of the picker. */
export const scoreFillClass: Record<ScoreBand, string> = {
  low: "bg-score-low text-background",
  mid: "bg-score-mid text-background",
  high: "bg-score-high text-background",
  top: "bg-score-top text-background",
};

/** Segments below the selected one. */
export const scoreTrailClass: Record<ScoreBand, string> = {
  low: "bg-score-low/25 text-score-low",
  mid: "bg-score-mid/25 text-score-mid",
  high: "bg-score-high/25 text-score-high",
  top: "bg-score-top/25 text-score-top",
};
