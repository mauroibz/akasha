/**
 * A rank inside a score, built by choosing between two (Sprint 116, DEC-176).
 *
 * Binary insertion: each unplaced entry is asked about against the middle of what is
 * already in order, and the half it belongs in is halved again, so it settles in about
 * log2(n) choices. *About the same* places it right after the one it was compared
 * with; *Skip* sets it aside without a place. Pure, so the page only draws the state.
 */

export type Choice = "candidate" | "against" | "same" | "skip";

export interface Ranking {
  /** In order, best first. */
  ranked: number[];
  /** Still to place, in the order they will be asked about. */
  waiting: number[];
  skipped: number[];
  /** The open search range in `ranked` for `waiting[0]`. */
  low: number;
  high: number;
  question: { candidate: number; against: number } | null;
}

function ask(state: Omit<Ranking, "question">): Ranking {
  let { ranked, waiting } = state;
  let { low, high } = state;
  // An entry alone, or a range closed to one place, needs no question.
  while (waiting.length > 0 && low >= high) {
    ranked = [...ranked.slice(0, low), waiting[0], ...ranked.slice(low)];
    waiting = waiting.slice(1);
    low = 0;
    high = ranked.length;
  }
  if (waiting.length === 0)
    return { ...state, ranked, waiting, low, high, question: null };
  const middle = Math.floor((low + high) / 2);
  return {
    ...state,
    ranked,
    waiting,
    low,
    high,
    question: { candidate: waiting[0], against: ranked[middle] },
  };
}

export function start(ranked: number[], unplaced: number[]): Ranking {
  return ask({
    ranked,
    waiting: unplaced,
    skipped: [],
    low: 0,
    high: ranked.length,
  });
}

export function answer(state: Ranking, choice: Choice): Ranking {
  if (!state.question) return state;
  const middle = Math.floor((state.low + state.high) / 2);
  if (choice === "skip")
    return ask({
      ...state,
      waiting: state.waiting.slice(1),
      skipped: [...state.skipped, state.waiting[0]],
      low: 0,
      high: state.ranked.length,
    });
  if (choice === "same")
    return ask({ ...state, low: middle + 1, high: middle + 1 });
  // The candidate liked more goes above the middle; less, below it.
  return choice === "candidate"
    ? ask({ ...state, high: middle })
    : ask({ ...state, low: middle + 1 });
}
