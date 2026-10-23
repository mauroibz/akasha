import { useRef } from "react";
import { Link } from "react-router-dom";
import { RotateCcw } from "lucide-react";
import { animate, m, useMotionValue, useTransform } from "motion/react";

import type { ItemType, LibraryEntry } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { formatLabels, statusLabelFor } from "@/features/library/labels";
import { TypesetCover } from "@/features/shelves/OpeningCover";
import { cn } from "@/lib/utils";

export type DeckDirection = "file" | "later";

/** How far a drag must travel, in px, before letting go files or passes. */
const SWIPE_DISTANCE = 96;
/** A quick flick counts even when it is short, in px per ms. */
const SWIPE_VELOCITY = 0.6;
/** Movement under this is a tap, which turns the card over. */
const TAP_SLOP = 8;

/**
 * One card of the deck (DEC-170): the cover large, and behind it — a tap turns
 * the card over — what the front has no room for.
 *
 * The swipe is hand-rolled on pointer events rather than Motion's `drag`: the
 * shell loads `domAnimation`, which leaves drag out on purpose (see AppShell),
 * and a horizontal pointer track with a spring back is all this needs. Motion
 * values still carry the lean and the stamps, so they never re-render React.
 */
export function DeckCard({
  entry,
  types,
  stampLabel,
  flipped,
  onFlip,
  onSwipe,
  face,
}: {
  entry: LibraryEntry;
  types: ItemType[] | undefined;
  /** A front other than the entry's cover (Sprint 112): two covers side by side. */
  face?: React.ReactNode;
  /** What *File* would set, stamped on the card as it leans right. */
  stampLabel: string;
  flipped: boolean;
  onFlip: () => void;
  /** Decided by a swipe; `fromX` is where the card was let go. */
  onSwipe: (direction: DeckDirection, fromX: number) => void;
}) {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-260, 0, 260], [-14, 0, 14]);
  const fileStamp = useTransform(x, [16, SWIPE_DISTANCE], [0, 1]);
  const laterStamp = useTransform(x, [-SWIPE_DISTANCE, -16], [1, 0]);
  const drag = useRef<{
    id: number;
    startX: number;
    startY: number;
    time: number;
    moved: boolean;
  } | null>(null);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    // `Element`, not `HTMLElement`: a press on the turn-over button often lands
    // on its SVG icon, and an SVG node is not an HTMLElement.
    if (event.target instanceof Element && event.target.closest("a, button"))
      return;
    drag.current = {
      id: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      time: event.timeStamp,
      moved: false,
    };
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const current = drag.current;
    if (!current || current.id !== event.pointerId) return;
    const dx = event.clientX - current.startX;
    const dy = event.clientY - current.startY;
    if (!current.moved) {
      if (Math.abs(dx) < TAP_SLOP && Math.abs(dy) < TAP_SLOP) return;
      // A mostly vertical start is not a swipe; let it go.
      if (Math.abs(dy) > Math.abs(dx)) {
        drag.current = null;
        return;
      }
      current.moved = true;
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    x.set(dx);
  };

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    const current = drag.current;
    drag.current = null;
    if (!current || current.id !== event.pointerId) return;
    if (!current.moved) {
      onFlip();
      return;
    }
    const dx = event.clientX - current.startX;
    const velocity = dx / Math.max(1, event.timeStamp - current.time);
    if (dx > SWIPE_DISTANCE || velocity > SWIPE_VELOCITY) onSwipe("file", dx);
    else if (dx < -SWIPE_DISTANCE || velocity < -SWIPE_VELOCITY)
      onSwipe("later", dx);
    else
      void animate(x, 0, {
        type: "spring",
        stiffness: 480,
        damping: 32,
      });
  };

  const onPointerCancel = () => {
    drag.current = null;
    void animate(x, 0, { duration: 0.2 });
  };

  const formats = formatLabels(types);
  const suggestion = entry.suggested_status
    ? statusLabelFor(entry.item.type, types, entry.suggested_status)
    : null;

  return (
    <m.div
      data-deck-card={entry.id}
      style={{ x, rotate, touchAction: "pan-y" }}
      className="relative h-full w-full cursor-grab select-none active:cursor-grabbing"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
    >
      <div className="h-full w-full [perspective:1400px]">
        <div
          className={cn(
            "relative h-full w-full transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] [transform-style:preserve-3d] motion-reduce:transition-none",
            flipped && "[transform:rotateY(180deg)]",
          )}
        >
          {/* Front: the cover, as large as the screen allows. */}
          <div
            aria-hidden={flipped}
            className="absolute inset-0 overflow-hidden rounded-2xl bg-surface-raised shadow-2xl ring-1 ring-border [backface-visibility:hidden]"
          >
            {face ? (
              face
            ) : entry.item.cover_url ? (
              <CoverImage
                src={entry.item.cover_url}
                alt={`Cover of ${entry.item.title}`}
                className="h-full w-full rounded-2xl [&_img]:pointer-events-none"
              />
            ) : (
              <span className="block h-full w-full [&_span]:text-[26px]">
                <TypesetCover title={entry.item.title} seed={entry.id} />
              </span>
            )}
            <Stamp
              style={{ opacity: fileStamp }}
              className="left-4 top-5 -rotate-12 border-score-top text-score-top"
            >
              {stampLabel}
            </Stamp>
            <Stamp
              style={{ opacity: laterStamp }}
              className="right-4 top-5 rotate-12 border-primary text-primary"
            >
              Later
            </Stamp>
          </div>
          {/* Back: the details the front has no room for. */}
          <div
            aria-hidden={!flipped}
            className="absolute inset-0 flex flex-col overflow-y-auto rounded-2xl bg-surface-raised p-4 shadow-2xl sm:p-6 ring-1 ring-border [backface-visibility:hidden] [transform:rotateY(180deg)]"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary-text">
              The back
            </p>
            <p className="mt-2 font-display text-lg font-medium leading-tight sm:mt-3 sm:text-2xl">
              {entry.item.title}
            </p>
            {entry.item.subtitle && (
              <p className="mt-1 font-display text-base italic text-muted-foreground sm:text-lg">
                {entry.item.subtitle}
              </p>
            )}
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs sm:mt-5 sm:gap-x-4 sm:gap-y-2 sm:text-sm">
              <dt className="text-muted-foreground">By</dt>
              <dd>{entry.item.creator ?? "Unknown"}</dd>
              {entry.item.year !== null && (
                <>
                  <dt className="text-muted-foreground">Year</dt>
                  <dd className="tabular-nums">{entry.item.year}</dd>
                </>
              )}
              {suggestion && (
                <>
                  <dt className="text-muted-foreground">Import says</dt>
                  <dd>{suggestion}</dd>
                </>
              )}
              {entry.score !== null && (
                <>
                  <dt className="text-muted-foreground">Score</dt>
                  <dd className="tabular-nums">
                    {entry.score}
                    {entry.score_provisional ? " (from the import)" : ""}
                  </dd>
                </>
              )}
              {entry.formats.length > 0 && (
                <>
                  <dt className="text-muted-foreground">Formats</dt>
                  <dd>
                    {entry.formats
                      .map((format) => formats[format] ?? format)
                      .join(", ")}
                  </dd>
                </>
              )}
              <dt className="text-muted-foreground">Added</dt>
              <dd className="tabular-nums">{entry.date_added.slice(0, 10)}</dd>
            </dl>
            <Link
              to={`/books/${entry.id}`}
              state={{ from: "triage" }}
              tabIndex={flipped ? 0 : -1}
              className="mt-auto pb-10 pt-4 text-xs font-medium sm:pb-0 sm:text-sm text-primary-text underline-offset-4 hover:underline focus-ring"
            >
              Open the full page →
            </Link>
          </div>
        </div>
      </div>
      <button
        type="button"
        onClick={onFlip}
        className="absolute bottom-3 right-3 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-background/80 text-foreground shadow ring-1 ring-border backdrop-blur focus-ring"
        aria-label={flipped ? "Turn to the cover" : "Turn over for details"}
        aria-pressed={flipped}
      >
        <RotateCcw className="h-4 w-4" aria-hidden="true" />
      </button>
    </m.div>
  );
}

