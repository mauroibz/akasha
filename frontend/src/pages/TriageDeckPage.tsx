import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { m } from "motion/react";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Undo2, X } from "lucide-react";

import {
  getLibraryPage,
  patchEntry,
  type EntryStatus,
  type LibraryEntry,
} from "@/api/library";
import { getShelves } from "@/api/shelves";
import { queryKeys } from "@/api/keys";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/ui/skeleton";
import {
  hotkeysFor,
  statusLabelFor,
  statusesFor,
} from "@/features/library/labels";
import { mergeUniqueEntries } from "@/features/library/library";
import { useItemTypes } from "@/features/library/useItemTypes";
import {
  DeckCard,
  DepartingCard,
  WaitingCard,
  type DeckDirection,
} from "@/features/triage/DeckCard";
import {
  deckQueue,
  draftFor,
  filingChanges,
  loadPassed,
  loadStatusDrafts,
  savePassed,
  saveStatusDrafts,
  triageFiltersFromParams,
  undoChanges,
  type CardDraft,
} from "@/features/triage/deck";
import { TypesetCover } from "@/features/shelves/OpeningCover";
import { useMotionPresets } from "@/lib/motion";
import { scoreChipClass } from "@/lib/score";
import { cn } from "@/lib/utils";

type DeckAction =
  | {
      kind: "filed";
      entry: LibraryEntry;
      draft: CardDraft;
      changes: ReturnType<typeof filingChanges>;
    }
  | { kind: "passed"; entry: LibraryEntry; draft: CardDraft };

