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

/**
 * How far a ranking's leader stands above the middle of its own ranking.
 *
 * This is the whole of "which insights are worth showing" (DEC-132). Sprint 065
 * offered keys in `__init__.py` order and opened every domain on whichever one its
 * field list happened to declare first, which is not a judgement about the library
 * at all.
 *
 * Only values held more than once count toward it: a long tail of ones is what
 * every key in a personal library has, and it says nothing about that key. A key
 * with fewer than three such values is not a ranking — it is a fact, and a fact is
 * better stated in a line than drawn as a card.
 *
 * Deliberately one paragraph of arithmetic over data already loaded. It is a
 * judgement that will be argued with, so changing one's mind about it has to stay
 * a small diff and a test — the same reasoning that made `groupable` a declaration
 * rather than a derivation.
 */
export function keyLead(rows: InsightRow[]): number {
  const deep = rows
    .filter((row) => row.count >= 2)
    .map((row) => row.count)
    .sort((a, b) => b - a);
  if (deep.length < 3) return 0;
  const middle = deep[Math.floor(deep.length / 2)];
  return deep[0] / Math.max(middle, 1);
}

/**
 * The keys worth a card, best first, and the ones that are not.
 *
 * Ties keep the order the domain declared, so its own sense of which of two
 * equally interesting keys comes first is not thrown away for nothing.
 */
export function orderKeys<T>(
  rankings: T[],
  rowsOf: (ranking: T) => InsightRow[],
): { carded: T[]; quiet: T[] } {
  const scored = rankings.map((ranking) => ({
    lead: keyLead(rowsOf(ranking)),
    ranking,
  }));
  return {
    carded: scored
      .filter((entry) => entry.lead > 0)
      .sort((a, b) => b.lead - a.lead)
      .map((entry) => entry.ranking),
    quiet: scored
      .filter((entry) => entry.lead === 0)
      .map((entry) => entry.ranking),
  };
}

/**
 * The whole truth about a key that did not earn a card, in one clause.
 *
 * Not hidden, and not padded out into a two-row table: "Spanish 31, English 16" is
 * everything that key has to say, and it fits in less space than the card would
 * have taken.
 */
export function quietSummary(rows: InsightRow[]): string {
  if (rows.length === 0) return "nothing recorded yet";
  if (rows.every((row) => row.count === 1))
    return `${rows.length} ${rows.length === 1 ? "value" : "values"}, each appearing once`;
  return rows
    .slice(0, 3)
    .map((row) => `${row.label} ${row.count}`)
    .join(", ");
}
