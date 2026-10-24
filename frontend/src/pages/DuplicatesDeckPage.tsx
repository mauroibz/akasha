import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check } from "lucide-react";

import {
  dismissDuplicate,
  getDuplicates,
  mergeEntries,
  undismissDuplicate,
  type DuplicatePair,
} from "@/api/duplicates";
import type { LibraryEntry } from "@/api/library";
import { queryKeys } from "@/api/keys";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import { Deck, DeckEnd, type DeckControls } from "@/features/deck/Deck";
import { formatLabels, statusLabelFor } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { TypesetCover } from "@/features/shelves/OpeningCover";
import { cn } from "@/lib/utils";

type Side = "a" | "b";
type Draft = { keep: Side | null; different: boolean };

const other = (side: Side): Side => (side === "a" ? "b" : "a");

/**
 * Duplicates, two at a time (Sprint 113, DEC-176): the same work entered twice, side
 * by side, with what differs marked. The owner picks the one to keep and is told what
 * happens before *Merge*; nothing the other holds is lost (the server fills only what
 * the kept one lacks). A merge cannot be undone; *They're different* can.
 */
export function DuplicatesDeckPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const itemTypes = useItemTypes();
  const found = useQuery({
    queryKey: ["chores", "duplicates"],
    queryFn: ({ signal }) => getDuplicates(signal),
    retry: false,
  });
  // Entries merged away this round: a pair that held one is no longer a pair.
  const [gone, setGone] = useState<Set<number>>(new Set());
  const pairs = useMemo(
    () =>
      (found.data ?? []).filter(
        (pair) => !gone.has(pair.a.id) && !gone.has(pair.b.id),
      ),
    [found.data, gone],
  );

  return (
    <Deck<DuplicatePair, Draft>
      label="Duplicates"
      progressLabel="Progress through possible duplicates"
      closeLabel="Back to Tidy up"
      onClose={() => navigate("/deck")}
      source={{
        cards: pairs,
        total: pairs.length,
        isPending: found.isPending,
        isError: found.isError,
        hasNextPage: false,
        isFetchingNextPage: false,
        fetchNextPage: () => undefined,
        refetch: () => void found.refetch(),
      }}
      loadingLabel="Looking for duplicates…"
      errorTitle="Duplicates could not be found"
      keyOf={(pair) => pair.a.id * 1_000_000 + pair.b.id}
      entryOf={(pair) => pair.a}
      cardFace={(pair) => <PairFace pair={pair} />}
      initialDraft={() => ({ keep: null, different: false })}
      canFile={(_pair, draft) => draft.different || draft.keep !== null}
      canUndo={(_pair, draft) => draft.different}
      stamp={(_pair, draft) => (draft.different ? "Different" : "Merge")}
      filedNoun="settled"
      file={async (pair, draft) => {
        if (draft.different) {
          await dismissDuplicate(pair.a.id, pair.b.id);
          return;
        }
        const keep = pair[draft.keep!];
        const drop = pair[other(draft.keep!)];
        await mergeEntries(keep.id, drop.id);
        setGone((ids) => new Set(ids).add(drop.id));
        void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      }}
      unfile={async (pair, draft) => {
        if (draft.different) await undismissDuplicate(pair.a.id, pair.b.id);
      }}
      renderControls={(pair, controls) => (
        <PairControls
          pair={pair}
          controls={controls}
          statusOf={(entry) =>
            statusLabelFor(entry.item.type, itemTypes.data, entry.status)
          }
          formats={formatLabels(itemTypes.data)}
        />
      )}
      renderEnd={({ filed, passedNow, waitingPassed, roundAgain, close }) => {
        const merged = filed.filter(({ draft }) => !draft.different).length;
        return (
          <DeckEnd
            entries={[]}
            title={waitingPassed ? "That’s the deck" : "No duplicates left"}
            summary={`${merged} merged · ${filed.length - merged} kept apart${
              passedNow ? ` · ${passedNow} left for later` : ""
            }.`}
          >
            {waitingPassed > 0 && (
              <Button className="rounded-full px-5" onClick={roundAgain}>
                Go through the {waitingPassed} you passed
              </Button>
            )}
            <Button
              variant={waitingPassed ? "secondary" : "default"}
              className="rounded-full px-5"
              onClick={close}
            >
              Back to Tidy up
            </Button>
          </DeckEnd>
        );
      }}
    />
  );
}

