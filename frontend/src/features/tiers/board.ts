/**
 * The tier board's state (Sprint 117, DEC-176): one row per score, ten to one, the
 * entries in each row in their rank order. Moving inside a row reorders it, which
 * is saved at once (a rank never changes a score). Moving to another row is a
 * proposal, applied only when the owner confirms. Pure, so the page only draws it.
 */

export type Board = Record<number, number[]>;

export interface Placed {
  id: number;
  score: number | null;
  score_rank?: number | null;
}

export const SCORES = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1] as const;

export function boardFrom(entries: readonly Placed[]): Board {
  const board: Board = {};
  for (const score of SCORES) board[score] = [];
  const ordered = [...entries].sort(
    (a, b) =>
      (a.score_rank ?? Number.MAX_SAFE_INTEGER) -
      (b.score_rank ?? Number.MAX_SAFE_INTEGER),
  );
  for (const entry of ordered)
    if (entry.score !== null && board[entry.score])
      board[entry.score].push(entry.id);
  return board;
}

export function rowOf(board: Board, id: number): number | null {
  for (const score of SCORES) if (board[score].includes(id)) return score;
  return null;
}

/** Move `id` to `score`, at `index` in that row (clamped), out of wherever it was. */
export function moveTo(
  board: Board,
  id: number,
  score: number,
  index: number,
): Board {
  const next: Board = {};
  for (const row of SCORES)
    next[row] = board[row].filter((other) => other !== id);
  const row = next[score];
  const at = Math.max(0, Math.min(index, row.length));
  next[score] = [...row.slice(0, at), id, ...row.slice(at)];
  return next;
}

/** Every entry the board shows in a row other than its score: what *Apply* writes. */
export function proposals(
  board: Board,
  entries: readonly Placed[],
): Array<{ id: number; from: number; to: number }> {
  const out: Array<{ id: number; from: number; to: number }> = [];
  for (const entry of entries) {
    const to = rowOf(board, entry.id);
    if (entry.score !== null && to !== null && to !== entry.score)
      out.push({ id: entry.id, from: entry.score, to });
  }
  return out;
}

/**
 * The rows whose order changed and can be saved now: none of their entries is a
 * proposal, since a rank is saved among entries that already share the score.
 */
export function rowsToRank(
  board: Board,
  before: Board,
  entries: readonly Placed[],
): number[][] {
  const moving = new Set(proposals(board, entries).map((row) => row.id));
  const rows: number[][] = [];
  for (const score of SCORES) {
    const row = board[score];
    if (row.length === 0 || row.some((id) => moving.has(id))) continue;
    const was = before[score];
    if (
      row.length === was.length &&
      row.every((id, index) => was[index] === id)
    )
      continue;
    rows.push(row);
  }
  return rows;
}
