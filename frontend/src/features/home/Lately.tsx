import { ArrowDownUp, Check, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import type { HomeLatelyRow, ModuleSize } from "@/api/home";
import { scoreArticle } from "@/features/rescore/rescore";
import { scoreChipClass } from "@/lib/score";
import { cn } from "@/lib/utils";

import { HomeModule } from "./HomeModule";
import { localDate } from "./year";

const ROWS: Record<ModuleSize, number> = { S: 4, M: 8, L: 10 };

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

const icons = {
  finished: Check,
  score: ArrowDownUp,
  added: Plus,
} as const;

/**
 * What happened lately (Sprint 131): finishes and score changes from the Diary's
 * timeline, and what was added, a day's additions as one row. Newest first; the
 * size says how many rows.
 */
export function Lately({
  rows,
  size,
  className,
}: {
  rows: HomeLatelyRow[];
  size: ModuleSize;
  className?: string;
}) {
  return (
    <HomeModule
      title="Lately"
      className={className}
      aside={
        <Link
          to="/diary"
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          Diary →
        </Link>
      }
    >
      <ul className="space-y-1">
        {rows.slice(0, ROWS[size]).map((row) => {
          const Icon = icons[row.kind];
          const title = (
            <Link
              to={`/books/${row.entry.id}`}
              className="font-medium text-foreground underline-offset-4 hover:underline focus-ring"
            >
              {row.entry.item.title}
            </Link>
          );
          return (
            <li
              key={`${row.kind}-${row.entry.id}-${row.at}`}
              className="flex min-h-9 items-center gap-2.5 text-sm"
            >
              <span
                aria-hidden="true"
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border text-muted-foreground [&_svg]:h-3 [&_svg]:w-3"
              >
                <Icon />
              </span>
              <span className="min-w-0 flex-1 truncate text-muted-foreground">
                {row.kind === "finished" ? (
                  <>Finished {title}</>
                ) : row.kind === "score" ? (
                  <>
                    {title}{" "}
                    {row.score !== null && row.previous === row.score ? (
                      // A score looked at again and kept (One question, the
                      // revisit deck): not a change to itself.
                      <>still {scoreArticle(row.score)}</>
                    ) : (
                      <span className="tabular-nums">
                        {row.previous ?? "–"} → {row.score ?? "–"}
                      </span>
                    )}
                  </>
                ) : (
                  <>
                    Added {title}
                    {row.count > 1 ? ` and ${row.count - 1} more` : ""}
                  </>
                )}
              </span>
              {row.kind === "finished" && row.score !== null ? (
                <span
                  className={cn(
                    "rounded px-1.5 text-xs font-semibold tabular-nums",
                    scoreChipClass(row.score),
                  )}
                >
                  {row.score}
                </span>
              ) : null}
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {day(row.at)}
              </span>
            </li>
          );
        })}
      </ul>
    </HomeModule>
  );
}
