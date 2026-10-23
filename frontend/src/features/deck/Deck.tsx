import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { m } from "motion/react";
import { toast } from "sonner";
import { Undo2, X } from "lucide-react";

import type { LibraryEntry } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/ui/skeleton";
import {
  DeckCard,
  DepartingCard,
  WaitingCard,
  type DeckDirection,
} from "@/features/triage/DeckCard";
import { useItemTypes } from "@/features/library/useItemTypes";
import { TypesetCover } from "@/features/shelves/OpeningCover";
import { useMotionPresets } from "@/lib/motion";

/** Where a chore's cards come from: a loaded queue that may have more behind it. */
export interface DeckSource<Card> {
  cards: readonly Card[];
  /** Every card the chore has, loaded or not. */
  total: number;
  isPending: boolean;
  isError: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
  refetch: () => void;
}

/** What the controls beside a card can do. */
export interface DeckControls<Draft> {
  draft: Draft;
  setDraft: (change: Partial<Draft>) => void;
  /**
   * Decide the card: `file` is the chore's own answer, `later` passes it. A change
   * applies to the draft first, so a second answer ("Let go") is one tap.
   */
  commit: (direction: DeckDirection, change?: Partial<Draft>) => void;
}

/** One decided card, as the end of the round lists it. */
export interface Decided<Card, Draft> {
  card: Card;
  draft: Draft;
}

/**
 * A chore done one card at a time (Sprint 112, DEC-176), generalized from the inbox's
 * deck (Sprint 106, DEC-170): the layer, the stack, the swipe, the keys, undo, the
 * passes and the end of a round are the deck's; the cards, the controls beside them,
 * and what *File* writes are the chore's.
 *
 * *Later* never writes. *File* calls the chore's `file` at once and moves on, so a
 * fast hand is never made to wait; *Undo* waits for that request before calling
 * `unfile`. A failed filing puts the card back on top.
 */
