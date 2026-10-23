import { useEffect, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";

import {
  getLibraryPage,
  patchEntry,
  type EntryStatus,
  type LibraryEntry,
} from "@/api/library";
import { getShelves } from "@/api/shelves";
import { queryKeys } from "@/api/keys";
import { Button } from "@/components/ui/button";
import { Deck, DeckEnd } from "@/features/deck/Deck";
import { titleSize } from "@/features/deck/titleSize";
import {
  hotkeysFor,
  statusLabelFor,
  statusesFor,
} from "@/features/library/labels";
import { mergeUniqueEntries } from "@/features/library/library";
import { useItemTypes } from "@/features/library/useItemTypes";
import {
  draftFor,
  filingChanges,
  loadStatusDrafts,
  PASSED_STORAGE_KEY,
  saveStatusDrafts,
  triageFiltersFromParams,
  undoChanges,
  type CardDraft,
} from "@/features/triage/deck";
import { scoreChipClass } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * The inbox one card at a time (Sprint 106, DEC-170), the first chore on the shared
 * deck (Sprint 112).
 *
 * A full-screen layer over the shell: on a phone the list's selects took the row
 * and left every title three letters long. Here the cover is large, the whole
 * title is set under it, and status, score and shelves are on the same screen, so
 * an obvious card is one tap. *Later* writes nothing — deferring is fine — and the
 * card comes back after the rest of the deck.
 */
export function TriageDeckPage() {
  const [searchParams] = useSearchParams();
  const filters = useMemo(
    () => triageFiltersFromParams(searchParams),
    [searchParams],
  );
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const itemTypes = useItemTypes();

  const library = useInfiniteQuery({
    queryKey: queryKeys.triage.list(filters),
    queryFn: ({ pageParam, signal }) =>
      getLibraryPage(filters, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    retry: false,
  });
  const entries = useMemo(
    () =>
      mergeUniqueEntries(library.data?.pages.map((page) => page.items) ?? []),
    [library.data],
  );

  const shelfQuery = useQuery({
    queryKey: queryKeys.shelves,
    queryFn: getShelves,
    retry: false,
  });
  const shelves = useMemo(() => {
    const rows = shelfQuery.data;
    if (!Array.isArray(rows)) return [];
    return [...rows].sort((a, b) => a.name.localeCompare(b.name));
  }, [shelfQuery.data]);

  const listDrafts = useRef(loadStatusDrafts());

  // The list behind the deck is not refetched card by card (the filed set keeps
  // them out); leaving is when it catches up.
  useEffect(
    () => () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.triage.all });
    },
    [queryClient],
  );

  const statusLabel = (entry: LibraryEntry, status: EntryStatus) =>
    statusLabelFor(entry.item.type, itemTypes.data, status);
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.triage.count });
    void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
  };
  const close = () =>
    navigate({ pathname: "/inbox", search: searchParams.toString() });

  return (
    <Deck<LibraryEntry, CardDraft>
      label="Inbox"
      progressLabel="Progress through the inbox"
      closeLabel="Back to the inbox"
      onClose={close}
      source={{
        cards: entries,
        total: library.data?.pages[0]?.total ?? 0,
        isPending: library.isPending,
        isError: library.isError,
        hasNextPage: library.hasNextPage,
        isFetchingNextPage: library.isFetchingNextPage,
        fetchNextPage: () => void library.fetchNextPage(),
        refetch: () => void library.refetch(),
      }}
      loadingLabel="Shuffling the inbox…"
      errorTitle="The inbox could not be loaded"
      keyOf={(entry) => entry.id}
      entryOf={(entry) => entry}
      passedStorageKey={PASSED_STORAGE_KEY}
      initialDraft={(entry) =>
        draftFor(entry, itemTypes.data, listDrafts.current)
      }
      stamp={(entry, draft) => statusLabel(entry, draft.status)}
      file={async (entry, draft) => {
        await patchEntry(entry.id, filingChanges(entry, draft));
        if (listDrafts.current.delete(entry.id))
          saveStatusDrafts(listDrafts.current);
        refresh();
      }}
      unfile={async (entry, draft) => {
        await patchEntry(
          entry.id,
          undoChanges(entry, filingChanges(entry, draft)),
        );
        refresh();
      }}
      onKey={(event, current, { setDraft }) => {
        const status = hotkeysFor(current.item.type, itemTypes.data)[
          event.key.toLowerCase()
        ];
        if (status && status !== "unsorted") {
          setDraft({ status });
          return true;
        }
        if (/^[0-9]$/.test(event.key)) {
          setDraft({
            score: event.key === "0" ? 10 : Number(event.key),
            scoreTouched: true,
          });
          return true;
        }
        return false;
      }}
      renderControls={(current, { draft, setDraft, commit }) => {
        const statuses = statusesFor(current.item.type, itemTypes.data).filter(
          (status) => status.choosable,
        );
        return (
          <>
            {/* Everything a decision needs, on the same screen. */}
            <section
              aria-label={`Sort ${current.item.title}`}
              className="flex shrink-0 flex-col gap-2.5 md:justify-center md:gap-6"
            >
              <div className="text-center md:text-left">
                <h2
                  className={cn(
                    "line-clamp-4 font-display font-medium leading-tight tracking-tight",
                    titleSize(current.item.title),
                  )}
                  data-testid="deck-title"
                >
                  {current.item.title}
                </h2>
                <p className="mt-1 truncate text-sm text-muted-foreground md:mt-3 md:text-base">
                  {current.item.creator ?? "Unknown"}
                  {current.item.year !== null && (
                    <span className="tabular-nums">
                      {" · "}
                      {current.item.year}
                    </span>
                  )}
                </p>
              </div>

              <fieldset>
                <legend className="sr-only">Status</legend>
                <div
                  className={cn(
                    "grid gap-2",
                    statuses.length <= 4 ? "grid-cols-4" : "grid-cols-3",
                    "md:flex md:flex-wrap",
                  )}
                >
                  {statuses.map((status) => {
                    const selected = draft.status === status.value;
                    return (
                      <button
                        key={status.value}
                        type="button"
                        aria-pressed={selected}
                        onClick={() => setDraft({ status: status.value })}
                        className={cn(
                          "h-10 truncate rounded-full border px-3 text-sm font-medium transition-colors focus-ring md:h-11 md:px-5",
                          selected
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-surface hover:bg-accent",
                        )}
                      >
                        {status.label}
                        {status.hotkey && (
                          <kbd
                            aria-hidden="true"
                            className="ml-2 hidden font-sans text-xs opacity-60 md:inline"
                          >
                            {status.hotkey}
                          </kbd>
                        )}
                      </button>
                    );
                  })}
                </div>
              </fieldset>

              <fieldset>
                <legend className="sr-only">
                  Score
                  {current.score_provisional && !draft.scoreTouched
                    ? ", provisional from the import"
                    : ""}
                </legend>
                <div className="flex items-center gap-1">
                  {Array.from({ length: 10 }, (_, index) => index + 1).map(
                    (score) => {
                      const selected = draft.score === score;
                      return (
                        <button
                          key={score}
                          type="button"
                          aria-pressed={selected}
                          aria-label={`Score ${score}`}
                          onClick={() =>
                            setDraft({
                              score: selected ? null : score,
                              scoreTouched: true,
                            })
                          }
                          className={cn(
                            "h-9 min-w-0 flex-1 rounded-md text-sm font-medium tabular-nums transition-colors focus-ring md:h-11",
                            selected
                              ? scoreChipClass(score)
                              : "bg-surface text-muted-foreground hover:bg-accent hover:text-foreground",
                            selected &&
                              current.score_provisional &&
                              !draft.scoreTouched &&
                              "opacity-70 outline-dashed outline-1 outline-offset-2 outline-foreground/50",
                          )}
                        >
                          {score}
                        </button>
                      );
                    },
                  )}
                </div>
                {current.score_provisional && !draft.scoreTouched && (
                  <p className="mt-1 text-center text-xs text-muted-foreground md:text-left">
                    Score from the import — tap one to make it yours.
                  </p>
                )}
              </fieldset>

              {shelves.length > 0 && (
                <fieldset>
                  <legend className="sr-only">Shelves</legend>
                  <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] md:mx-0 md:flex-wrap md:overflow-visible md:px-0">
                    {shelves.map((shelf) => {
                      const on = draft.shelfIds.includes(shelf.id);
                      return (
                        <button
                          key={shelf.id}
                          type="button"
                          aria-pressed={on}
                          onClick={() =>
                            setDraft({
                              shelfIds: on
                                ? draft.shelfIds.filter((id) => id !== shelf.id)
                                : [...draft.shelfIds, shelf.id],
                            })
                          }
                          className={cn(
                            "h-8 shrink-0 rounded-full border px-3 text-xs transition-colors focus-ring",
                            on
                              ? "border-primary-text text-primary-text"
                              : "border-dashed border-border text-muted-foreground hover:text-foreground",
                          )}
                        >
                          {on ? "✓ " : "+ "}
                          {shelf.name}
                        </button>
                      );
                    })}
                  </div>
                </fieldset>
              )}

              <div className="grid grid-cols-[1fr_1.6fr] gap-3">
                <Button
                  variant="secondary"
                  className="h-12 gap-2 rounded-full text-base md:h-14"
                  onClick={() => commit("later")}
                >
                  <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                  Later
                </Button>
                <Button
                  className="h-12 gap-2 rounded-full text-base md:h-14"
                  onClick={() => commit("file")}
                  aria-label={`File as ${statusLabel(current, draft.status)}`}
                >
                  <span className="truncate">
                    File as {statusLabel(current, draft.status)}
                  </span>
                  <ArrowRight className="h-4 w-4 shrink-0" aria-hidden="true" />
                </Button>
              </div>
              <p className="hidden text-xs text-muted-foreground md:block">
                <kbd>→</kbd> file · <kbd>←</kbd> later · <kbd>1</kbd>–
                <kbd>0</kbd> score · <kbd>i</kbd> turn over ·{" "}
                <kbd>Backspace</kbd> undo · <kbd>Esc</kbd> leave. On a phone,
                swipe the card.
              </p>
            </section>
          </>
        );
      }}
      renderEnd={({ filed, passedNow, waitingPassed, roundAgain, close }) => {
        const clear = waitingPassed === 0;
        return (
          <DeckEnd
            entries={filed.map(({ card }) => card)}
            title={clear ? "Inbox clear" : "That’s the deck"}
            summary={`${
              filed.length === 0
                ? "Nothing filed this time"
                : `${filed.length} filed`
            }${passedNow > 0 ? ` · ${passedNow} left for later` : ""}${
              clear && filed.length > 0 ? ". Every one has a place." : "."
            }`}
          >
            {!clear && (
              <Button className="rounded-full px-5" onClick={roundAgain}>
                Go through the {waitingPassed} you passed
              </Button>
            )}
            <Button
              variant={clear ? "default" : "secondary"}
              className="rounded-full px-5"
              onClick={close}
            >
              Back to the inbox
            </Button>
          </DeckEnd>
        );
      }}
    />
  );
}
