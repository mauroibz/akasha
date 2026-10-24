import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getGoals, type Goal } from "@/api/goals";
import { queryKeys } from "@/api/keys";
import { getDiary } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/ui/empty-state";
import { Timeline } from "@/features/diary/Timeline";
import { GoalBand } from "@/features/goals/GoalBand";
import { GoalDialog } from "@/features/goals/GoalDialog";
import { GoalInvite } from "@/features/goals/GoalInvite";
import { goalDomains } from "@/features/goals/goals";
import { Loading } from "@/components/ui/skeleton";
import { countLabel } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { cn } from "@/lib/utils";
import { navigateWithTransition } from "@/lib/viewTransition";

const MONTH = new Intl.DateTimeFormat(undefined, { month: "long" });

function monthName(month: string): string {
  const [year, number] = month.split("-").map(Number);
  return MONTH.format(new Date(year, (number || 1) - 1, 1));
}

/**
 * The Diary (Sprint 098, proposal §7): what you finished, month by month, across every
 * domain: "March: 3 books, 1 movie", with the covers. Read from `date_finished`.
 *
 * A gentle goal leads the page (Sprint 104, DEC-169; Sprint 127, DEC-179): slots the
 * year's covers fill, and a few picks. Without one, an invitation with three paces.
 */
export function DiaryPage() {
  const navigate = useNavigate();
  const [year, setYear] = useState<number | undefined>(undefined);
  // Every year as one timeline (Sprint 118), beside the year-by-year view.
  const [everyYear, setEveryYear] = useState(false);
  const itemTypes = useItemTypes();
  const diary = useQuery({
    queryKey: queryKeys.diary(year),
    queryFn: ({ signal }) => getDiary(year, signal),
  });
  const types = Array.isArray(itemTypes.data) ? itemTypes.data : [];
  const labelFor = (id: string, count: number) => countLabel(count, id, types);
  const shown = diary.data?.year ?? year;
  const years = diary.data?.years ?? [];
  const goals = useQuery({
    queryKey: queryKeys.goals,
    queryFn: ({ signal }) => getGoals(signal),
  });
  const [editing, setEditing] = useState<{ open: boolean; goal?: Goal }>({
    open: false,
  });
  const canSetGoal = goalDomains(types).length > 0;
  const goalYear = shown ?? new Date().getFullYear();
  const thisYear = goalYear === new Date().getFullYear();
  // A domain's finishes in the shown year, for its goal's slots (Sprint 127).
  const finishedOf = (itemType: string) =>
    (diary.data?.months ?? []).flatMap((month) =>
      month.entries.filter((entry) => entry.item.type === itemType),
    );
  // The library a goal is offered for: the one finished most this year.
  const invited = [...goalDomains(types)].sort(
    (a, b) => finishedOf(b.id).length - finishedOf(a.id).length,
  )[0];

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-5 py-8">
      <PageHeader
        title="Diary"
        lede="What you finished, month by month."
        actions={
          years.length > 0 ? (
            <div
              role="group"
              aria-label="Year"
              className="flex flex-wrap gap-1.5"
            >
              <button
                type="button"
                aria-pressed={everyYear}
                onClick={() => setEveryYear(true)}
                className={cn(
                  "rounded-full px-3 py-1.5 text-sm font-medium transition-colors focus-ring",
                  everyYear
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                All years
              </button>
              {years.map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={!everyYear && option === shown}
                  onClick={() => {
                    setEveryYear(false);
                    setYear(option);
                  }}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-sm font-medium tabular-nums transition-colors focus-ring",
                    !everyYear && option === shown
                      ? "bg-primary/15 text-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {option}
                </button>
              ))}
            </div>
          ) : undefined
        }
      />
      {everyYear ? (
        <Timeline types={types} />
      ) : (
        <>
          {goals.data?.map((goal) => (
            <GoalBand
              key={goal.item_type}
              goal={goal}
              year={goalYear}
              types={types}
              finished={finishedOf(goal.item_type)}
              onChange={() => setEditing({ open: true, goal })}
            />
          ))}
          {/* No goal: the Diary opens with an invitation (Sprint 127). */}
          {goals.data?.length === 0 && invited && thisYear && (
            <GoalInvite
              domain={invited}
              done={finishedOf(invited.id).length}
              year={goalYear}
              onOther={() => setEditing({ open: true })}
            />
          )}
          {goals.data && goals.data.length > 0 && canSetGoal && (
            <p className="mt-6 text-sm text-muted-foreground">
              <button
                type="button"
                onClick={() => setEditing({ open: true })}
                className="min-h-11 font-medium text-foreground underline decoration-primary decoration-2 underline-offset-4 focus-ring"
              >
                Add a goal for another library
              </button>
            </p>
          )}
          <GoalDialog
            open={editing.open}
            onOpenChange={(open) => setEditing((value) => ({ ...value, open }))}
            types={types}
            initial={editing.goal}
          />
          {diary.isPending ? (
            <Loading
              label="Loading your diary…"
              shape="grid"
              className="mt-8"
            />
          ) : diary.isError ? (
            <p role="alert" className="mt-8 text-destructive">
              The diary could not be loaded.
            </p>
          ) : diary.data.months.length === 0 ? (
            <EmptyState title={`Nothing finished in ${shown}`} className="mt-8">
              An entry joins the diary when it has a finish date: set one on its
              page, or import from a source that records it.
            </EmptyState>
          ) : (
            <>
              <p className="mt-6">
                <Link
                  to={`/diary/${shown}/review`}
                  className="inline-flex min-h-11 items-center font-medium text-primary-text underline-offset-4 hover:underline focus-ring"
                >
                  Your {shown} in review
                </Link>
              </p>
              <ol className="mt-4 space-y-10">
                {diary.data.months.map((month) => (
                  <li
                    key={month.month}
                    aria-labelledby={`month-${month.month}`}
                  >
                    <h2
                      id={`month-${month.month}`}
                      className="font-display text-2xl font-medium tracking-tight"
                    >
                      {monthName(month.month)}
                    </h2>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {Object.entries(month.counts)
                        .map(([id, count]) => labelFor(id, count))
                        .join(", ")}
                    </p>
                    {/* A month's only cover is drawn large, a busy month's at shelf
                  size (Sprint 104, the owner's "play with cover sizing"). */}
                    <ul
                      className={cn(
                        "mt-4 grid gap-4",
                        month.entries.length === 1
                          ? "max-w-[11rem] grid-cols-1 sm:max-w-[13rem]"
                          : "grid-cols-2 sm:grid-cols-4 lg:grid-cols-5",
                      )}
                    >
                      {month.entries.map((entry) => (
                        <li key={entry.id}>
                          <button
                            type="button"
                            onClick={() =>
                              navigateWithTransition(
                                navigate,
                                `/books/${entry.id}`,
                              )
                            }
                            className="block w-full rounded-md text-left focus-ring"
                            aria-label={`Open ${entry.item.title}`}
                          >
                            <CoverImage
                              src={entry.item.cover_url}
                              alt=""
                              className="aspect-[2/3] w-full rounded-[3px_7px_7px_3px] object-cover shadow-[inset_4px_0_0_rgba(0,0,0,0.15),0_12px_22px_-12px_rgba(28,25,23,0.45)]"
                            />
                            <span className="mt-2 block truncate text-sm font-medium">
                              {entry.item.title}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ol>
            </>
          )}
        </>
      )}
    </main>
  );
}
