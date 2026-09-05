import { useWindowVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { CoverImage } from "@/components/CoverImage";
import { ScorePicker } from "@/components/ScorePicker";
import { StatusSelect } from "@/components/StatusSelect";
import type { LibraryEntry } from "@/api/library";
import { formatLabels, statusesFor } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import {
  gridColumnCount,
  gridLayout,
  gridRowHeight,
  tableRowHeight,
  type LibraryView,
} from "./library";

interface VirtualLibraryProps {
  entries: LibraryEntry[];
  /** Server-side match count, so a feed item can say which of how many it is. */
  total: number;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  focusedId: number | null;
  highlightId?: number | null;
  /** The entry whose write just failed and was rolled back. */
  rollbackId?: number | null;
  loadNextPage: () => void;
  onFocusEntry: (id: number) => void;
  onScore: (entry: LibraryEntry, score: number) => void;
  onStatus: (entry: LibraryEntry, status: LibraryEntry["status"]) => void;
  view: LibraryView;
}

function EntryControls({
  entry,
  onScore,
  onStatus,
  onCover,
}: Pick<VirtualLibraryProps, "onScore" | "onStatus"> & {
  entry: LibraryEntry;
  /** Sprint 072 wall cards: controls ride the cover's bottom scrim (DEC-139). */
  onCover?: boolean;
}) {
  // One cached request for the whole session, shared with every other row.
  const itemTypes = useItemTypes();
  return (
    <div
      data-card-controls=""
      onClick={(e) => e.stopPropagation()}
      className={
        onCover
          ? // Both controls always in the DOM and visible at rest (AC4 is not
            // a hover contract). The opaque backing is the Sprint 071 lesson:
            // colours on artwork blend into it — the translucent buttons need
            // solid ground behind them, not a tint over the poster.
            //
            // `relative` is load-bearing: the score panel anchors to this
            // container (not to its own chip, which sits off-centre) so
            // the panel opens centred above the card — contained at every
            // width (AC9), within DEC-023 without changing the card box.
            "relative flex h-[52px] items-center justify-center gap-2 rounded-full bg-surface p-1 shadow-lg"
          : "flex h-11 shrink-0 items-center gap-2"
      }
    >
      <StatusSelect
        value={entry.status}
        onValueChange={(status) => onStatus(entry, status)}
        label={`Status for ${entry.item.title}`}
        statuses={statusesFor(entry.item.type, itemTypes.data)}
        // Both densities keep the sprint's 44px target at 390px (AC4/AC10).
        className="h-11 w-auto"
      />
      <ScorePicker
        value={entry.score}
        provisional={entry.score_provisional}
        onChange={(score) => {
          if (score !== null) onScore(entry, score);
        }}
        label={`Score for ${entry.item.title}`}
        // Compact so the panel stays a contained overlay (DEC-023); onCover
        // grows the chip to 44px with the larger numeral and centres the panel
        // above it (AC4, AC9).
        compact
        onCover={onCover}
      />
    </div>
  );
}

function EntryMetadata({
  entry,
  grid,
}: {
  entry: LibraryEntry;
  grid: boolean;
}) {
  // Nothing gets pinned width in Sprint 072 — the card is a measureless cover,
  // and everything in it takes the full measure of the card. The title gets
  // two lines at text-sm leading-5 (40px) merged into the textHeight budget;
  // the creator and the year/format lines each fit inside one line.
  if (grid)
    return (
      <div className="grid min-w-0 content-start px-2.5 pt-2" data-card-meta="">
        <h2
          className="overflow-hidden text-sm font-semibold leading-5 [-webkit-line-clamp:2] [display:-webkit-box] [-webkit-box-orient:vertical]"
          title={entry.item.title}
        >
          {entry.item.title}
        </h2>
        <>
          <p
            className="mt-0.5 overflow-hidden text-xs leading-4 text-muted-foreground truncate"
            title={entry.item.creator ?? undefined}
          >
            {entry.item.creator ?? "Unknown creator"}
          </p>
          <p className="mt-0.5 text-xs leading-4 text-muted-foreground">
            <span className="sr-only">Edition year: </span>
            {entry.item.year ?? <span aria-hidden="true">Year unknown</span>}
            {entry.item.year === null || entry.item.year === undefined ? (
              <span className="sr-only">unknown</span>
            ) : null}
            {entry.item.metadata.original_year &&
            entry.item.metadata.original_year !== entry.item.year ? (
              <>
                {" · "}
                <span className="sr-only">originally published </span>
                <span aria-hidden="true">orig. </span>
                {entry.item.metadata.original_year}
              </>
            ) : null}
          </p>
          <FormatBadges entry={entry} />
        </>
      </div>
    );

  // List density is one horizontal reading line, not the wall metadata stacked
  // into a shorter box. Lower-priority columns progressively hide when the
  // viewport cannot hold them; desktop keeps the complete title / creator /
  // year / formats sequence while the card controls retain 44px targets.
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3" data-card-meta="">
      <h2
        className="min-w-0 flex-[2] truncate text-sm font-semibold"
        title={entry.item.title}
      >
        {entry.item.title}
      </h2>
      <p className="hidden min-w-0 flex-[1.5] truncate text-xs text-muted-foreground sm:block">
        {entry.item.creator ?? "Unknown creator"}
      </p>
      <p className="hidden shrink-0 text-xs text-muted-foreground md:block">
        <span className="sr-only">Edition year: </span>
        {entry.item.year ?? <span aria-hidden="true">Year unknown</span>}
        {entry.item.year === null || entry.item.year === undefined ? (
          <span className="sr-only">unknown</span>
        ) : null}
      </p>
      <FormatBadges entry={entry} dense />
    </div>
  );
}

