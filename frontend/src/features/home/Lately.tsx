import { Link } from "react-router-dom";

import type { HomeLatelyRow } from "@/api/home";
import { Cover } from "@/components/Cover";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

import { localDate } from "./year";

/**
 * A row's day where the person is. A finish is a bare day and is that day; an addition
 * or a change of score is a moment in UTC, so an evening import west of Greenwich
 * reads as the evening's day (Sprint 132). Formatted per call, in the zone of now.
 */
function day(at: string): string {
  const moment = at.length > 10 ? new Date(at) : localDate(at.slice(0, 10));
  const shown = Number.isNaN(moment.getTime())
    ? localDate(at.slice(0, 10))
    : moment;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
  }).format(shown);
}

/** What a row says under its cover: what happened, in a word or a figure. */
function what(row: HomeLatelyRow): string {
  if (row.kind === "finished") return "Finished";
  if (row.kind === "added")
    return row.count > 1 ? `Added +${row.count - 1}` : "Added";
  if (row.score !== null && row.previous === row.score) return "Still";
  return `${row.previous ?? "–"} → ${row.score ?? "–"}`;
}

/** The same for a screen reader, in words. */
function said(row: HomeLatelyRow): string {
  if (row.kind === "added" && row.count > 1)
    return `Added with ${row.count - 1} more`;
  if (row.kind === "score" && row.previous !== row.score)
    return `Score changed from ${row.previous ?? "none"} to ${row.score ?? "none"}`;
  return what(row);
}

/**
 * The Library's second band (Sprint 141, DEC-193): what was finished, rescored and
 * added, newest first, as one row of covers that scrolls sideways when it is longer
 * than the screen. It was a list of sentences on Home (Sprint 131); the Library is a
 * place of covers, and a day's additions are still one cover.
 */
export function Lately({ rows }: { rows: HomeLatelyRow[] }) {
  if (rows.length === 0) return null;
  return (
    <section aria-labelledby="lately-heading">
      <div className="mb-3 flex items-baseline gap-3">
        <h2 id="lately-heading" className="font-display text-xl font-medium">
          Lately
        </h2>
        <p className="text-xs text-muted-foreground">
          finished and added, newest first
        </p>
      </div>
      <ul className="-mx-1 flex gap-4 overflow-x-auto px-1 pb-2">
        {rows.map((row) => (
          <li
            key={`${row.kind}-${row.entry.id}-${row.at}`}
            className="w-24 shrink-0 sm:w-28"
          >
            <Link
              to={`/books/${row.entry.id}`}
              aria-label={`${said(row)}: ${row.entry.item.title}, ${day(row.at)}`}
              className="group block rounded-md focus-ring"
            >
              <Cover src={row.entry.item.cover_url} size="m" />
              <span className="mt-2 block truncate text-sm font-medium">
                {row.entry.item.title}
              </span>
              <span className="mt-0.5 flex items-center justify-between gap-1 text-xs text-muted-foreground">
                <span className="truncate tabular-nums">{what(row)}</span>
                {row.kind !== "added" && row.score !== null ? (
                  <span
                    className={cn(scoreChipShape, scoreChipClass(row.score))}
                  >
                    {row.score}
                  </span>
                ) : (
                  <span className="shrink-0 tabular-nums">{day(row.at)}</span>
                )}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