/** The card's front: the two covers, side by side. */
function PairFace({ pair }: { pair: DuplicatePair }) {
  return (
    <div className="grid h-full w-full grid-cols-2 gap-1 bg-surface-raised p-1">
      {[pair.a, pair.b].map((entry) => (
        <div key={entry.id} className="overflow-hidden rounded-xl">
          {entry.item.cover_url ? (
            <CoverImage
              src={entry.item.cover_url}
              alt={`Cover of ${entry.item.title}`}
              className="h-full w-full object-cover [&_img]:pointer-events-none"
            />
          ) : (
            <TypesetCover title={entry.item.title} seed={entry.id} />
          )}
        </div>
      ))}
    </div>
  );
}

function PairControls({
  pair,
  controls: { draft, setDraft, commit },
  statusOf,
  formats,
}: {
  pair: DuplicatePair;
  controls: DeckControls<Draft>;
  statusOf: (entry: LibraryEntry) => string;
  formats: Record<string, string>;
}) {
  const facts = (entry: LibraryEntry): Array<[string, string]> => [
    ["Year", String(entry.item.year ?? "—")],
    ["Status", statusOf(entry)],
    ["Score", entry.score === null ? "—" : String(entry.score)],
    ["Finished", entry.date_finished ?? "—"],
    ["Shelves", entry.shelves.map((shelf) => shelf.name).join(", ") || "—"],
    [
      "Formats",
      entry.formats.map((format) => formats[format] ?? format).join(", ") ||
        "—",
    ],
    ["Notes", entry.notes ? "Yes" : "—"],
    ["Added", entry.date_added.slice(0, 10)],
  ];
  const left = facts(pair.a);
  const right = facts(pair.b);
  const keep = draft.keep ? pair[draft.keep] : null;
  const drop = draft.keep ? pair[other(draft.keep)] : null;
  return (
    <section
      aria-label="Which one to keep"
      className="flex shrink-0 flex-col gap-3 md:justify-center md:gap-5"
    >
      <p className="text-center text-sm text-muted-foreground md:text-left">
        {pair.reason}. Keep one: the other is removed, and anything this one
        lacks is filled from it.
      </p>
      <div className="grid grid-cols-2 gap-3">
        {(["a", "b"] as const).map((side, column) => {
          const entry = pair[side];
          const rows = column === 0 ? left : right;
          const others = column === 0 ? right : left;
          const chosen = draft.keep === side;
          return (
            <div
              key={side}
              role="group"
              aria-label={entry.item.title}
              className={cn(
                "flex min-w-0 flex-col gap-2 rounded-xl border p-3 transition-colors",
                chosen ? "border-primary bg-primary/10" : "border-border",
              )}
            >
              <p className="line-clamp-3 font-display text-lg font-medium leading-tight md:text-2xl">
                {entry.item.title}
              </p>
              <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs md:text-sm">
                {rows.map(([name, value], index) => (
                  <div key={name} className="contents">
                    <dt className="text-muted-foreground">{name}</dt>
                    <dd
                      className={cn(
                        "min-w-0 truncate",
                        value !== others[index][1] && "font-semibold",
                      )}
                    >
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
              <Button
                variant={chosen ? "default" : "outline"}
                size="sm"
                aria-pressed={chosen}
                className="mt-auto gap-1 rounded-full"
                onClick={() =>
                  setDraft({ keep: chosen ? null : side, different: false })
                }
              >
                {chosen && <Check className="h-4 w-4" aria-hidden="true" />}
                Keep this one
              </Button>
            </div>
          );
        })}
      </div>
      {keep && drop && (
        <p className="text-center text-sm md:text-left" role="status">
          {drop.item.title} is removed. Its score, dates, notes, shelves,
          formats, place and loans fill what {keep.item.title} lacks.
        </p>
      )}
      <div className="grid grid-cols-3 gap-2">
        <Button
          variant="secondary"
          className="h-12 gap-1 rounded-full md:h-14"
          onClick={() => commit("later")}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Later
        </Button>
        <Button
          variant="outline"
          className="h-12 rounded-full md:h-14"
          onClick={() => commit("file", { different: true, keep: null })}
        >
          They’re different
        </Button>
        <Button
          className="h-12 rounded-full md:h-14"
          disabled={!keep}
          onClick={() => commit("file")}
        >
          Merge
        </Button>
      </div>
    </section>
  );
}
