import { useInfiniteQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { getTimeline, type ItemType, type TimelineEvent } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Loading } from "@/components/ui/skeleton";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";
import { navigateWithTransition } from "@/lib/viewTransition";

const MONTH = new Intl.DateTimeFormat(undefined, { month: "long" });

function monthOf(at: string): string {
  const [year, month] = at.slice(0, 7).split("-").map(Number);
  return MONTH.format(new Date(year, (month || 1) - 1, 1));
}

/** Events grouped by year, then month, keeping their order. */
function grouped(events: TimelineEvent[]) {
  const years: Array<{
    year: string;
    months: Array<{ month: string; events: TimelineEvent[] }>;
  }> = [];
  for (const event of events) {
    const year = event.at.slice(0, 4);
    const month = event.at.slice(0, 7);
    let bucket = years.at(-1);
    if (!bucket || bucket.year !== year) {
      bucket = { year, months: [] };
      years.push(bucket);
    }
    let row = bucket.months.at(-1);
    if (!row || row.month !== month) {
      row = { month, events: [] };
      bucket.months.push(row);
    }
    row.events.push(event);
  }
  return years;
}

/**
 * The Diary across every year (Sprint 118, DEC-176): what was finished and how scores
 * changed, in one line of time across every library, so the film after the book shows
 * by itself. Newest first, loaded a page at a time.
 */
export function Timeline({ types }: { types: ItemType[] }) {
  const navigate = useNavigate();
  const timeline = useInfiniteQuery({
    queryKey: ["diary", "timeline"],
    queryFn: ({ pageParam, signal }) => getTimeline(pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const domainOf = (id: string) =>
    types.find((type) => type.id === id)?.label ?? id;

  if (timeline.isPending)
    return <Loading label="Loading every year…" className="mt-8" />;
  if (timeline.isError)
    return (
      <p role="alert" className="mt-8 text-destructive">
        The timeline could not be loaded.
      </p>
    );
  const events = timeline.data.pages.flatMap((page) => page.events);
  if (events.length === 0)
    return (
      <EmptyState title="Nothing in the timeline yet" className="mt-8">
        Finishes and changed scores appear here as they happen.
      </EmptyState>
    );

  return (
    <div className="mt-8">
      <ol aria-label="Every year" className="space-y-10">
        {grouped(events).map((year) => (
          <li key={year.year}>
            <h2 className="font-display text-4xl font-medium tracking-tight">
              {year.year}
            </h2>
            <ol className="mt-4 space-y-6 border-l border-border pl-5">
              {year.months.map((month) => (
                <li key={month.month}>
                  <h3 className="-ml-[1.65rem] flex items-center gap-3 text-sm font-medium text-muted-foreground">
                    <span
                      aria-hidden="true"
                      className="h-2.5 w-2.5 rounded-full bg-primary"
                    />
                    {monthOf(month.month)}
                  </h3>
                  <ul className="mt-3 space-y-3">
                    {month.events.map((event, index) => (
                      <li
                        key={`${event.kind}-${event.entry.id}-${event.at}-${index}`}
                        data-event={event.kind}
                        className="flex items-start gap-3"
                      >
                        <button
                          type="button"
                          aria-label={`Open ${event.entry.item.title}`}
                          onClick={() =>
                            navigateWithTransition(
                              navigate,
                              `/books/${event.entry.id}`,
                            )
                          }
                          className="w-10 shrink-0 rounded focus-ring"
                        >
                          <CoverImage
                            src={event.entry.item.cover_url ?? null}
                            alt=""
                            className="aspect-[2/3] w-10 rounded object-cover"
                          />
                        </button>
                        <div className="min-w-0 flex-1 text-sm">
                          <p className="flex flex-wrap items-baseline gap-x-2">
                            <span className="font-medium">
                              {event.entry.item.title}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {domainOf(event.entry.item.type)}
                            </span>
                          </p>
                          {event.kind === "finished" ? (
                            <p className="mt-0.5 flex items-center gap-2 text-muted-foreground">
                              Finished
                              {event.score !== null && (
                                <span
                                  className={cn(
                                    scoreChipShape,
                                    scoreChipClass(event.score),
                                  )}
                                >
                                  {event.score}
                                </span>
                              )}
                            </p>
                          ) : (
                            <p className="mt-0.5 text-muted-foreground">
                              <span className="text-foreground">
                                {event.previous === event.score
                                  ? `Still ${event.score}`
                                  : `${event.previous} → ${event.score ?? "no score"}`}
                              </span>
                              {event.reason &&
                                ` · ${event.reason === "reread" ? "after a reread" : "with time"}`}
                              {event.note && (
                                <span className="mt-0.5 block font-display italic text-foreground">
                                  “{event.note}”
                                </span>
                              )}
                            </p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </li>
        ))}
      </ol>
      {timeline.hasNextPage && (
        <Button
          variant="secondary"
          className="mt-8 rounded-full px-5"
          disabled={timeline.isFetchingNextPage}
          onClick={() => void timeline.fetchNextPage()}
        >
          {timeline.isFetchingNextPage ? "Loading…" : "Earlier"}
        </Button>
      )}
    </div>
  );
}