export function Deck<Card, Draft>({
  label,
  progressLabel,
  closeLabel,
  onClose,
  source,
  loadingLabel,
  errorTitle,
  keyOf,
  entryOf,
  passedStorageKey,
  initialDraft,
  canUndo,
  canFile,
  stamp,
  file,
  unfile,
  renderControls,
  onKey,
  renderEnd,
  cardFace,
  filedNoun = "filed",
  failure,
}: {
  /** The eyebrow over the progress bar: "Inbox", "Still want this?". */
  label: string;
  progressLabel: string;
  closeLabel: string;
  onClose: () => void;
  source: DeckSource<Card>;
  loadingLabel: string;
  errorTitle: string;
  keyOf: (card: Card) => number;
  /** The entry whose cover and back the card shows. */
  entryOf: (card: Card) => LibraryEntry;
  /** Session storage for passes, so a reload keeps them at the back. */
  passedStorageKey?: string;
  initialDraft: (card: Card) => Draft;
  /** Whether a filed card can be taken back; a merge cannot. Defaults to yes. */
  canUndo?: (card: Card, draft: Draft) => boolean;
  /** Whether *File* has anything to write; when not, a swipe right passes instead. */
  canFile?: (card: Card, draft: Draft) => boolean;
  /** What *File* would do, stamped on the card as it leans right. */
  stamp: (card: Card, draft: Draft) => string;
  file: (card: Card, draft: Draft) => Promise<unknown>;
  unfile: (card: Card, draft: Draft) => Promise<unknown>;
  renderControls: (card: Card, controls: DeckControls<Draft>) => ReactNode;
  /** A chore's own keys; answer `true` when one was handled. */
  onKey?: (
    event: KeyboardEvent,
    card: Card,
    controls: DeckControls<Draft>,
  ) => boolean;
  renderEnd: (end: {
    filed: Array<Decided<Card, Draft>>;
    passedNow: number;
    waitingPassed: number;
    roundAgain: () => void;
    close: () => void;
  }) => ReactNode;
  /** A front other than the entry's cover, such as two covers side by side. */
  cardFace?: (card: Card) => ReactNode;
  /** "filed", "kept": how the count in the top bar names a decided card. */
  filedNoun?: string;
  /** What a failed filing says, when "could not be filed" is not the chore's word. */
  failure?: string;
}) {
  const presets = useMotionPresets();
  const itemTypes = useItemTypes();
  const [filed, setFiled] = useState<Map<number, Decided<Card, Draft>>>(
    new Map(),
  );
  const [passed, setPassed] = useState<number[]>(() =>
    passedStorageKey ? loadIds(passedStorageKey) : [],
  );
  const [passedNow, setPassedNow] = useState(0);
  const [history, setHistory] = useState<
    Array<{ kind: "filed" | "passed"; card: Card; draft: Draft }>
  >([]);
  const [drafts, setDrafts] = useState<Map<number, Draft>>(new Map());
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
  const inFlight = useRef(new Map<number, Promise<unknown>>());

  useEffect(() => {
    if (passedStorageKey) saveIds(passedStorageKey, passed);
  }, [passed, passedStorageKey]);

  const passedIds = useMemo(() => new Set(passed), [passed]);
  const queue = useMemo(
    () =>
      source.cards.filter(
        (card) => !filed.has(keyOf(card)) && !passedIds.has(keyOf(card)),
      ),
    [source.cards, filed, passedIds, keyOf],
  );
  const current = queue[0];
  const unloaded = source.hasNextPage
    ? Math.max(0, source.total - source.cards.length)
    : 0;
  const left = queue.length + unloaded;
  const waitingPassed = source.cards.filter(
    (card) => passedIds.has(keyOf(card)) && !filed.has(keyOf(card)),
  ).length;
  const done = filed.size + passedNow;

  // Keep a few cards ahead loaded.
  useEffect(() => {
    if (queue.length < 5 && source.hasNextPage && !source.isFetchingNextPage)
      source.fetchNextPage();
  }, [queue.length, source]);

  const draft = current
    ? (drafts.get(keyOf(current)) ?? initialDraft(current))
    : null;
  const setDraft = (change: Partial<Draft>) => {
    if (!current || !draft) return;
    setDrafts((map) =>
      new Map(map).set(keyOf(current), { ...draft, ...change }),
    );
  };

  const forget = (card: Card) => {
    setFiled((map) => {
      const next = new Map(map);
      next.delete(keyOf(card));
      return next;
    });
  };

  const commit = (
    direction: DeckDirection,
    fromX = 0,
    change?: Partial<Draft>,
  ) => {
    if (!current || !draft) return;
    const card = current;
    const decided = change ? { ...draft, ...change } : draft;
    if (direction === "file" && canFile && !canFile(card, decided))
      direction = "later";
    const key = keyOf(card);
    setFlipped(false);
    if (direction === "file") {
      const request = file(card, decided).catch(() => {
        // Back on top of the deck, as it was left.
        forget(card);
        setHistory((stack) =>
          stack.filter(
            (action) =>
              !(action.kind === "filed" && keyOf(action.card) === key),
          ),
        );
        toast.error(
          failure ?? `“${entryOf(card).item.title}” could not be ${filedNoun}`,
          {
            description: "It is back on top of the deck.",
          },
        );
      });
      inFlight.current.set(key, request);
      setFiled((map) => new Map(map).set(key, { card, draft: decided }));
      setHistory((stack) => [
        ...stack,
        { kind: "filed", card, draft: decided },
      ]);
    } else {
      setPassed((ids) => [...ids.filter((id) => id !== key), key]);
      setPassedNow((count) => count + 1);
      setHistory((stack) => [
        ...stack,
        { kind: "passed", card, draft: decided },
      ]);
    }
    setDrafts((map) => new Map(map).set(key, decided));
    if (!presets.reduced) {
      ghostKey.current += 1;
      setGhosts((list) => [
        ...list,
        {
          key: ghostKey.current,
          entry: entryOf(card),
          direction,
          fromX,
          stamp: direction === "file" ? stamp(card, decided) : "Later",
        },
      ]);
    }
  };

  const last = history.at(-1);
  const undoable =
    last !== undefined &&
    (last.kind === "passed" || !canUndo || canUndo(last.card, last.draft));

  const undo = async () => {
    if (!last || !undoable) return;
    setHistory((stack) => stack.slice(0, -1));
    setFlipped(false);
    const key = keyOf(last.card);
    if (last.kind === "passed") {
      setPassed((ids) => ids.filter((id) => id !== key));
      setPassedNow((count) => Math.max(0, count - 1));
      return;
    }
    forget(last.card);
    try {
      await inFlight.current.get(key);
      await unfile(last.card, last.draft);
    } catch {
      toast.error(`“${entryOf(last.card).item.title}” could not be put back`, {
        description: `It may already be ${filedNoun}; check it in the library.`,
      });
    }
  };

  const roundAgain = () => {
    setPassed([]);
    setPassedNow(0);
  };

  // The deck's keys: arrows to decide, Backspace to undo, i to turn over; then the
  // chore's own.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
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
      if (!current || !controls) return;
      if (event.key === "i") {
        event.preventDefault();
        setFlipped((value) => !value);
        return;
      }
      if (onKey?.(event, current, controls)) event.preventDefault();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const controls: DeckControls<Draft> | null = draft
    ? {
        draft,
        setDraft,
        commit: (direction, change) => commit(direction, 0, change),
      }
    : null;

  // A new card is always shown face up.
  const currentKey = current ? keyOf(current) : null;
  useEffect(() => setFlipped(false), [currentKey]);

  return (
    <DialogPrimitive.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
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
              aria-label={closeLabel}
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </DialogPrimitive.Close>
            <div className="min-w-0 flex-1">
              <DialogPrimitive.Title className="flex items-baseline gap-2 text-xs font-semibold uppercase tracking-[0.3em] text-primary-text">
                {label}
                <span className="font-sans text-xs normal-case tracking-normal text-muted-foreground">
                  {!source.isPending ? (
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
                        {filed.size} {filedNoun}
                      </m.span>
                    </>
                  )}
                </span>
              </DialogPrimitive.Title>
              <div
                className="mt-2 h-1 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-label={progressLabel}
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
              disabled={!undoable}
              onClick={() => void undo()}
            >
              <Undo2 className="h-4 w-4" aria-hidden="true" />
              Undo
            </Button>
          </header>

          {source.isPending && (
            <Loading label={loadingLabel} className="m-auto" />
          )}
          {source.isError && (
            <div className="m-auto px-6 text-center" role="alert">
              <p className="font-display text-2xl">{errorTitle}</p>
              <Button
                className="mt-5 rounded-full px-5"
                onClick={() => source.refetch()}
              >
                Try again
              </Button>
            </div>
          )}

          {!source.isPending &&
            !source.isError &&
            !current &&
            !source.hasNextPage &&
            renderEnd({
              filed: Array.from(filed.values()),
              passedNow,
              waitingPassed,
              roundAgain,
              close: onClose,
            })}
          {!source.isPending && !current && source.hasNextPage && (
            <Loading label="Fetching more cards…" className="m-auto" />
          )}

          {current && controls && (
            <div className="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col gap-2.5 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 md:grid md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] md:gap-12 md:px-10 md:pb-10 md:pt-8">
              {/* The stack: the card, and the next two standing behind it. */}
              <div className="flex min-h-0 flex-1 items-center justify-center md:h-full">
                <div className="relative aspect-[2/3] h-full max-h-full max-w-full">
                  {queue[2] && (
                    <WaitingCard entry={entryOf(queue[2])} depth={2} />
                  )}
                  {queue[1] && (
                    <WaitingCard entry={entryOf(queue[1])} depth={1} />
                  )}
                  <m.div
                    key={keyOf(current)}
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
                      entry={entryOf(current)}
                      types={itemTypes.data}
                      stampLabel={stamp(current, controls.draft)}
                      flipped={flipped}
                      onFlip={() => setFlipped((value) => !value)}
                      onSwipe={commit}
                      face={cardFace?.(current)}
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
              {renderControls(current, controls)}
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** The end of a round: covers fanned, what happened, and the ways on. */
export function DeckEnd({
  entries,
  title,
  summary,
  children,
}: {
  /** The decided cards' entries; the last five are fanned. */
  entries: LibraryEntry[];
  title: string;
  summary: string;
  /** The buttons. */
  children: ReactNode;
}) {
  const fan = entries.slice(-5);
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
        {title}
      </h2>
      <p className="mt-3 text-muted-foreground">{summary}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">{children}</div>
    </section>
  );
}

/** A key the deck answers only when focus is not in a field the owner types into. */
function isTypingTarget(target: EventTarget | null) {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

function loadIds(key: string): number[] {
  try {
    const parsed: unknown = JSON.parse(
      window.sessionStorage.getItem(key) ?? "[]",
    );
    return Array.isArray(parsed)
      ? parsed.filter((id): id is number => Number.isInteger(id))
      : [];
  } catch {
    return [];
  }
}

function saveIds(key: string, ids: number[]) {
  try {
    if (ids.length === 0) window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, JSON.stringify(ids));
  } catch {
    // A deck without storage forgets its passes on reload, nothing more.
  }
}
