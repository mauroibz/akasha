import type { InsightRow } from "@/api/library";
import { meanScoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * One ranking, drawn as rows rather than as a table (Sprint 066).
 *
 * The row *is* the bar: it is filled to its share of its own ranking's leader, so
 * proportion is seen instead of computed. The shipped table drew `7` and `3` at
 * identical weight, and a ranking whose whole job is ordering cannot afford that.
 *
 * This is also the only honest use of the accent on this screen. Before, every row
 * label was `text-primary` — twelve identical amber links, so amber distinguished
 * nothing. The labels are `foreground` ink here and the accent encodes a quantity.
 *
 * Both numbers are on every row under either order (DEC-132): the bar carries how
 * many, the chip carries how good, and a short bar under an emerald chip is the
 * reading the shipped screen could not produce at all.
 */

/** A row's share of the leader, rounded once and used for both the bar and its label. */
export function magnitude(count: number, max: number): number {
  // Three decimals is far beyond what a bar can show, and is a stable number to
  // assert against — the alternative is a test that measures rendered pixels.
  return Number((count / Math.max(max, 1)).toFixed(3));
}

/** What a screen reader is told a row holds, since the visible cells are terse. */
function rowLabel(row: InsightRow): string {
  const held = `${row.count} ${row.count === 1 ? "entry" : "entries"}`;
  if (row.mean_score === null) return `${row.label}: ${held}, none rated`;
  return `${row.label}: ${held}, mean score ${row.mean_score.toFixed(1)} from ${
    row.rated_count
  } rated`;
}

export function InsightsRanking({
  rows,
  unplaced = [],
  onOpen,
}: {
  rows: InsightRow[];
  /**
   * Rows the current order cannot place — too few of their entries are rated for a
   * mean to mean anything. Drawn below a divider that says how many, which is what
   * the `min_rated` threshold does, shown rather than configured. Sprint 065 asked
   * the server to omit them, so a group with one rating left the screen silently.
   */
  unplaced?: InsightRow[];
  onOpen: (row: InsightRow) => void;
}) {
  // Both groups share one scale, so a bar means the same thing on either side of
  // the divider.
  const max = Math.max(...[...rows, ...unplaced].map((row) => row.count), 1);

  const draw = (row: InsightRow) => {
    const share = magnitude(row.count, max);
    return (
      <li key={row.key}>
        <button
          type="button"
          aria-label={rowLabel(row)}
          className="group relative flex min-h-11 w-full items-center gap-3 overflow-hidden rounded-md px-3 py-2 text-left focus-ring"
          onClick={() => onOpen(row)}
        >
          <span
            aria-hidden="true"
            data-magnitude={String(share)}
            style={{ width: `${Number((share * 100).toFixed(1))}%` }}
            className="absolute inset-y-0 left-0 rounded-md bg-primary/15 transition-colors group-hover:bg-primary/25"
          />
          <span
            data-row-label=""
            className="relative min-w-0 flex-1 truncate text-sm font-medium"
          >
            {row.label}
          </span>
          <span className="relative shrink-0 text-sm tabular-nums text-muted-foreground">
            {row.count}
          </span>
          <span
            className={cn(
              "relative shrink-0 text-center",
              scoreChipShape,
              meanScoreChipClass(row.mean_score),
            )}
          >
            {row.mean_score !== null ? row.mean_score.toFixed(1) : "—"}
          </span>
        </button>
      </li>
    );
  };

  return (
    <ul className="flex flex-col gap-0.5">
      {rows.map(draw)}
      {unplaced.length > 0 && (
        <li
          aria-hidden="true"
          className="flex items-center gap-3 px-3 pb-1 pt-3 text-xs text-muted-foreground"
        >
          {unplaced.length} not rated enough to place
          <span className="h-px flex-1 bg-border" />
        </li>
      )}
      {unplaced.map(draw)}
    </ul>
  );
}
