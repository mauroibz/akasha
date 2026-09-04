import { useId, useState } from "react";

import type { InsightRow } from "@/api/library";
import { InsightsMembers } from "@/features/library/InsightsMembers";
import { magnitude } from "@/features/library/insights";
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
  type,
  insightKey,
  hrefFor,
}: {
  rows: InsightRow[];
  /**
   * Rows the current order cannot place — too few of their entries are rated for a
   * mean to mean anything. Drawn below a divider that says how many, which is what
   * the `min_rated` threshold does, shown rather than configured. Sprint 065 asked
   * the server to omit them, so a group with one rating left the screen silently.
   */
  unplaced?: InsightRow[];
  /** Both identify the entries behind a row, for opening it in place. */
  type: string;
  insightKey: string;
  /** Where "open all of these in the library" goes. */
  hrefFor: (row: InsightRow) => string;
}) {
  // One row open at a time: a card is six rows tall and two panels turn it into
  // a scroll. Opening another closes the first, which is also how a reader
  // compares two of them.
  const [open, setOpen] = useState<string | null>(null);
  const panelId = useId();
  // Both groups share one scale, so a bar means the same thing on either side of
  // the divider.
  const max = Math.max(...[...rows, ...unplaced].map((row) => row.count), 1);

  // Indexed, not keyed: a panel id has to be a valid IDREF and a grouping value
  // is arbitrary text — "julio cortázar" has a space in it, which makes
  // `aria-controls` point at nothing. Caught by the axe gate, not by review.
  const draw = (row: InsightRow, index: number) => {
    const share = magnitude(row.count, max);
    const expanded = open === row.key;
    const panel = `${panelId}-${index}`;
    return (
      <li key={row.key}>
        <button
          type="button"
          aria-label={rowLabel(row)}
          aria-expanded={expanded}
          aria-controls={panel}
          className="group relative flex min-h-11 w-full items-center gap-3 overflow-hidden rounded-md px-3 py-2 text-left focus-ring"
          onClick={() => setOpen(expanded ? null : row.key)}
        >
          <span
            aria-hidden="true"
            data-magnitude={String(share)}
            style={{ width: `${Number((share * 100).toFixed(1))}%` }}
            className={cn(
              "absolute inset-y-0 left-0 rounded-md transition-colors group-hover:bg-primary/25",
              expanded ? "bg-primary/30" : "bg-primary/15",
            )}
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
        {expanded && (
          <InsightsMembers
            id={panel}
            type={type}
            insightKey={insightKey}
            value={row.key}
            count={row.count}
            href={hrefFor(row)}
          />
        )}
      </li>
    );
  };

  return (
    <ul className="flex flex-col gap-0.5">
      {rows.map((row, index) => draw(row, index))}
      {unplaced.length > 0 && (
        <li
          aria-hidden="true"
          className="flex items-center gap-3 px-3 pb-1 pt-3 text-xs text-muted-foreground"
        >
          {unplaced.length} not rated enough to place
          <span className="h-px flex-1 bg-border" />
        </li>
      )}
      {unplaced.map((row, index) => draw(row, rows.length + index))}
    </ul>
  );
}
