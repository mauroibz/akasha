import type { LibraryEntry } from "@/api/library";

/** One card in a round of *Five minutes* (Sprint 126, DEC-179). */
export type FiveCard =
  | { kind: "pair"; pair: [LibraryEntry, LibraryEntry] }
  | { kind: "gap"; entry: LibraryEntry }
  | { kind: "old"; entry: LibraryEntry }
  | { kind: "pile"; entry: LibraryEntry };

/**
 * Two entries of one score to choose between, from that score's order as the library
 * sorts it (placed first, best first): the first one not yet placed against the one
 * above it, so one answer extends the order; when all are placed, the top two.
 */
export function pairFrom(
  ordered: LibraryEntry[],
): [LibraryEntry, LibraryEntry] | null {
  if (ordered.length < 2) return null;
  const unplaced = ordered.findIndex(
    (entry, index) => index > 0 && entry.score_rank == null,
  );
  const at = unplaced > 0 ? unplaced : 1;
  return [ordered[at - 1], ordered[at]];
}

/**
 * The order to write after one answer: the entries already placed and the two just
 * compared, with the answer in it. An entry never asked about stays unplaced, as the
 * rank endpoint leaves whatever it is not sent.
 */
export function orderAfter(
  ordered: LibraryEntry[],
  pair: [LibraryEntry, LibraryEntry],
  winner: LibraryEntry,
): number[] {
  const asked = new Set(pair.map((entry) => entry.id));
  const ids = ordered
    .filter((entry) => entry.score_rank != null || asked.has(entry.id))
    .map((entry) => entry.id);
  const [upper, lower] = pair;
  if (winner.id === lower.id) {
    const i = ids.indexOf(upper.id);
    const j = ids.indexOf(lower.id);
    [ids[i], ids[j]] = [ids[j], ids[i]];
  }
  return ids;
}

/**
 * A round: one pair, then gaps, old scores and the pile in turn, until five cards or
 * nothing is left. Only the kinds that have something to ask take part.
 */
export function mixRound(
  sources: {
    pair: [LibraryEntry, LibraryEntry] | null;
    gaps: LibraryEntry[];
    old: LibraryEntry[];
    pile: LibraryEntry[];
  },
  size = 5,
): FiveCard[] {
  const round: FiveCard[] = sources.pair
    ? [{ kind: "pair", pair: sources.pair }]
    : [];
  const queues: FiveCard[][] = [
    sources.gaps.map((entry) => ({ kind: "gap", entry })),
    sources.old.map((entry) => ({ kind: "old", entry })),
    sources.pile.map((entry) => ({ kind: "pile", entry })),
  ];
  while (round.length < size && queues.some((queue) => queue.length)) {
    for (const queue of queues) {
      const next = queue.shift();
      if (next && round.length < size) round.push(next);
    }
  }
  return round;
}
