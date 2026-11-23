import { useState } from "react";
import { Link } from "react-router-dom";

import type { ItemType, LibraryEntry } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { FinishDialog } from "@/features/finish/FinishDialog";
import { countLabel, progressFor } from "@/features/library/labels";
import { stepFor } from "@/features/progress/outline";
import { statusWith } from "@/features/rescore/rescore";
import { cn } from "@/lib/utils";

import { HomeModule } from "./HomeModule";
import { useHomeWrite } from "./useHomeWrite";

const pill =
  "inline-flex min-h-11 items-center rounded-full border border-border px-3 text-sm font-medium transition-colors hover:bg-accent focus-ring disabled:opacity-50";

function totalOf(entry: LibraryEntry, field: string | null): number | null {
  if (!field) return null;
  const value = entry.item.metadata[field];
  return typeof value === "number" && value > 0 ? value : null;
}

/**
 * What is under way, across every domain (Sprint 130): the first entry large, the
 * rest as a row. Log progress where the domain counts it, *Finished* through the
 * same sheet the detail page opens, *Set aside* back onto the domain's pile.
 */
export function OnNow({
  entries,
  types,
  className,
}: {
  entries: LibraryEntry[];
  types: ItemType[] | undefined;
  className?: string;
}) {
  const write = useHomeWrite();
  const [finishing, setFinishing] = useState<LibraryEntry | null>(null);
  const counts = new Map<string, number>();
  for (const entry of entries)
    counts.set(entry.item.type, (counts.get(entry.item.type) ?? 0) + 1);
  const [lead, ...rest] = entries;

  function actions(entry: LibraryEntry, primary: boolean) {
    const spec = progressFor(entry.item.type, types);
    const planned = statusWith(entry.item.type, types, "planned");
    const step = spec ? stepFor(spec.unit_label) : 0;
    const done = entry.progress ?? 0;
    const title = entry.item.title;
    return (
      <div className="flex flex-wrap gap-2">
        {spec ? (
          <button
            type="button"
            className={cn(
              pill,
              primary &&
                "border-transparent bg-primary text-primary-foreground hover:bg-primary/90",
            )}
            disabled={write.isPending}
            aria-label={`Add ${step} ${spec.unit_label}${step === 1 ? "" : "s"} to ${title}`}
            onClick={() =>
              write.mutate({ entry, changes: { progress: done + step } })
            }
          >
            +{step === 1 ? "" : `${step} `}
            {spec.unit_label}
            {step === 1 ? "" : "s"}
          </button>
        ) : null}
        <button
          type="button"
          className={pill}
          aria-label={`Finished ${title}`}
          onClick={() => setFinishing(entry)}
        >
          Finished
        </button>
        {planned ? (
          <button
            type="button"
            className={pill}
            disabled={write.isPending}
            aria-label={`Set ${title} aside`}
            onClick={() =>
              write.mutate({ entry, changes: { status: planned } })
            }
          >
            Set aside
          </button>
        ) : null}
      </div>
    );
  }

  function howFar(entry: LibraryEntry) {
    const spec = progressFor(entry.item.type, types);
    if (!spec) return null;
    const total = totalOf(entry, spec.total_field);
    const done = entry.progress;
    if (done === null || done === undefined)
      return (
        <p className="text-xs text-muted-foreground">
          No {spec.unit_label}s logged yet
        </p>
      );
    return (
      <div className="space-y-1">
        {total ? (
          <div
            className="h-1.5 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label={`${spec.label} of ${entry.item.title}`}
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={Math.min(done, total)}
          >
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.min(100, (done / total) * 100)}%` }}
            />
          </div>
        ) : null}
        <p className="text-xs tabular-nums text-muted-foreground">
          {total ? `${done} / ${total}` : done} {spec.unit_label}s
        </p>
      </div>
    );
  }

  return (
    <HomeModule
      title="On now"
      className={className}
      aside={
        entries.length
          ? [...counts]
              .map(([type, count]) => countLabel(count, type, types))
              .join(" · ")
          : undefined
      }
    >
      {!lead ? (
        <p className="text-sm text-muted-foreground">
          Nothing under way. Start something from the pile.
        </p>
      ) : (
        <>
          <div className="flex gap-4">
            <Link
              to={`/books/${lead.id}`}
              className="w-24 shrink-0 rounded-md focus-ring sm:w-28"
              aria-label={`Open ${lead.item.title}`}
            >
              <CoverImage
                src={lead.item.cover_url}
                alt=""
                className="aspect-[2/3] w-full rounded-md object-cover"
              />
            </Link>
            <div className="min-w-0 flex-1 space-y-2">
              <h3 className="font-display text-xl font-medium leading-snug">
                {lead.item.title}
              </h3>
              {lead.item.creator ? (
                <p className="truncate text-xs text-muted-foreground">
                  {lead.item.creator}
                </p>
              ) : null}
              {howFar(lead)}
              {actions(lead, true)}
            </div>
          </div>
          {rest.length ? (
            <ul className="mt-4 space-y-3 border-t border-border pt-3">
              {rest.map((entry) => (
                <li key={entry.id} className="flex gap-3">
                  <Link
                    to={`/books/${entry.id}`}
                    className="w-12 shrink-0 rounded focus-ring"
                    aria-label={`Open ${entry.item.title}`}
                  >
                    <CoverImage
                      src={entry.item.cover_url}
                      alt=""
                      className="aspect-[2/3] w-full rounded object-cover"
                    />
                  </Link>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <p className="truncate text-sm font-medium">
                      {entry.item.title}
                    </p>
                    {howFar(entry)}
                    {actions(entry, false)}
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}
      <FinishDialog
        entry={finishing}
        types={types}
        onClose={() => setFinishing(null)}
      />
    </HomeModule>
  );
}
