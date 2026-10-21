import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { queryKeys } from "@/api/keys";
import { getDiary } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/ui/empty-state";
import { Loading } from "@/components/ui/skeleton";
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
 */
export function DiaryPage() {
  const navigate = useNavigate();
  const [year, setYear] = useState<number | undefined>(undefined);
  const itemTypes = useItemTypes();
  const diary = useQuery({
    queryKey: queryKeys.diary(year),
    queryFn: ({ signal }) => getDiary(year, signal),
  });
  const types = Array.isArray(itemTypes.data) ? itemTypes.data : [];
  const labelFor = (id: string, count: number) => {
    const label = (
      types.find((type) => type.id === id)?.label ?? id
    ).toLowerCase();
    return `${count} ${label}${count === 1 ? "" : label.endsWith("s") ? "" : "s"}`;
  };
  const shown = diary.data?.year ?? year;
  const years = diary.data?.years ?? [];

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-5 py-8">
      <PageHeader
        title="Diary"
        lede="What you finished, month by month."
        actions={
          years.length > 1 ? (
            <div
              role="group"
              aria-label="Year"
              className="flex flex-wrap gap-1.5"
            >
              {years.map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={option === shown}
                  onClick={() => setYear(option)}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-sm font-medium tabular-nums transition-colors focus-ring",
                    option === shown
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
      {diary.isPending ? (
        <Loading label="Loading your diary…" shape="grid" className="mt-8" />
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
        <ol className="mt-8 space-y-10">
          {diary.data.months.map((month) => (
            <li key={month.month} aria-labelledby={`month-${month.month}`}>
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
              <ul className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-6">
                {month.entries.map((entry) => (
                  <li key={entry.id}>
                    <button
                      type="button"
                      onClick={() =>
                        navigateWithTransition(navigate, `/books/${entry.id}`)
                      }
                      className="block w-full rounded-md text-left focus-ring"
                      aria-label={`Open ${entry.item.title}`}
                    >
                      <CoverImage
                        src={entry.item.cover_url}
                        alt=""
                        className="aspect-[2/3] w-full rounded-md object-cover"
                      />
                      <span className="mt-1.5 block truncate text-xs font-medium">
                        {entry.item.title}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}
