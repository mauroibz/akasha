import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef, useState } from "react";

import type { LibraryEntry } from "@/api/library";
import type { LibraryView } from "./library";

interface VirtualLibraryProps {
  entries: LibraryEntry[];
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  focusedId: number | null;
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
  const [scoreDraft, setScoreDraft] = useState(entry.score?.toString() ?? "");
  useEffect(() => setScoreDraft(entry.score?.toString() ?? ""), [entry.score]);
  return (
    <div className="flex items-center gap-2">
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
      <input
        id={`score-${entry.id}`}
        className={`h-11 w-14 rounded-lg bg-zinc-800 px-2 text-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-fuchsia-400 ${entry.score_provisional ? "ring-1 ring-amber-400/70 text-amber-200" : ""}`}
        inputMode="numeric"
        min={1}
        max={10}
        type="number"
        value={scoreDraft}
        onChange={(event) => {
          setScoreDraft(event.target.value);
          const score = Number(event.target.value);
          if (event.target.value && score >= 1 && score <= 10)
            onScore(entry, score);
        }}
      />
    </div>
  );
}

export function VirtualLibrary(props: VirtualLibraryProps) {
  const parentRef = useRef<HTMLDivElement>(null);
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
          return (
            <article
              aria-label={entry.item.title}
              className={
                props.view === "table"
                  ? "absolute left-0 top-0 flex w-full items-center gap-4 border-b border-zinc-800 px-4"
                  : "absolute left-0 top-0 grid w-full grid-cols-[128px_1fr] gap-5 px-4 py-3"
              }
              data-entry-id={entry.id}
              data-provisional={entry.score_provisional ? "true" : "false"}
              key={entry.id}
              onFocus={() => props.onFocusEntry(entry.id)}
              role={props.view === "table" ? "row" : undefined}
              style={{
                height: row.size,
                transform: `translateY(${row.start}px)`,
              }}
              tabIndex={0}
            >
              <div
                className={
                  props.view === "table"
                    ? "h-14 w-10 shrink-0 rounded bg-zinc-800"
                    : "aspect-[2/3] rounded-xl bg-zinc-800"
                }
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <h2 className="truncate font-semibold">{entry.item.title}</h2>
                <p className="truncate text-sm text-zinc-400">
                  {entry.item.sort_author ?? "Unknown author"}
                </p>
              </div>
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
