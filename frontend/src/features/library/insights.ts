import type { InsightRow } from "@/api/library";

/**
 * The two orders a ranking can be read in (Sprint 066).
 *
 * Sprint 065 shipped these as *metrics*: `count` and `score` were different
 * requests returning different columns, so choosing one threw the other away —
 * `rated_count` and `mean_score` arrive on every row under both and were rendered
 * under neither. They are one dataset in two orders, and both are drawn on every
 * row regardless of which one it is sorted by.
 */
export type InsightSort = "count" | "score";

export interface OrderedRanking {
  /** The rows the chosen order can place, in it. */
  placed: InsightRow[];
  /**
   * Rows the score order cannot place because too few of their entries are rated.
   * Never dropped: the shipped screen asked the server to omit them, so a group
   * with one rating vanished from the screen with nothing said about it.
   */
  unplaced: InsightRow[];
}

/** Ties break on the normalized key, which is the order the server itself used. */
const byKey = (a: InsightRow, b: InsightRow) => a.key.localeCompare(b.key);

export function orderRows(
  rows: InsightRow[],
  sort: InsightSort,
  minRated: number,
): OrderedRanking {
  const byCount = (a: InsightRow, b: InsightRow) =>
    b.count - a.count || byKey(a, b);

  if (sort === "count") {
    return { placed: [...rows].sort(byCount), unplaced: [] };
  }

  const placeable = (row: InsightRow) =>
    row.mean_score !== null && row.rated_count >= minRated;

  return {
    placed: rows.filter(placeable).sort(
      (a, b) =>
        // `placeable` guarantees both means; the fallbacks are for the compiler.
        (b.mean_score ?? 0) - (a.mean_score ?? 0) || byCount(a, b),
    ),
    unplaced: rows.filter((row) => !placeable(row)).sort(byCount),
  };
}