function Stamp({
  className,
  style,
  children,
}: {
  className: string;
  style: React.ComponentProps<typeof m.span>["style"];
  children: React.ReactNode;
}) {
  return (
    <m.span
      aria-hidden="true"
      style={style}
      className={cn(
        "pointer-events-none absolute rounded-lg border-4 bg-background/70 px-3 py-1 font-display text-3xl font-semibold uppercase tracking-wide opacity-0 backdrop-blur-sm",
        className,
      )}
    >
      {children}
    </m.span>
  );
}

/**
 * A decided card on its way off the table: a copy, so the deck behind it is
 * already live. It leaves from where the hand let go, leaning, stamped.
 */
export function DepartingCard({
  entry,
  direction,
  fromX,
  stamp,
  onDone,
}: {
  entry: LibraryEntry;
  direction: DeckDirection;
  fromX: number;
  stamp: string;
  onDone: () => void;
}) {
  const sign = direction === "file" ? 1 : -1;
  return (
    <m.div
      aria-hidden="true"
      data-departing=""
      className="pointer-events-none absolute inset-0 z-20 overflow-hidden rounded-2xl bg-surface-raised shadow-2xl ring-1 ring-border"
      initial={{ x: fromX, rotate: (fromX / 260) * 14, opacity: 1 }}
      animate={{
        x: sign * (window.innerWidth * 0.75 + 240),
        rotate: sign * 22,
        opacity: 0.4,
        transition: { duration: 0.32, ease: [0.4, 0, 0.9, 0.6] },
      }}
      onAnimationComplete={onDone}
    >
      {entry.item.cover_url ? (
        <CoverImage
          src={entry.item.cover_url}
          alt=""
          className="h-full w-full rounded-2xl"
        />
      ) : (
        <span className="block h-full w-full [&_span]:text-[26px]">
          <TypesetCover title={entry.item.title} seed={entry.id} />
        </span>
      )}
      <span
        className={cn(
          "absolute top-5 rounded-lg border-4 bg-background/70 px-3 py-1 font-display text-3xl font-semibold uppercase tracking-wide backdrop-blur-sm",
          direction === "file"
            ? "left-4 -rotate-12 border-score-top text-score-top"
            : "right-4 rotate-12 border-primary text-primary",
        )}
      >
        {stamp}
      </span>
    </m.div>
  );
}

/** A card waiting behind the current one: its cover only, smaller and lower. */
export function WaitingCard({
  entry,
  depth,
}: {
  entry: LibraryEntry;
  depth: 1 | 2;
}) {
  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 overflow-hidden rounded-2xl bg-surface-raised shadow-xl ring-1 ring-border transition-transform duration-300"
      style={{
        transform: `translateY(${depth * 14}px) scale(${1 - depth * 0.05})`,
        opacity: 1 - depth * 0.25,
      }}
    >
      {entry.item.cover_url ? (
        <CoverImage
          src={entry.item.cover_url}
          alt=""
          className="h-full w-full rounded-2xl"
        />
      ) : (
        <TypesetCover title={entry.item.title} seed={entry.id} />
      )}
    </div>
  );
}
