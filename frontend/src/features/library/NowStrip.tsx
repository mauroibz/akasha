import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import { getNow, patchEntry, type LibraryEntry } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { useItemTypes } from "@/features/library/useItemTypes";
import { navigateWithTransition } from "@/lib/viewTransition";

/** Pages advance ten at a time, everything else one: an episode, a chapter. */
function stepFor(unit: string): number {
  return unit === "page" ? 10 : 1;
}

/**
 * What you are in the middle of, across every domain (Sprint 098, proposal §7): the
 * screen people would open daily. A cover, how far through, and one tap to advance
 * where the domain counts progress. Hidden when nothing is under way.
 */
export function NowStrip() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const itemTypes = useItemTypes();
  const now = useQuery({
    queryKey: queryKeys.now,
    queryFn: ({ signal }) => getNow(signal),
    staleTime: 30_000,
  });
  const advance = useMutation({
    mutationFn: ({
      entry,
      progress,
    }: {
      entry: LibraryEntry;
      progress: number;
    }) => patchEntry(entry.id, { progress }),
    onMutate: async ({ entry, progress }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.now });
      const before = queryClient.getQueryData<LibraryEntry[]>(queryKeys.now);
      queryClient.setQueryData<LibraryEntry[]>(queryKeys.now, (rows) =>
        rows?.map((row) => (row.id === entry.id ? { ...row, progress } : row)),
      );
      return { before };
    },
    onError: (_error, _vars, context) => {
      queryClient.setQueryData(queryKeys.now, context?.before);
      toast.error("Your progress could not be saved", {
        description: "The previous value was restored.",
      });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    },
  });

  // Anything but a list is nothing under way: a strip must not be able to take the
  // library page down with it.
  const rows = Array.isArray(now.data) ? now.data : [];
  if (rows.length === 0) return null;
  const types = Array.isArray(itemTypes.data) ? itemTypes.data : [];

  return (
    // Its own spacing, so nothing at all is drawn when nothing is under way (the
    // library spec holds the first cover's position).
    <section aria-labelledby="now-heading" className="mb-6 pt-5">
      <h2
        id="now-heading"
        className="mb-3 font-display text-2xl font-medium tracking-tight"
      >
        Now
      </h2>
      <ul className="flex gap-4 overflow-x-auto pb-2">
        {rows.map((entry) => {
          const spec =
            types.find((type) => type.id === entry.item.type)?.progress ?? null;
          const totalValue = spec?.total_field
            ? entry.item.metadata[spec.total_field]
            : undefined;
          const total =
            typeof totalValue === "number" && totalValue > 0
              ? totalValue
              : null;
          const done = entry.progress ?? 0;
          const step = spec ? stepFor(spec.unit_label) : 0;
          return (
            <li key={entry.id} className="w-36 shrink-0">
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
                  className="aspect-[2/3] w-36 rounded-md object-cover"
                />
              </button>
              <p className="mt-2 truncate text-sm font-medium">
                {entry.item.title}
              </p>
              {spec ? (
                <>
                  {total ? (
                    <div
                      className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted"
                      role="progressbar"
                      aria-label={`${spec.label} of ${entry.item.title}`}
                      aria-valuemin={0}
                      aria-valuemax={total}
                      aria-valuenow={Math.min(done, total)}
                    >
                      <div
                        className="h-full rounded-full bg-primary transition-[width] duration-300"
                        style={{
                          width: `${Math.min(100, (done / total) * 100)}%`,
                        }}
                      />
                    </div>
                  ) : null}
                  <div className="mt-1.5 flex items-center justify-between gap-2">
                    <span className="truncate text-xs text-muted-foreground">
                      {total ? `${done} / ${total}` : done} {spec.unit_label}s
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        advance.mutate({ entry, progress: done + step })
                      }
                      aria-label={`Add ${step} ${spec.unit_label}${step === 1 ? "" : "s"} to ${entry.item.title}`}
                      className="shrink-0 rounded-full border border-border px-2 py-0.5 text-xs font-medium hover:bg-accent focus-ring"
                    >
                      +{step}
                    </button>
                  </div>
                </>
              ) : (
                <p className="mt-1 text-xs text-muted-foreground">
                  In progress
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
