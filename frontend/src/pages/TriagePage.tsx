import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";

import {
  acceptSuggestedStatuses,
  bulkUpdateEntries,
  getLibraryPage,
  type EntryStatus,
  type LibraryFilters,
  type SortKey,
} from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import {
  isEditableTarget,
  mergeUniqueEntries,
} from "@/features/library/library";

const statusLabels: Record<EntryStatus, string> = {
  unsorted: "Inbox",
  read: "Read",
  reading: "Reading",
  to_read: "To read",
  wishlist: "Wishlist",
  dropped: "Dropped",
};

const statusHotkeys: Record<string, EntryStatus> = {
  r: "read",
  t: "to_read",
  w: "wishlist",
  d: "dropped",
  g: "reading",
  u: "unsorted",
};

function filtersFromParams(params: URLSearchParams): LibraryFilters {
  const statuses = params.getAll("status") as EntryStatus[];
  return {
    statuses: statuses.length ? statuses : ["unsorted"],
    shelves: params.getAll("shelf"),
    query: params.get("q") ?? "",
    sort: (params.get("sort") as SortKey) ?? "date_added",
    order: (params.get("order") as "asc" | "desc") ?? "desc",
  };
}

export function TriagePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(
    () => filtersFromParams(searchParams),
    [searchParams],
  );
  const [search, setSearch] = useState(filters.query);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [allMatching, setAllMatching] = useState(false);
  const [excludedIds, setExcludedIds] = useState<Set<number>>(new Set());
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [lastShiftIndex, setLastShiftIndex] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Debounce search
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (search.trim()) next.set("q", search.trim());
          else next.delete("q");
          return next;
        },
        { replace: true },
      );
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search, setSearchParams]);

  // Reset selection when filters change
  useEffect(() => {
    setSelectedIds(new Set());
    setAllMatching(false);
    setExcludedIds(new Set());
  }, [filters]);

  const library = useInfiniteQuery({
    queryKey: ["triage", filters],
    queryFn: ({ pageParam }) => getLibraryPage(filters, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    retry: false,
  });

  const entries = useMemo(
    () =>
      mergeUniqueEntries(library.data?.pages.map((page) => page.items) ?? []),
    [library.data],
  );
  const firstPage = library.data?.pages[0];

  const bulkMutation = useMutation({
    mutationFn: (body: Parameters<typeof bulkUpdateEntries>[0]) =>
      bulkUpdateEntries(body),
    onSuccess: (affected) => {
      setAnnouncement(`${affected} entries updated`);
      setSelectedIds(new Set());
      setAllMatching(false);
      setExcludedIds(new Set());
      void queryClient.invalidateQueries({ queryKey: ["triage"] });
      void queryClient.invalidateQueries({ queryKey: ["library"] });
    },
    onError: () => setAnnouncement("Bulk update failed"),
  });

  const acceptMutation = useMutation({
    mutationFn: () => acceptSuggestedStatuses({ status: filters.statuses }),
    onSuccess: (affected) => {
      setAnnouncement(`${affected} suggested statuses accepted`);
      void queryClient.invalidateQueries({ queryKey: ["triage"] });
      void queryClient.invalidateQueries({ queryKey: ["library"] });
    },
    onError: () => setAnnouncement("Could not accept suggested statuses"),
  });

  const selectionCount = allMatching
    ? (firstPage?.total ?? 0) - excludedIds.size
    : selectedIds.size;

  // Build bulk body from selection state
  const buildBulkBody = (
    set: Parameters<typeof bulkUpdateEntries>[0]["set"],
  ) => {
    if (allMatching) {
      return {
        filter: {
          status: filters.statuses,
          shelf: filters.shelves,
          q: filters.query.trim() || undefined,
        },
        excluded_entry_ids: Array.from(excludedIds),
        set,
      };
    }
    return {
      entry_ids: Array.from(selectedIds),
      set,
    };
  };

  // Virtualizer
  const parentRef = useRef<HTMLDivElement>(null);
  const rowHeight = 56;
  const virtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 6,
    getItemKey: (index) => entries[index]?.id ?? index,
    initialRect: { width: 1000, height: 640 },
  });
  const virtualItems = virtualizer.getVirtualItems();

  // Load next page near bottom
  useEffect(() => {
    const last = virtualItems.at(-1);
    if (
      last &&
      last.index >= entries.length - 6 &&
      library.hasNextPage &&
      !library.isFetchingNextPage
    )
      library.fetchNextPage();
  }, [virtualItems, entries.length, library]);

  // Scroll focused row into view and move focus to it
  useEffect(() => {
    if (focusedId === null) return;
    // If the focused element is already the target row, nothing to do
    const active = document.activeElement;
    if (
      active instanceof HTMLElement &&
      active.dataset.entryId === String(focusedId)
    )
      return;
    // If focus is on a form control inside the target row, let it stay
    if (
      active instanceof HTMLElement &&
      active.closest(`[data-entry-id="${focusedId}"]`)
    )
      return;
    const index = entries.findIndex((row) => row.id === focusedId);
    if (index < 0) return;
    virtualizer.scrollToIndex(index, { align: "auto" });
    window.requestAnimationFrame(() => {
      parentRef.current
        ?.querySelector<HTMLElement>(`[data-entry-id="${focusedId}"]`)
        ?.focus();
    });
  }, [entries, focusedId, virtualizer]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) {
        // Allow Ctrl/Cmd+A from any target (select-all is a page action)
        if ((event.ctrlKey || event.metaKey) && event.key === "a") {
          event.preventDefault();
          setAllMatching(true);
          setExcludedIds(new Set());
        }
        return;
      }
      if (event.key === "/") {
        event.preventDefault();
        searchRef.current?.focus();
        return;
      }
      // Navigation
      if (
        ["ArrowDown", "j", "ArrowUp", "k"].includes(event.key) &&
        entries.length
      ) {
        event.preventDefault();
        const current = Math.max(
          0,
          entries.findIndex((row) => row.id === focusedId),
        );
        const direction =
          event.key === "ArrowDown" || event.key === "j" ? 1 : -1;
        const next = Math.min(
          entries.length - 1,
          Math.max(0, current + direction),
        );
        setFocusedId(entries[next].id);
        return;
      }
      // Status hotkeys (apply to focused row or selection)
      const statusKey = statusHotkeys[event.key.toLowerCase()];
      if (statusKey) {
        event.preventDefault();
        const entry = entries.find((row) => row.id === focusedId);
        if (entry && selectionCount === 0) {
          // Single-row update via bulk API
          bulkMutation.mutate({
            entry_ids: [entry.id],
            set: { status: statusKey },
          });
        } else if (selectionCount > 0) {
          bulkMutation.mutate(buildBulkBody({ status: statusKey }));
        }
        return;
      }
      // Score shortcuts (1-9, 0=10) on focused row
      const score = event.key === "0" ? 10 : Number(event.key);
      const entry = entries.find((row) => row.id === focusedId);
      if (entry && score >= 1 && score <= 10) {
        event.preventDefault();
        if (selectionCount > 0) {
          bulkMutation.mutate(buildBulkBody({ score }));
        } else {
          bulkMutation.mutate({
            entry_ids: [entry.id],
            set: { score },
          });
        }
        return;
      }
      // Enter: commit and advance (open detail for single row, or just advance)
      if (event.key === "Enter") {
        event.preventDefault();
        if (selectionCount === 0 && focusedId !== null) {
          void navigate(`/books/${focusedId}`);
        } else {
          // After bulk action, advance focus
          const current = Math.max(
            0,
            entries.findIndex((row) => row.id === focusedId),
          );
          if (current < entries.length - 1)
            setFocusedId(entries[current + 1].id);
        }
        return;
      }
      // Escape: clear selection
      if (event.key === "Escape") {
        event.preventDefault();
        setSelectedIds(new Set());
        setAllMatching(false);
        setExcludedIds(new Set());
        return;
      }
      // Ctrl/Cmd+A: select all matching
      if ((event.ctrlKey || event.metaKey) && event.key === "a") {
        event.preventDefault();
        setAllMatching(true);
        setExcludedIds(new Set());
        return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    entries,
    focusedId,
    selectedIds,
    allMatching,
    excludedIds,
    selectionCount,
  ]);

  const toggleSelect = (id: number, index: number, shiftKey: boolean) => {
    if (allMatching) {
      // In all-matching mode, toggle the exclusion set
      setExcludedIds((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
      return;
    }
    if (shiftKey && lastShiftIndex !== null) {
      const start = Math.min(lastShiftIndex, index);
      const end = Math.max(lastShiftIndex, index);
      const range = new Set(selectedIds);
      for (let i = start; i <= end; i++) {
        if (entries[i]) range.add(entries[i].id);
      }
      setSelectedIds(range);
      setLastShiftIndex(index);
      return;
    }
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setLastShiftIndex(index);
  };

  const isRowSelected = (id: number) =>
    allMatching ? !excludedIds.has(id) : selectedIds.has(id);

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-5 py-7 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-5 border-b border-zinc-800 pb-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-fuchsia-400">
            Triage
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">
            Inbox
            {firstPage?.total ? (
              <span className="ml-3 text-lg text-zinc-500">
                {firstPage.total} unsorted
              </span>
            ) : null}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {firstPage?.total ? (
            <button
              className="min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring disabled:opacity-50"
              disabled={acceptMutation.isPending}
              onClick={() => acceptMutation.mutate()}
            >
              {acceptMutation.isPending ? "Accepting…" : "Accept all suggested"}
            </button>
          ) : null}
          <button
            className="min-h-11 rounded-full border border-zinc-800 px-4 text-sm focus-ring"
            onClick={() => void navigate("/")}
          >
            ← Library
          </button>
        </div>
      </header>
      <section
        aria-label="Triage filters"
        className="mt-6 flex flex-wrap items-center gap-3"
      >
        <label className="relative min-w-60 flex-1">
          <span className="sr-only">Filter triage</span>
          <input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Filter by title or author  /"
            className="h-11 w-full rounded-full bg-zinc-900 px-4 outline-none focus-ring"
          />
        </label>
      </section>

      {library.isPending && (
        <div className="py-24 text-center text-zinc-400" role="status">
          Loading inbox…
        </div>
      )}
      {library.isError && (
        <div className="py-24 text-center" role="alert">
          <h2 className="text-xl font-semibold">Inbox could not be loaded</h2>
          <button
            className="mt-5 min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring"
            onClick={() => void library.refetch()}
          >
            Try again
          </button>
        </div>
      )}
      {firstPage?.items.length === 0 && (
        <section className="py-24 text-center">
          <h2 className="text-2xl font-semibold">Inbox is clear</h2>
          <p className="mt-2 text-zinc-400">Import books to start triaging.</p>
        </section>
      )}

      {entries.length > 0 && (
        <>
          {/* Bulk action bar */}
          {selectionCount > 0 && (
            <div
              className="sticky top-3 z-20 mt-4 flex flex-wrap items-center gap-3 rounded-2xl bg-zinc-800 p-3 shadow-lg"
              role="toolbar"
              aria-label="Bulk actions"
            >
              <span className="px-2 text-sm text-zinc-300">
                {selectionCount} selected
              </span>
              <select
                className="min-h-11 rounded-full bg-zinc-700 px-4 text-sm focus-ring"
                value=""
                onChange={(event) => {
                  if (event.target.value)
                    bulkMutation.mutate(
                      buildBulkBody({
                        status: event.target.value as EntryStatus,
                      }),
                    );
                }}
                aria-label="Set status for selected"
              >
                <option value="">Set status…</option>
                <option value="read">Read</option>
                <option value="reading">Reading</option>
                <option value="to_read">To read</option>
                <option value="wishlist">Wishlist</option>
                <option value="dropped">Dropped</option>
              </select>
              <select
                className="min-h-11 rounded-full bg-zinc-700 px-4 text-sm focus-ring"
                value=""
                onChange={(event) => {
                  const score = Number(event.target.value);
                  if (score >= 1 && score <= 10)
                    bulkMutation.mutate(buildBulkBody({ score }));
                }}
                aria-label="Set score for selected"
              >
                <option value="">Set score…</option>
                {Array.from({ length: 10 }, (_, i) => i + 1).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <button
                className="min-h-11 rounded-full bg-zinc-700 px-4 text-sm focus-ring"
                onClick={() =>
                  bulkMutation.mutate(
                    buildBulkBody({ clear_provisional: true }),
                  )
                }
              >
                Clear provisional
              </button>
              <button
                className="min-h-11 rounded-full bg-zinc-700 px-4 text-sm focus-ring"
                onClick={() => {
                  setSelectedIds(new Set());
                  setAllMatching(false);
                  setExcludedIds(new Set());
                }}
              >
                Clear selection
              </button>
            </div>
          )}

          {/* Virtualized table */}
          <div
            ref={parentRef}
            className="triage-scroll mt-4 h-[min(70vh,760px)] overflow-auto rounded-2xl bg-zinc-900/40"
            role="table"
            aria-label="Triage table"
          >
            <div
              className="relative w-full"
              style={{ height: virtualizer.getTotalSize() }}
            >
              {virtualItems.map((row) => {
                const entry = entries[row.index];
                const selected = isRowSelected(entry.id);
                const hasConflict = entry.suggested_status !== null;
                return (
                  <div
                    key={entry.id}
                    data-entry-id={entry.id}
                    data-selected={selected}
                    data-provisional={entry.score_provisional}
                    role="row"
                    tabIndex={0}
                    className={`absolute left-0 top-0 flex w-full items-center gap-3 border-b border-zinc-800 px-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fuchsia-400 ${selected ? "bg-fuchsia-900/20" : ""}`}
                    style={{
                      height: rowHeight,
                      transform: `translateY(${row.start}px)`,
                    }}
                    onClick={(e) => {
                      if (
                        e.target instanceof HTMLElement &&
                        e.target.closest("button, a, select, input")
                      )
                        return;
                      setFocusedId(entry.id);
                      toggleSelect(entry.id, row.index, e.shiftKey);
                    }}
                    onFocus={() => setFocusedId(entry.id)}
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 shrink-0 accent-fuchsia-500"
                      checked={selected}
                      aria-label={`Select ${entry.item.title}`}
                      onChange={() => {}}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSelect(entry.id, row.index, e.shiftKey);
                      }}
                    />
                    <CoverImage
                      src={entry.item.cover_url}
                      alt=""
                      className="h-9 w-7 shrink-0 rounded"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {entry.item.title}
                      </p>
                      <p className="truncate text-xs text-zinc-500">
                        {entry.item.sort_author ?? "Unknown"}
                      </p>
                    </div>
                    {hasConflict && (
                      <span
                        className="shrink-0 rounded-full bg-amber-900/40 px-2 py-0.5 text-xs text-amber-300"
                        title={`Suggested: ${statusLabels[entry.suggested_status!]}`}
                      >
                        {statusLabels[entry.suggested_status!]}
                      </span>
                    )}
                    <span className="shrink-0 text-xs text-zinc-400">
                      {entry.score ?? "—"}
                      {entry.score_provisional ? "·" : ""}
                    </span>
                    <button
                      className="shrink-0 rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-400 focus-ring"
                      aria-label={`Open ${entry.item.title}`}
                      onClick={() => void navigate(`/books/${entry.id}`)}
                    >
                      →
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
      <p className="sr-only" aria-live="assertive">
        {announcement}
      </p>
    </main>
  );
}
