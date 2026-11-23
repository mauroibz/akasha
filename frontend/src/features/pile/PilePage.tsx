import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getPile, type HomeNext } from "@/api/home";
import { queryKeys } from "@/api/keys";
import type { LibraryEntry } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/ui/empty-state";
import { Loading } from "@/components/ui/skeleton";
import { FinishDialog } from "@/features/finish/FinishDialog";
import { finishAction, finishActionFor } from "@/features/finish/label";
import { useHomeWrite } from "@/features/home/useHomeWrite";
import { domainsFrom } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { statusWith } from "@/features/rescore/rescore";
import { cn } from "@/lib/utils";

/** The whole pile: the ranking reads it in one pass (Sprint 132's budget is 2,000). */
const WHOLE = 1000;

const pill =
  "min-h-9 shrink-0 rounded-full border border-border px-3 text-sm font-medium transition-colors hover:bg-accent focus-ring disabled:opacity-50";

/**
 * The pile as a list (DEC-192): everything waiting across libraries, in the order *Up
 * next* offers it, each with its strongest reason and *Start*. A library filter
 * narrows it; *Sort in cards* is the deck, for keeping or letting go.
 */
export function PilePage() {
  const queryClient = useQueryClient();
  const itemTypes = useItemTypes();
  const pile = useQuery({
    queryKey: [...queryKeys.pile, WHOLE],
    queryFn: ({ signal }) => getPile(WHOLE, signal),
  });
  const write = useHomeWrite();
  const [library, setLibrary] = useState("");
  const [finishing, setFinishing] = useState<LibraryEntry | null>(null);
  const picks: HomeNext[] = Array.isArray(pile.data) ? pile.data : [];
  const counts = new Map<string, number>();
  for (const pick of picks)
    counts.set(
      pick.entry.item.type,
      (counts.get(pick.entry.item.type) ?? 0) + 1,
    );
  const libraries = domainsFrom(itemTypes.data).filter((type) =>
    counts.has(type.id),
  );
  const shown = library
    ? picks.filter((pick) => pick.entry.item.type === library)
    : picks;
  const refresh = () =>
    void queryClient.invalidateQueries({ queryKey: queryKeys.pile });

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-5 py-8">
      <PageHeader
        back={{ to: "/", label: "Home" }}
        title="The pile"
        lede="Everything waiting, in the order Up next offers it."
        count={picks.length || undefined}
        actions={
          <Link
            to="/deck/planned"
            className="text-sm font-medium underline-offset-4 hover:underline focus-ring"
          >
            Sort in cards →
          </Link>
        }
      />
      {libraries.length > 1 ? (
        <div
          role="group"
          aria-label="Library"
          className="mt-6 flex flex-wrap gap-2"
        >
          {[{ id: "", plural_label: "All" }, ...libraries].map((type) => (
            <button
              key={type.id}
              type="button"
              aria-pressed={library === type.id}
              onClick={() => setLibrary(type.id)}
              className={cn(
                pill,
                library === type.id &&
                  "border-transparent bg-primary text-primary-foreground hover:bg-primary/90",
              )}
            >
              {type.plural_label}{" "}
              <span className="tabular-nums opacity-70">
                {type.id ? counts.get(type.id) : picks.length}
              </span>
            </button>
          ))}
        </div>
      ) : null}
      {pile.isPending ? (
        <Loading label="Loading the pile…" />
      ) : picks.length === 0 ? (
        <EmptyState title="Nothing waiting">
          What you plan to read, watch or listen to next lands here.
        </EmptyState>
      ) : (
        <ol className="mt-6 divide-y divide-border">
          {shown.map((pick) => {
            const entry = pick.entry;
            const type = entry.item.type;
            const start = statusWith(type, itemTypes.data, "in_progress");
            const label = libraries.find((row) => row.id === type)?.label;
            const why = pick.reasons[0]?.text;
            return (
              <li key={entry.id} className="flex items-center gap-4 py-3">
                <span className="w-6 shrink-0 text-right text-xs tabular-nums text-primary">
                  {picks.indexOf(pick) + 1}
                </span>
                <Link
                  to={`/books/${entry.id}`}
                  className="w-10 shrink-0 focus-ring"
                  aria-label={`Open ${entry.item.title}`}
                >
                  <CoverImage
                    src={entry.item.cover_url ?? null}
                    alt=""
                    className="aspect-[2/3] w-10 rounded object-cover"
                  />
                </Link>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{entry.item.title}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {[entry.item.creator, label].filter(Boolean).join(" · ")}
                  </p>
                  {why ? (
                    <p className="truncate text-xs text-muted-foreground">
                      {why}
                    </p>
                  ) : null}
                </div>
                {start ? (
                  <button
                    type="button"
                    className={pill}
                    disabled={write.isPending}
                    aria-label={`Start ${entry.item.title}`}
                    onClick={() =>
                      write.mutate(
                        { entry, changes: { status: start } },
                        { onSuccess: refresh },
                      )
                    }
                  >
                    Start
                  </button>
                ) : (
                  <button
                    type="button"
                    className={pill}
                    aria-label={finishActionFor(
                      entry.item.title,
                      type,
                      itemTypes.data,
                    )}
                    onClick={() => setFinishing(entry)}
                  >
                    {finishAction(type, itemTypes.data)}
                  </button>
                )}
              </li>
            );
          })}
        </ol>
      )}
      <FinishDialog
        entry={finishing}
        types={itemTypes.data}
        onClose={() => setFinishing(null)}
        onFinished={refresh}
      />
    </main>
  );
}
