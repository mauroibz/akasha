import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";

import { queryKeys } from "@/api/keys";
import { getScoreHistory, type ScoreEvent } from "@/api/library";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * How a score changed over time (Sprint 115, DEC-176): the scores with their years in
 * one line, and under it, opened, each change with why. Drawn only when there has been
 * more than one score, so a first opinion is not dressed up as a history.
 */
export function ScoreHistoryRow({
  entryId,
  icon,
}: {
  entryId: number;
  icon: React.ReactNode;
}) {
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const history = useQuery({
    queryKey: queryKeys.scoreHistory(entryId),
    queryFn: ({ signal }) => getScoreHistory(entryId, signal),
  });
  const events = (Array.isArray(history.data) ? history.data : []).filter(
    (event) => event.score !== null,
  );
  if (events.length < 2) return null;
  return (
    <div
      data-fact="score-history"
      className="group -mx-2 grid grid-cols-[9.5rem_1fr] items-center gap-x-3 rounded-md px-2 py-1.5 sm:grid-cols-[11rem_1fr]"
    >
      <dt className="flex items-center gap-2 text-sm text-muted-foreground [&_svg]:h-4 [&_svg]:w-4 [&_svg]:shrink-0">
        {icon}
        Over time
      </dt>
      <dd className="flex min-w-0 items-center justify-between gap-2">
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          {events.map((event, index) => (
            <span key={index} className="flex items-center gap-1.5">
              {index > 0 && (
                <span aria-hidden="true" className="text-muted-foreground">
                  →
                </span>
              )}
              <span className="sr-only">
                {event.score} in {year(event)}
              </span>
              <span aria-hidden="true" className="flex items-center gap-1">
                <span
                  className={cn(scoreChipShape, scoreChipClass(event.score))}
                >
                  {event.score}
                </span>
                <span className="tabular-nums text-muted-foreground">
                  {year(event)}
                </span>
              </span>
            </span>
          ))}
        </span>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
          className="ml-auto flex shrink-0 items-center gap-1 rounded px-1.5 text-xs text-muted-foreground focus-ring hover:text-foreground"
        >
          {open ? "Hide" : "Why"}
          <ChevronDown
            aria-hidden="true"
            className={cn("size-4 transition-transform", open && "rotate-180")}
          />
        </button>
      </dd>
      {open && (
        <dd id={panelId} className="col-span-2 pb-2 pt-2">
          <ol className="space-y-1.5 text-sm">
            {events.map((event, index) => (
              <li key={index} className="flex flex-wrap gap-x-2">
                <span className="tabular-nums text-muted-foreground">
                  {event.recorded_at.slice(0, 10)}
                </span>
                <span>
                  {event.previous === null || event.previous === undefined
                    ? `First scored ${event.score}`
                    : event.previous === event.score
                      ? `Still ${event.score}`
                      : `${event.previous} → ${event.score}`}
                </span>
                {event.reason && (
                  <span className="text-muted-foreground">
                    {event.reason === "reread" ? "after a reread" : "with time"}
                  </span>
                )}
                {event.note && (
                  <span className="font-display italic">“{event.note}”</span>
                )}
              </li>
            ))}
          </ol>
        </dd>
      )}
    </div>
  );
}

function year(event: ScoreEvent): string {
  return event.recorded_at.slice(0, 4);
}
