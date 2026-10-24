import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/keys";
import { getEntry, getGaps, type LibraryEntry } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Loading } from "@/components/ui/skeleton";
import { useItemTypes } from "@/features/library/useItemTypes";
import { OneQuestion } from "@/features/questions/OneQuestion";

/**
 * Fill in the gaps (Sprint 125, DEC-179): the finished books missing a date or a
 * format, one at a time, each asking Sprint 124's questions. The list is read once
 * when the page opens, so answering never reshuffles what is coming.
 */
export function GapsPage() {
  const itemTypes = useItemTypes();
  const gaps = useQuery({
    queryKey: ["play", "gaps", "deck"],
    queryFn: ({ signal }) => getGaps(signal),
    staleTime: Infinity,
  });
  const [index, setIndex] = useState(0);
  const entries = gaps.data?.entries ?? [];
  const current = entries[index];

  return (
    <main className="mx-auto min-h-screen w-full max-w-xl px-5 pb-24 pt-8">
      <PageHeader
        back={{ to: "/insights", label: "Insights" }}
        eyebrow="Play"
        title="Fill in the gaps"
        count={
          current ? (
            <span className="tabular-nums">
              {index + 1} of {entries.length}
            </span>
          ) : undefined
        }
      />
      {gaps.isPending ? (
        <Loading label="Finding the gaps…" className="mt-10" />
      ) : !current ? (
        <EmptyState title="That's every gap for now" className="mt-10">
          Back to{" "}
          <Link to="/insights" className="underline underline-offset-4">
            Insights
          </Link>
          .
        </EmptyState>
      ) : (
        <Card
          key={current.id}
          entry={current}
          types={itemTypes.data}
          onNext={() => setIndex((value) => value + 1)}
        />
      )}
    </main>
  );
}

function Card({
  entry,
  types,
  onNext,
}: {
  entry: LibraryEntry;
  types: ReturnType<typeof useItemTypes>["data"];
  onNext: () => void;
}) {
  // The entry as it is now: each answer refetches it and the next question follows.
  const live = useQuery({
    queryKey: queryKeys.entry(entry.id),
    queryFn: () => getEntry(entry.id),
    initialData: entry,
  });
  const shown = live.data ?? entry;
  const creators = shown.item.metadata?.creators;
  return (
    <section className="mt-8">
      <div className="flex items-end gap-5">
        <CoverImage
          src={shown.item.cover_url ?? null}
          alt=""
          className="aspect-[2/3] w-28 shrink-0 rounded-[3px_8px_8px_3px] object-cover shadow-lg"
        />
        <div className="min-w-0">
          <h2 className="font-display text-3xl font-medium leading-tight">
            {shown.item.title}
          </h2>
          {Array.isArray(creators) && creators.length > 0 && (
            <p className="mt-1 text-sm text-muted-foreground">
              {creators.join(", ")}
            </p>
          )}
        </div>
      </div>
      <OneQuestion entry={shown} types={types} />
      <div className="mt-6 flex justify-end">
        <Button className="rounded-full px-6" onClick={onNext}>
          Next book
        </Button>
      </div>
    </section>
  );
}