/** A key the deck answers only when focus is not in a field the owner types into. */
function isTypingTarget(target: EventTarget | null) {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

/**
 * The inbox one card at a time (Sprint 106, DEC-170).
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
  const presets = useMotionPresets();
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
  const total = library.data?.pages[0]?.total ?? 0;

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

  const [filed, setFiled] = useState<Map<number, LibraryEntry>>(new Map());
  const [passed, setPassed] = useState<number[]>(loadPassed);
  const [passedNow, setPassedNow] = useState(0);
  const [history, setHistory] = useState<DeckAction[]>([]);
  const [cardDrafts, setCardDrafts] = useState<Map<number, CardDraft>>(
    new Map(),
  );
  // Cards on their way out: a copy flies off while the next card is already live,
  // so a fast hand on the keys is never made to wait for an animation.
  const [ghosts, setGhosts] = useState<
    Array<{
      key: number;
      entry: LibraryEntry;
      direction: DeckDirection;
      fromX: number;
      stamp: string;
    }>
  >([]);
  const ghostKey = useRef(0);
  const [flipped, setFlipped] = useState(false);
  const listDrafts = useRef(loadStatusDrafts());
  // A filing's request, so an undo straight after waits for it rather than racing it.
  const inFlight = useRef(new Map<number, Promise<unknown>>());

  useEffect(() => savePassed(passed), [passed]);

  const filedIds = useMemo(() => new Set(filed.keys()), [filed]);
  const passedIds = useMemo(() => new Set(passed), [passed]);
  const queue = useMemo(
    () => deckQueue(entries, filedIds, passedIds),
    [entries, filedIds, passedIds],
  );
  const current = queue[0];
  const unloaded = library.hasNextPage
    ? Math.max(0, total - entries.length)
    : 0;
  const left = queue.length + unloaded;
  const waitingPassed = entries.filter(
    (entry) => passedIds.has(entry.id) && !filedIds.has(entry.id),
  ).length;
  const done = filed.size + passedNow;

  // Keep a few cards ahead loaded.
  useEffect(() => {
    if (queue.length < 5 && library.hasNextPage && !library.isFetchingNextPage)
      void library.fetchNextPage();
  }, [queue.length, library]);

  // The list behind the deck is not refetched card by card (the filed set keeps
  // them out); leaving is when it catches up.
  useEffect(
    () => () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.triage.all });
    },
    [queryClient],
  );

  const draft = current
    ? (cardDrafts.get(current.id) ??
      draftFor(current, itemTypes.data, listDrafts.current))
    : null;
  const statusLabel = (status: EntryStatus) =>
    current
      ? statusLabelFor(current.item.type, itemTypes.data, status)
      : status;
  const setDraft = (change: Partial<CardDraft>) => {
    if (!current || !draft) return;
    setCardDrafts((map) =>
      new Map(map).set(current.id, { ...draft, ...change }),
    );
  };

  const fileMutation = useMutation({
    mutationFn: ({
      entry,
      changes,
    }: {
      entry: LibraryEntry;
      changes: ReturnType<typeof filingChanges>;
    }) => patchEntry(entry.id, changes),
    onSuccess: (_saved, { entry }) => {
      if (listDrafts.current.delete(entry.id))
        saveStatusDrafts(listDrafts.current);
      void queryClient.invalidateQueries({ queryKey: queryKeys.triage.count });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    },
    onError: (_error, { entry }) => {
      // Back into the deck where it was: it comes up next, as it was left.
      setFiled((map) => {
        const next = new Map(map);
        next.delete(entry.id);
        return next;
      });
      setHistory((stack) =>
        stack.filter(
          (action) =>
            !(action.kind === "filed" && action.entry.id === entry.id),
        ),
      );
      toast.error(`“${entry.item.title}” could not be filed`, {
        description: "It is back on top of the deck.",
      });
    },
  });

  const commit = (direction: DeckDirection, fromX = 0) => {
    if (!current || !draft) return;
    setFlipped(false);
    if (direction === "file") {
      const changes = filingChanges(current, draft);
      const request = fileMutation
        .mutateAsync({ entry: current, changes })
        .catch(() => undefined);
      inFlight.current.set(current.id, request);
      setFiled((map) => new Map(map).set(current.id, current));
      setHistory((stack) => [
        ...stack,
        { kind: "filed", entry: current, draft, changes },
      ]);
    } else {
      setPassed((ids) => [
        ...ids.filter((id) => id !== current.id),
        current.id,
      ]);
      setPassedNow((count) => count + 1);
      setHistory((stack) => [
        ...stack,
        { kind: "passed", entry: current, draft },
      ]);
    }
    setCardDrafts((map) => new Map(map).set(current.id, draft));
    if (!presets.reduced) {
      ghostKey.current += 1;
      setGhosts((list) => [
        ...list,
        {
          key: ghostKey.current,
          entry: current,
          direction,
          fromX,
          stamp: direction === "file" ? statusLabel(draft.status) : "Later",
        },
      ]);
    }
  };

  const undo = useCallback(async () => {
    const last = history.at(-1);
    if (!last) return;
    setHistory((stack) => stack.slice(0, -1));
    setFlipped(false);
    if (last.kind === "passed") {
      setPassed((ids) => ids.filter((id) => id !== last.entry.id));
      setPassedNow((count) => Math.max(0, count - 1));
      return;
    }
    setFiled((map) => {
      const next = new Map(map);
      next.delete(last.entry.id);
      return next;
    });
    try {
      await inFlight.current.get(last.entry.id);
      await patchEntry(last.entry.id, undoChanges(last.entry, last.changes));
      void queryClient.invalidateQueries({ queryKey: queryKeys.triage.count });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    } catch {
      toast.error(`“${last.entry.item.title}” could not be put back`, {
        description: "It may already be filed; check it in the library.",
      });
    }
  }, [history, queryClient]);

  const goRoundAgain = () => {
    setPassed([]);
    setPassedNow(0);
  };

  // Keyboard: the domain's status keys, digits for score, arrows to decide.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || isTypingTarget(event.target)) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const onControl =
        event.target instanceof HTMLElement &&
        event.target.closest("button, a") !== null;
      if (event.key === "ArrowRight") {
        event.preventDefault();
        commit("file");
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        commit("later");
        return;
      }
      // On a focused button Enter and Space are that button's own.
      if (!onControl && event.key === "Enter") {
        event.preventDefault();
        commit("file");
        return;
      }
      if (!onControl && event.key === " ") {
        event.preventDefault();
        commit("later");
        return;
      }
      if (event.key === "Backspace") {
        event.preventDefault();
        void undo();
        return;
      }
      if (!current || !draft) return;
      if (event.key === "i") {
        event.preventDefault();
        setFlipped((value) => !value);
        return;
      }
      const status = hotkeysFor(current.item.type, itemTypes.data)[
        event.key.toLowerCase()
      ];
      if (status && status !== "unsorted") {
        event.preventDefault();
        setDraft({ status });
        return;
      }
      if (/^[0-9]$/.test(event.key)) {
        event.preventDefault();
        setDraft({
          score: event.key === "0" ? 10 : Number(event.key),
          scoreTouched: true,
        });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // A new card is always shown face up.
  useEffect(() => setFlipped(false), [current?.id]);

  const close = () =>
    navigate({ pathname: "/inbox", search: searchParams.toString() });

  const statuses = current
    ? statusesFor(current.item.type, itemTypes.data).filter(
        (status) => status.choosable,
      )
    : [];
  const filedEntries = Array.from(filed.values());

  return (
    <DialogPrimitive.Root
      open
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content
          aria-describedby={undefined}
          onOpenAutoFocus={(event) => event.preventDefault()}
          className="fixed inset-0 z-50 flex h-[100dvh] flex-col overflow-hidden bg-background text-foreground focus:outline-none"
        >
          {/* Top bar: leave, how far along, undo. */}
          <header className="flex shrink-0 items-center gap-3 px-3 pt-[max(0.5rem,env(safe-area-inset-top))] sm:px-6 sm:pt-4">
            <DialogPrimitive.Close
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-accent hover:text-foreground focus-ring"
              aria-label="Back to the inbox"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </DialogPrimitive.Close>
            <div className="min-w-0 flex-1">
              <DialogPrimitive.Title className="flex items-baseline gap-2 text-xs font-semibold uppercase tracking-[0.3em] text-primary-text">
                Inbox
                <span className="font-sans text-xs normal-case tracking-normal text-muted-foreground">
                  {library.data ? (
                    <span data-testid="deck-left">
                      {left === 1 ? "1 left" : `${left} left`}
                    </span>
                  ) : null}
                  {filed.size > 0 && (
                    <>
                      {" · "}
                      <m.span
                        key={filed.size}
                        className="inline-block tabular-nums text-foreground"
                        initial={presets.commitPop.from}
                        animate={presets.commitPop.to}
                      >
                        {filed.size} filed
                      </m.span>
                    </>
                  )}
                </span>
              </DialogPrimitive.Title>
              <div
                className="mt-2 h-1 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-label="Progress through the inbox"
                aria-valuemin={0}
                aria-valuemax={done + left}
                aria-valuenow={done}
              >
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300"
                  style={{
                    width: `${done + left ? (done / (done + left)) * 100 : 0}%`,
                  }}
                />
              </div>
            </div>
            <Button
              variant="ghost"
              className="h-11 shrink-0 gap-2 rounded-full px-3"
              disabled={history.length === 0}
              onClick={() => void undo()}
            >
              <Undo2 className="h-4 w-4" aria-hidden="true" />
              Undo
            </Button>
          </header>

          {library.isPending && (
            <Loading label="Shuffling the inbox…" className="m-auto" />
          )}
          {library.isError && (
            <div className="m-auto px-6 text-center" role="alert">
              <p className="font-display text-2xl">
                The inbox could not be loaded
              </p>
              <Button
                className="mt-5 rounded-full px-5"
                onClick={() => void library.refetch()}
              >
                Try again
              </Button>
            </div>
          )}

          {library.data && !current && !library.hasNextPage && (
            <DeckEnd
              filed={filedEntries}
              passedNow={passedNow}
              waitingPassed={waitingPassed}
              onRoundAgain={goRoundAgain}
              onClose={close}
            />
          )}
          {library.data && !current && library.hasNextPage && (
            <Loading label="Fetching more cards…" className="m-auto" />
          )}

          {current && draft && (
            <div className="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col gap-2.5 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 md:grid md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] md:gap-12 md:px-10 md:pb-10 md:pt-8">
              {/* The stack: the card, and the next two standing behind it. */}
              <div className="flex min-h-0 flex-1 items-center justify-center md:h-full">
                <div className="relative aspect-[2/3] h-full max-h-full max-w-full">
                  {queue[2] && <WaitingCard entry={queue[2]} depth={2} />}
                  {queue[1] && <WaitingCard entry={queue[1]} depth={1} />}
                  <m.div
                    key={current.id}
                    className="absolute inset-0"
                    initial={
                      presets.reduced
                        ? false
                        : { scale: 0.95, y: 14, opacity: 0.8 }
                    }
                    animate={{
                      scale: 1,
                      y: 0,
                      opacity: 1,
                      transition: presets.reduced
                        ? { duration: 0 }
                        : { type: "spring", stiffness: 420, damping: 30 },
                    }}
                  >
                    <DeckCard
                      entry={current}
                      types={itemTypes.data}
                      stampLabel={statusLabel(draft.status)}
                      flipped={flipped}
                      onFlip={() => setFlipped((value) => !value)}
                      onSwipe={commit}
                    />
                  </m.div>
                  {ghosts.map((ghost) => (
                    <DepartingCard
                      key={ghost.key}
                      entry={ghost.entry}
                      direction={ghost.direction}
                      fromX={ghost.fromX}
                      stamp={ghost.stamp}
                      onDone={() =>
                        setGhosts((list) =>
                          list.filter((other) => other.key !== ghost.key),
                        )
                      }
                    />
                  ))}
                </div>
              </div>

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
                                  ? draft.shelfIds.filter(
                                      (id) => id !== shelf.id,
                                    )
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
                    aria-label={`File as ${statusLabel(draft.status)}`}
                  >
                    <span className="truncate">
                      File as {statusLabel(draft.status)}
                    </span>
                    <ArrowRight
                      className="h-4 w-4 shrink-0"
                      aria-hidden="true"
                    />
                  </Button>
                </div>
                <p className="hidden text-xs text-muted-foreground md:block">
                  <kbd>→</kbd> file · <kbd>←</kbd> later · <kbd>1</kbd>–
                  <kbd>0</kbd> score · <kbd>i</kbd> turn over ·{" "}
                  <kbd>Backspace</kbd> undo · <kbd>Esc</kbd> leave. On a phone,
                  swipe the card.
                </p>
              </section>
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** Long titles step down, so the whole of one fits where a short one is set large. */
function titleSize(title: string) {
  if (title.length <= 40) return "text-3xl md:text-5xl";
  if (title.length <= 80) return "text-2xl md:text-4xl";
  return "text-xl md:text-3xl";
}

/** The end of a round: what happened, and what is left for later. */
function DeckEnd({
  filed,
  passedNow,
  waitingPassed,
  onRoundAgain,
  onClose,
}: {
  filed: LibraryEntry[];
  passedNow: number;
  waitingPassed: number;
  onRoundAgain: () => void;
  onClose: () => void;
}) {
  const fan = filed.slice(-5);
  const clear = waitingPassed === 0;
  return (
    <section
      className="m-auto flex w-full max-w-lg flex-col items-center px-6 py-8 text-center"
      aria-label="End of the deck"
    >
      {fan.length > 0 && (
        <div className="relative mb-10 h-44 w-full" aria-hidden="true">
          {fan.map((entry, index) => {
            const offset = index - (fan.length - 1) / 2;
            return (
              <div
                key={entry.id}
                className="absolute left-1/2 top-0 h-40 w-[6.75rem] overflow-hidden rounded-lg shadow-xl ring-1 ring-border"
                style={{
                  transform: `translateX(calc(-50% + ${offset * 44}px)) translateY(${Math.abs(offset) * 8}px) rotate(${offset * 7}deg)`,
                }}
              >
                {entry.item.cover_url ? (
                  <CoverImage
                    src={entry.item.cover_url}
                    alt=""
                    className="h-full w-full rounded-lg"
                  />
                ) : (
                  <TypesetCover title={entry.item.title} seed={entry.id} />
                )}
              </div>
            );
          })}
        </div>
      )}
      <h2 className="font-display text-4xl font-medium tracking-tight sm:text-5xl">
        {clear ? "Inbox clear" : "That’s the deck"}
      </h2>
      <p className="mt-3 text-muted-foreground">
        {filed.length === 0
          ? "Nothing filed this time."
          : `${filed.length} filed`}
        {passedNow > 0 && ` · ${passedNow} left for later`}
        {clear && filed.length > 0 ? ". Every one has a place." : "."}
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {!clear && (
          <Button className="rounded-full px-5" onClick={onRoundAgain}>
            Go through the {waitingPassed} you passed
          </Button>
        )}
        <Button
          variant={clear ? "default" : "secondary"}
          className="rounded-full px-5"
          onClick={onClose}
        >
          Back to the inbox
        </Button>
      </div>
    </section>
  );
}
