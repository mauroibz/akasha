import type { ReactNode } from "react";

import type { LibraryEntry } from "@/api/library";

/** A score worth putting in order: the most common one two or more entries share. */
export function bestScore(counts: number[]): number | null {
  let best: number | null = null;
  counts.forEach((count, index) => {
    if (count >= 2 && (best === null || count >= counts[best - 1]))
      best = index + 1;
  });
  return best;
}

/** One game in Play (Sprint 125): a question, its covers, where it goes. */
export interface Game {
  key: string;
  to: string;
  question: ReactNode;
  /** The question as plain words, for the link's name. */
  label: string;
  meta: string;
  covers: LibraryEntry[];
}
