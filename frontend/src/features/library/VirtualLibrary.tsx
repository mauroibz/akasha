import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { CoverImage } from "@/components/CoverImage";
import { ScorePicker } from "@/components/ScorePicker";
import { StatusSelect } from "@/components/StatusSelect";
import type { LibraryEntry } from "@/api/library";
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
  stretch,
}: Pick<VirtualLibraryProps, "onScore" | "onStatus"> & {
  entry: LibraryEntry;
  stretch?: boolean;
}) {
  return (
    <div
      className="flex h-11 shrink-0 items-center gap-2"
      data-card-controls=""
      onClick={(e) => e.stopPropagation()}
    >
      <StatusSelect
        value={entry.status}
        onValueChange={(status) => onStatus(entry, status)}
        label={`Status for ${entry.item.title}`}
        // In a card the select absorbs the free width so it can never push the
        // score control past the card edge.
        className={stretch ? "h-9 min-w-0 flex-1" : "h-9 w-auto"}
      />
      <ScorePicker
        value={entry.score}
        provisional={entry.score_provisional}
        onChange={(score) => {
          if (score !== null) onScore(entry, score);
        }}
        label={`Score for ${entry.item.title}`}
        compact
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
  return (
    <div className="min-w-0 flex-1" data-card-meta="">
      <h2
        className={`font-semibold leading-snug ${grid ? "line-clamp-3" : "truncate"}`}
      >
        {entry.item.title}
      </h2>
      <p
        className={`text-sm text-muted-foreground ${grid ? "mt-1 line-clamp-2" : "truncate"}`}
      >
        {entry.item.sort_author ?? "Unknown author"}
      </p>
      {/* A grid card is 260px wide and gives its metadata column 88px once the
          fixed cover and the padding are subtracted, so "Edition year: 2015 ·
          Original: 1963" could only ever render as "Edition year: 201…". The
          card box is pinned (DEC-023) and the cover cannot shrink, so the text
          shortens and wraps instead: the label survives for screen readers,
          where it costs no pixels, and the years are what a reader needs. */}
      <p className={`text-xs text-muted-foreground/80 ${grid ? "mt-1" : ""}`}>
        <span className="sr-only">Edition year: </span>
        {entry.item.year ?? "unknown"}
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
    </div>
  );
}

export function VirtualLibrary(props: VirtualLibraryProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const isGrid = props.view !== "table";
  const [containerWidth, setContainerWidth] = useState(0);

  useLayoutEffect(() => {
    const element = parentRef.current;
    if (!element) return;
    const measure = () => setContainerWidth(element.clientWidth);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const columns = isGrid ? gridColumnCount(containerWidth) : 1;
  const rowHeight = isGrid ? gridRowHeight : tableRowHeight;
  const rowCount = Math.ceil(props.entries.length / columns);
  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    // A grid row mounts `columns` cards, so it uses a smaller overscan to keep
    // the mounted-DOM budget comparable to the table.
    overscan: isGrid ? 2 : 4,
    getItemKey: (index) => props.entries[index * columns]?.id ?? index,
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
            ? `flex h-full flex-col gap-3 overflow-hidden rounded-2xl bg-surface/60 p-4 ${focusRing} ${ring}`
            : `flex h-full w-full items-center gap-4 border-b border-border px-4 ${focusRing} ${ring}`
        }
        data-entry-id={entry.id}
        data-provisional={entry.score_provisional ? "true" : "false"}
        data-highlighted={isHighlighted ? "true" : "false"}
        data-rollback={isRolledBack ? "true" : "false"}
        key={entry.id}
        onFocus={() => props.onFocusEntry(entry.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void navigate(`/books/${entry.id}`);
          }
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
        <button
          type="button"
          className={`flex min-w-0 flex-1 gap-4 overflow-hidden text-left focus-visible:outline-none ${
            isGrid ? "items-start" : "items-center"
          }`}
          aria-label={`Open ${entry.item.title}`}
          onClick={() => void navigate(`/books/${entry.id}`)}
        >
          <div className="shrink-0" data-card-cover="">
            <CoverImage
              src={entry.item.cover_url}
              alt={`Cover of ${entry.item.title}`}
              className={isGrid ? "h-48 w-32 rounded-xl" : "h-14 w-10"}
            />
          </div>
          <EntryMetadata entry={entry} grid={isGrid} />
        </button>
        <EntryControls
          entry={entry}
          onScore={props.onScore}
          onStatus={props.onStatus}
          stretch={isGrid}
        />
      </article>
    );
  };

  return (
    <div
      ref={parentRef}
      className="library-scroll mt-5 h-[min(70vh,760px)] overflow-y-auto overflow-x-hidden rounded-2xl bg-surface/40"
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
                transform: `translateY(${row.start}px)`,
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
          Loading more books
        </p>
      )}
    </div>
  );
}