/**
 * How you hold this copy, read straight off the row.
 *
 * "Filter to owned and see how" is one filter plus this: without it the answer is
 * on the detail page, one click per record, which is not an answer to "sort by
 * owned and see where I own it" (DEC-059).
 */
function FormatBadges({
  entry,
  dense = false,
}: {
  entry: LibraryEntry;
  dense?: boolean;
}) {
  const itemTypes = useItemTypes();
  if (!entry.formats?.length) return null;
  const labels = formatLabels(itemTypes.data);
  return (
    <span
      className={
        dense
          ? "hidden shrink-0 flex-nowrap items-center gap-1 empty:hidden lg:inline-flex"
          : "mt-1 inline-flex flex-wrap items-center gap-1 align-[3px] empty:hidden"
      }
      data-card-formats=""
    >
      <span className="sr-only">Formats: </span>
      {entry.formats.map((format) => (
        <span
          key={format}
          className="rounded-full bg-surface-raised px-2 py-0.5 text-[11px] leading-4 text-muted-foreground"
        >
          {labels[format] ?? format}
        </span>
      ))}
    </span>
  );
}

export function VirtualLibrary(props: VirtualLibraryProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const isGrid = props.view !== "table";
  const [containerWidth, setContainerWidth] = useState(0);
  // How far down the document the list starts. The window virtualizer measures
  // the viewport, so it needs to know what sits above the list — the header, the
  // controls, the chips — or every row is placed that far too high.
  const [scrollMargin, setScrollMargin] = useState(0);

  useLayoutEffect(() => {
    const element = parentRef.current;
    if (!element) return;
    const measure = () => {
      setContainerWidth(element.clientWidth);
      // Read against the document rather than the viewport: `offsetTop` walks a
      // chain of offset parents that the motion wrapper can interrupt, and this
      // number has to stay right while the page is scrolled.
      setScrollMargin(element.getBoundingClientRect().top + window.scrollY);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    // The chips and the filter row above the list reflow, which moves the list's
    // start without ever changing its own size — so the body is observed too.
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    observer.observe(document.body);
    return () => observer.disconnect();
  }, []);

  const columns = isGrid ? gridColumnCount(containerWidth) : 1;
  const rowHeight = isGrid ? gridRowHeight : tableRowHeight;
  const rowCount = Math.ceil(props.entries.length / columns);
  const virtualizer = useWindowVirtualizer({
    count: rowCount,
    estimateSize: () => rowHeight,
    // A grid row mounts `columns` cards, so it uses a smaller overscan to keep
    // the mounted-DOM budget comparable to the table.
    // The 52px list density shows fourteen rows at 900px. Two rows of overscan
    // on either side keep scrolling smooth while preserving DEC-023's strict
    // <20 mounted-row budget (four would mount 23 rows at depth).
    overscan: 2,
    getItemKey: (index) => props.entries[index * columns]?.id ?? index,
    scrollMargin,
    initialRect: { width: 1000, height: 640 },
  });
  const virtualItems = virtualizer.getVirtualItems();
  const mountedRows = virtualItems.length
    ? virtualItems
    : Array.from({ length: Math.min(5, rowCount) }, (_, index) => ({
        index,
        key: props.entries[index * columns]?.id ?? index,
        size: rowHeight,
        start: index * rowHeight,
        end: (index + 1) * rowHeight,
        lane: 0,
      }));

  useEffect(() => {
    const last = virtualItems.at(-1);
    if (
      last &&
      last.index >= rowCount - 3 &&
      props.hasNextPage &&
      !props.isFetchingNextPage
    )
      props.loadNextPage();
  }, [props, rowCount, virtualItems]);

  useEffect(() => {
    if (props.focusedId === null) return;
    const active = document.activeElement;
    if (
      active instanceof HTMLElement &&
      active !== document.body &&
      active.isConnected
    )
      return;
    const index = props.entries.findIndex(
      (entry) => entry.id === props.focusedId,
    );
    if (index < 0) return;
    virtualizer.scrollToIndex(Math.floor(index / columns), { align: "auto" });
    window.requestAnimationFrame(() => {
      parentRef.current
        ?.querySelector<HTMLElement>(`[data-entry-id="${props.focusedId}"]`)
        ?.focus();
    });
  }, [columns, props.entries, props.focusedId, virtualizer]);

  const renderEntry = (entry: LibraryEntry, position: number) => {
    const isHighlighted = props.highlightId === entry.id;
    const isRolledBack = props.rollbackId === entry.id;
    // The ring fades rather than vanishing, so the eye is handed back to the
    // list instead of having the marker snatched away. A shadow transition,
    // not a layout one: the card box is pinned by DEC-023.
    // `[transition-duration:...]` rather than `duration-500`: tailwindcss-animate
    // redefines the `duration-*` utilities to set `animation-duration` as well,
    // and later in the cascade, so a card carrying both the ring transition and
    // the shake would run the shake at the ring's duration.
    const ring = `transition-shadow [transition-duration:500ms] ${isHighlighted ? "ring-2 ring-primary" : ""} ${isRolledBack ? "animate-shake" : ""}`;
    const focusRing =
      "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";
    return (
      <article
        aria-label={entry.item.title}
        className={
          isGrid
            ? // Sprint 072: no padding on the wall card — the cover is the
              // card's skin edge-to-edge, and the text block carries its own.
              `relative h-full overflow-hidden rounded-2xl bg-surface/60 ${focusRing} ${ring}`
            : `flex h-full min-h-0 w-full items-center gap-4 border-b border-border px-4 ${focusRing} ${ring}`
        }
        data-entry-id={entry.id}
        data-provisional={entry.score_provisional ? "true" : "false"}
        data-highlighted={isHighlighted ? "true" : "false"}
        data-rollback={isRolledBack ? "true" : "false"}
        key={entry.id}
        onFocus={() => props.onFocusEntry(entry.id)}
        onClick={(e) => {
          if (!isGrid) return;
          // The text block's own button opens the card; this handler is the
          // net for clicks on the card shell itself. Interactive children
          // keep their clicks — EntryControls stops propagation and this
          // guard returns before a button's click could double-navigate.
          if ((e.target as HTMLElement).closest("button, [role='combobox']"))
            return;
          void navigate(`/books/${entry.id}`);
        }}
        onKeyDown={(e) => {
          if (e.key !== "Enter") return;
          // Enter on a control is the control's own action — the chip opens,
          // the pill opens, the Open button opens the page. Only a bare Enter
          // on the card itself (the row crack, reached from `j`/`k`) is the
          // open-shortcut; without this guard one key press is both.
          if ((e.target as HTMLElement).closest("button, [role='combobox']"))
            return;
          e.preventDefault();
          void navigate(`/books/${entry.id}`);
        }}
        // Both views are the same list of entries at two densities, so both
        // are a feed of articles. Table mode used to claim `role="row"` inside
        // `role="table"` with no cells beneath it, which axe reports as a
        // critical `aria-required-children` failure and which gave a screen
        // reader a table it could not navigate (DEC-038).
        aria-posinset={position}
        aria-setsize={props.total}
        tabIndex={0}
      >
        {isGrid ? (
          <>
            {/* Sprint 072 wall card. The cover is the card's skin — edge to
                edge, pinned, cropped — so its wrapper opts out of hit-testing
                entirely: its job is pixels, not clicks. */}
            <div
              className="pointer-events-none absolute inset-x-0 top-0"
              style={{ height: gridLayout.coverHeight }}
              data-card-cover=""
            >
              <CoverImage
                src={entry.item.cover_url}
                alt={`Cover of ${entry.item.title}`}
                className="absolute inset-0 h-full w-full rounded-none"
              />
              {/* The scrim: artwork reads as art because the black gradient
                  sits above it, and it keeps the score chip and status pill
                  legible over any poster, light or dark (DEC-139 risk item). */}
              <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
            </div>
            {/* The text block is the card's open control — a named button exactly
                like the table row's, whose topmost target is the title text
                itself, so a reader who clicks the title hits the title (the
                editorial suite's heading click opens the detail; AC11 leaves
                that suite untouched) and a screen reader gets a real door.
                There is deliberately NO full-card overlay: one above the
                whole surface would intercept exactly that click. */}
            <button
              type="button"
              aria-label={`Open ${entry.item.title}`}
              className="absolute inset-x-0 bottom-0 z-[1] block overflow-hidden rounded-b-2xl bg-surface text-left focus-visible:outline-none"
              style={{ height: gridLayout.textHeight }}
              onClick={() => void navigate(`/books/${entry.id}`)}
            >
              <EntryMetadata entry={entry} grid />
            </button>
            {/* The controls ride the bottom of the cover — the pile sits a
                few pixels up from the poster's edge, on the scrim's opaque
                backing rather than tinted into the artwork itself. z-10 keeps
                it above the text block's button: its 52px footprint sits in
                the cover region, and clicks there must hit the chip, not the
                card. */}
            <div
              className="absolute inset-x-0 z-10 flex justify-center p-1.5"
              style={{ top: gridLayout.coverHeight - 58 }}
            >
              <EntryControls
                entry={entry}
                onScore={props.onScore}
                onStatus={props.onStatus}
                onCover
              />
            </div>
          </>
        ) : (
          <>
            <button
              type="button"
              className="flex min-w-0 flex-1 items-center gap-4 overflow-hidden text-left focus-visible:outline-none"
              aria-label={`Open ${entry.item.title}`}
              onClick={() => void navigate(`/books/${entry.id}`)}
            >
              <div className="shrink-0" data-card-cover="">
                <CoverImage
                  src={entry.item.cover_url}
                  alt={`Cover of ${entry.item.title}`}
                  className="h-12 w-8"
                />
              </div>
              <EntryMetadata entry={entry} grid={false} />
            </button>
            <EntryControls
              entry={entry}
              onScore={props.onScore}
              onStatus={props.onStatus}
            />
          </>
        )}
      </article>
    );
  };

  return (
    <div
      ref={parentRef}
      // No height and no overflow: the page scrolls, not the grid. The owner's
      // report was that the primary surface was a window inside the page, and the
      // fixed height was the whole of it. `overflow-x-hidden` stays, because a
      // wide card must not push the document sideways.
      className="library-scroll mt-4 overflow-x-hidden rounded-2xl bg-surface/40"
      role="feed"
      aria-label="Library"
      aria-busy={props.isFetchingNextPage}
      data-mounted-count={mountedRows.length}
      data-columns={columns}
    >
      <div
        className="relative w-full"
        style={{ height: virtualizer.getTotalSize() }}
      >
        {mountedRows.map((row) => {
          const rowEntries = props.entries.slice(
            row.index * columns,
            row.index * columns + columns,
          );
          return (
            <div
              className={`absolute left-0 top-0 w-full ${isGrid ? "px-4" : ""}`}
              // Addressable so `e2e/library.spec.ts` can assert that no
              // animation is ever registered against a virtual row. The row's
              // position is an inline transform owned by the virtualizer;
              // animating it would fight the thing that places it.
              data-virtual-row=""
              key={row.key}
              style={{
                height: row.size,
                // Positions from the window virtualizer are document-relative, so
                // the list's own offset comes back off to place a row inside it.
                transform: `translateY(${row.start - scrollMargin}px)`,
              }}
            >
              <div
                className="grid"
                style={
                  isGrid
                    ? {
                        gap: gridLayout.gap,
                        gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                        height: gridLayout.cardHeight,
                      }
                    : { height: row.size }
                }
              >
                {rowEntries.map((entry, column) =>
                  // A virtualized feed mounts a window, so without an explicit
                  // position a screen reader announces "article" with no idea
                  // where in ten thousand it sits.
                  renderEntry(entry, row.index * columns + column + 1),
                )}
              </div>
            </div>
          );
        })}
      </div>
      {props.isFetchingNextPage && (
        <p role="status" className="sr-only">
          Loading more
        </p>
      )}
    </div>
  );
}
