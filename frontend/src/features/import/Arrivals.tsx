import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getLibraryPage } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { useJobEvent, useJobs } from "@/features/activity/jobEvents";
import { defaultLibraryFilters } from "@/features/library/library";

const SHOWN = 12;

/**
 * An import arriving (Sprint 097, proposal I6): the batch's newest Inbox entries, whose
 * covers fill in as its enrichment jobs finish, and how many are in. Before this the
 * covers and details arrived silently, or did not, and nothing on screen said which.
 */
export function Arrivals({
  batchId,
  expected,
}: {
  batchId: string;
  /** How many items the commit created, each with one enrichment job queued. */
  expected: number;
}) {
  const queryClient = useQueryClient();
  const key = ["arrivals", batchId] as const;
  const entries = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      getLibraryPage(
        {
          ...defaultLibraryFilters,
          statuses: ["unsorted"],
          sort: "date_added",
          order: "desc",
        },
        undefined,
        signal,
        Math.min(Math.max(expected, 1), 100),
      ),
    staleTime: 2_000,
  });
  const jobs = useJobs().filter(
    (job) => job.batch_id === batchId && job.kind === "enrich_item",
  );
  const finished = jobs.filter((job) =>
    ["succeeded", "failed", "cancelled"].includes(job.state),
  ).length;
  useJobEvent((event) => {
    if (event.batch_id === batchId && event.state === "succeeded")
      void queryClient.invalidateQueries({ queryKey: key });
  });

  // The batch is the newest `expected` Inbox entries; enrichment runs them in the
  // order they were queued, first row first, so the strip shows that end of the
  // batch: the covers that arrive soonest, not the twelve that arrive last.
  const rows = (entries.data?.items ?? [])
    .slice(0, expected)
    .reverse()
    .slice(0, SHOWN);
  if (expected === 0 || rows.length === 0) return null;
  const done = Math.min(finished, expected);
  return (
    <section className="mt-5" aria-labelledby="arrivals-heading">
      <h3 id="arrivals-heading" className="text-sm font-medium">
        Arriving
      </h3>
      {/* No live region of its own: it sits inside the result panel's, and two
          nested status regions announce twice (DEC-028). */}
      <p className="mt-0.5 text-sm text-muted-foreground">
        {done >= expected
          ? `All ${expected} filled in.`
          : `${done} of ${expected} filled in. Covers and details appear as they are found.`}
      </p>
      <ul className="mt-3 flex gap-2 overflow-x-auto pb-1">
        {rows.map((entry) => (
          <li key={entry.id} className="w-14 shrink-0">
            <CoverImage
              src={entry.item.cover_url}
              alt={`Cover of ${entry.item.title}`}
              className="aspect-[2/3] w-14 rounded-sm object-cover"
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
