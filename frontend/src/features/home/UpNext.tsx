import { useState } from "react";
import { Link } from "react-router-dom";

import type { HomeNext, ModuleSize } from "@/api/home";
import type { ItemType, LibraryEntry } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { FinishDialog } from "@/features/finish/FinishDialog";
import { finishAction, finishActionFor } from "@/features/finish/label";
import { statusWith } from "@/features/rescore/rescore";
import { cn } from "@/lib/utils";

import { HomeModule } from "./HomeModule";
import { useHomeWrite } from "./useHomeWrite";

const SHOWN: Record<ModuleSize, number> = { S: 3, M: 4, L: 5 };

/** Written out in full so Tailwind sees each class. */
const columns: Record<number, string> = {
  1: "min-[720px]:grid-cols-1",
  2: "min-[720px]:grid-cols-2",
  3: "min-[720px]:grid-cols-3",
  4: "min-[720px]:grid-cols-4",
  5: "min-[720px]:grid-cols-5",
};

/** The strongest reason the ranking gave; the rest stay with the pile. */
function reason(pick: HomeNext): string | null {
  return pick.reasons[0]?.text ?? null;
}

/**
 * What comes next (Sprints 130, 132): the pile ranked across libraries, each pick
 * with the strongest reason the ranking found and *Start*, which moves it to its
 * domain's under-way status. A domain with no under-way status (a film is watched or
 * not) offers *Finished* instead, through the finish sheet. Covers in a row; on a
 * phone the row scrolls inside the module, never the page.
 */
export function UpNext({
  picks,
  pile,
  types,
  size = "L",
  className,
}: {
  picks: HomeNext[];
  pile: number;
  types: ItemType[] | undefined;
  /** How many picks: three small, four medium, five large. */
  size?: ModuleSize;
  className?: string;
}) {
  const write = useHomeWrite();
  const shown = picks.slice(0, SHOWN[size]);
  const [finishing, setFinishing] = useState<LibraryEntry | null>(null);
  return (
    <HomeModule
      title="Up next"
      className={className}
      aside={
        pile ? (
          <Link
            to="/deck/planned"
            className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
          >
            {pile.toLocaleString()} on the pile →
          </Link>
        ) : undefined
      }
    >
      {shown.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nothing waiting. What you plan to read or watch next lands here.
        </p>
      ) : (
        <ol
          className={cn(
            "-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-1 min-[720px]:grid min-[720px]:overflow-visible",
            columns[shown.length],
          )}
        >
          {shown.map((pick, index) => {
            const start = statusWith(
              pick.entry.item.type,
              types,
              "in_progress",
            );
            const why = reason(pick);
            return (
              <li
                key={pick.entry.id}
                className="flex w-28 shrink-0 snap-start flex-col gap-1.5 min-[720px]:w-auto"
              >
                <span className="text-xs tabular-nums text-primary">
                  {index + 1}
                </span>
                <Link
                  to={`/books/${pick.entry.id}`}
                  className="rounded-md focus-ring"
                  aria-label={`Open ${pick.entry.item.title}`}
                >
                  <CoverImage
                    src={pick.entry.item.cover_url}
                    alt=""
                    className="aspect-[2/3] w-full rounded-md object-cover"
                  />
                </Link>
                <p className="line-clamp-2 text-sm font-medium leading-snug">
                  {pick.entry.item.title}
                </p>
                {why ? (
                  <p className="line-clamp-3 text-xs text-muted-foreground">
                    {why}
                  </p>
                ) : null}
                {start ? (
                  <button
                    type="button"
                    disabled={write.isPending}
                    aria-label={`Start ${pick.entry.item.title}`}
                    onClick={() =>
                      write.mutate({
                        entry: pick.entry,
                        changes: { status: start },
                      })
                    }
                    className={cn(
                      "mt-auto min-h-11 rounded-full border border-border text-sm font-medium transition-colors hover:bg-accent focus-ring disabled:opacity-50",
                      index === 0 &&
                        "border-transparent bg-primary text-primary-foreground hover:bg-primary/90",
                    )}
                  >
                    Start
                  </button>
                ) : (
                  <button
                    type="button"
                    aria-label={finishActionFor(
                      pick.entry.item.title,
                      pick.entry.item.type,
                      types,
                    )}
                    onClick={() => setFinishing(pick.entry)}
                    className="mt-auto min-h-11 rounded-full border border-border text-sm font-medium transition-colors hover:bg-accent focus-ring"
                  >
                    {finishAction(pick.entry.item.type, types)}
                  </button>
                )}
              </li>
            );
          })}
        </ol>
      )}
      <FinishDialog
        entry={finishing}
        types={types}
        onClose={() => setFinishing(null)}
      />
    </HomeModule>
  );
}
