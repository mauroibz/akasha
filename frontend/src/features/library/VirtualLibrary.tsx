import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { CoverImage } from "@/components/CoverImage";
import { ScorePicker } from "@/components/ScorePicker";
import type { LibraryEntry } from "@/api/library";
import type { LibraryView } from "./library";

interface VirtualLibraryProps {
  entries: LibraryEntry[];
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  focusedId: number | null;
  highlightId?: number | null;
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
}: Pick<VirtualLibraryProps, "onScore" | "onStatus"> & {
  entry: LibraryEntry;
}) {
  return (
    <div
      className="flex items-center gap-2"
      data-card-controls=""
      onClick={(e) => e.stopPropagation()}
    >
      <label className="sr-only" htmlFor={`status-${entry.id}`}>
        Status for {entry.item.title}
      </label>
      <select
        id={`status-${entry.id}`}
        className="min-h-11 rounded-lg bg-zinc-800 px-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-fuchsia-400"
        value={entry.status}
        onChange={(event) =>
          onStatus(entry, event.target.value as LibraryEntry["status"])
        }
      >
        <option value="read">Read</option>
        <option value="reading">Reading</option>
        <option value="to_read">To read</option>
        <option value="wishlist">Wishlist</option>
        <option value="dropped">Dropped</option>
        <option value="unsorted">Inbox</option>
      </select>
      <label className="sr-only" htmlFor={`score-${entry.id}`}>
        Score for {entry.item.title}
      </label>
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

export function VirtualLibrary(props: VirtualLibraryProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const rowHeight = props.view === "table" ? 84 : 310;
  const virtualizer = useVirtualizer({
    count: props.entries.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 4,
    getItemKey: (index) => props.entries[index]?.id ?? index,
    initialRect: { width: 1000, height: 640 },
  });
  const virtualItems = virtualizer.getVirtualItems();
  const mountedItems = virtualItems.length
    ? virtualItems
    : props.entries.slice(0, 5).map((entry, index) => ({
        index,
        key: entry.id,
        size: rowHeight,
        start: index * rowHeight,
        end: (index + 1) * rowHeight,
        lane: 0,
      }));

  useEffect(() => {
    const last = virtualItems.at(-1);
    if (
      last &&
      last.index >= props.entries.length - 3 &&
      props.hasNextPage &&
      !props.isFetchingNextPage
    )
      props.loadNextPage();
  }, [props, virtualItems]);

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
    virtualizer.scrollToIndex(index, { align: "auto" });
    window.requestAnimationFrame(() => {
      parentRef.current
        ?.querySelector<HTMLElement>(`[data-entry-id="${props.focusedId}"]`)
        ?.focus();
    });
  }, [props.entries, props.focusedId, virtualizer]);

  return (
    <div
      ref={parentRef}
      className="library-scroll mt-5 h-[min(70vh,760px)] overflow-auto rounded-2xl bg-zinc-900/40"
      role={props.view === "table" ? "table" : "feed"}
      aria-label="Library"
      data-mounted-count={mountedItems.length}
    >
      <div
        className="relative w-full"
        style={{ height: virtualizer.getTotalSize() }}
      >
        {mountedItems.map((row) => {
          const entry = props.entries[row.index];
          const isHighlighted = props.highlightId === entry.id;
          return (
            <article
              aria-label={entry.item.title}
              className={
                props.view === "table"
                  ? `absolute left-0 top-0 flex w-full items-center gap-4 border-b border-zinc-800 px-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fuchsia-400 ${isHighlighted ? "ring-2 ring-fuchsia-400" : ""}`
                  : `absolute left-0 top-0 grid w-full grid-cols-[128px_1fr] gap-5 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fuchsia-400 ${isHighlighted ? "ring-2 ring-fuchsia-400" : ""}`
              }
              data-entry-id={entry.id}
              data-provisional={entry.score_provisional ? "true" : "false"}
              data-highlighted={isHighlighted ? "true" : "false"}
              key={entry.id}
              onFocus={() => props.onFocusEntry(entry.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void navigate(`/books/${entry.id}`);
                }
              }}
              role={props.view === "table" ? "row" : undefined}
              style={{
                height: row.size,
                transform: `translateY(${row.start}px)`,
              }}
              tabIndex={0}
            >
              <button
                type="button"
                className="flex min-w-0 flex-1 items-center gap-4 text-left focus-visible:outline-none"
                aria-label={`Open ${entry.item.title}`}
                onClick={() => void navigate(`/books/${entry.id}`)}
              >
                <div data-card-cover="">
                  <CoverImage
                    src={entry.item.cover_url}
                    alt={`Cover of ${entry.item.title}`}
                    className={
                      props.view === "table"
                        ? "h-14 w-10 shrink-0"
                        : "aspect-[2/3] rounded-xl"
                    }
                  />
                </div>
                <div className="min-w-0 flex-1" data-card-meta="">
                  <h2 className="truncate font-semibold">{entry.item.title}</h2>
                  <p className="truncate text-sm text-zinc-400">
                    {entry.item.sort_author ?? "Unknown author"}
                  </p>
                  <p className="text-xs text-zinc-500">
                    Edition year: {entry.item.year ?? "unknown"}
                    {entry.item.metadata.original_year &&
                    entry.item.metadata.original_year !== entry.item.year
                      ? ` · Original: ${entry.item.metadata.original_year}`
                      : ""}
                  </p>
                </div>
              </button>
              <EntryControls
                entry={entry}
                onScore={props.onScore}
                onStatus={props.onStatus}
              />
            </article>
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
