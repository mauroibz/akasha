import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { m } from "motion/react";
import { toast } from "sonner";
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
import { ChevronRight } from "lucide-react";

import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  chooseableStatuses,
  statusHotkeys,
  statusLabels,
} from "@/features/library/labels";
import { useMotionPresets } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import {
  isEditableTarget,
  mergeUniqueEntries,
} from "@/features/library/library";

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
  const [lastShiftIndex, setLastShiftIndex] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const presets = useMotionPresets();
  const navigate = useNavigate();

  // Debounce search. Same guard as the library: writing an identical query
  // string back to the URL re-rendered the whole virtualized table a quarter
  // second after every page load, and reset the selection with it.
  useEffect(() => {
    const trimmed = search.trim();
    if (trimmed === filters.query) return;
    const timer = window.setTimeout(() => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (trimmed) next.set("q", trimmed);
          else next.delete("q");
          return next;
        },
        { replace: true },
      );
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search, filters.query, setSearchParams]);

  // Reset selection when filters change
  useEffect(() => {
    setSelectedIds(new Set());
    setAllMatching(false);
    setExcludedIds(new Set());
  }, [filters]);

  const library = useInfiniteQuery({
    queryKey: ["triage", filters],
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
  const firstPage = library.data?.pages[0];

  const bulkMutation = useMutation({
    mutationFn: (body: Parameters<typeof bulkUpdateEntries>[0]) =>
      bulkUpdateEntries(body),
    onSuccess: (affected) => {
      toast.success(`${affected} entries updated`);
      setSelectedIds(new Set());
      setAllMatching(false);
      setExcludedIds(new Set());
      void queryClient.invalidateQueries({ queryKey: ["triage"] });
      void queryClient.invalidateQueries({ queryKey: ["library"] });
    },
    onError: () => toast.error("Bulk update failed"),
  });

  const acceptMutation = useMutation({
    mutationFn: () => acceptSuggestedStatuses({ status: filters.statuses }),
    onSuccess: (affected) => {
      toast.success(`${affected} suggested statuses accepted`);
      void queryClient.invalidateQueries({ queryKey: ["triage"] });
      void queryClient.invalidateQueries({ queryKey: ["library"] });
    },
    onError: () => toast.error("Could not accept suggested statuses"),
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
      <header className="flex flex-wrap items-end justify-between gap-5 border-b border-border pb-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">
            Triage
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">
            Inbox
            {firstPage?.total ? (
              <span className="ml-3 text-lg text-muted-foreground">
                {firstPage.total} unsorted
              </span>
            ) : null}
          </h1>
          {entries.some((entry) => entry.score_provisional) ? (
            // The bare interpunct that used to mark these read as a typo. A
            // marker nobody can decode is not a marker.
            <p className="mt-2 text-xs text-muted-foreground">
              <span aria-hidden="true">*</span> a provisional score, converted
              from an imported rating and not yet confirmed. &ldquo;Clear
              provisional&rdquo; removes it from a selection.
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-3">
          {firstPage?.total ? (
            <Button
              className="rounded-full px-5"
              disabled={acceptMutation.isPending}
              onClick={() => acceptMutation.mutate()}
            >
              {acceptMutation.isPending ? "Accepting…" : "Accept all suggested"}
            </Button>
          ) : null}
          <Button
            variant="outline"
            className="rounded-full"
            onClick={() => void navigate("/")}
          >
            ← Library
          </Button>
        </div>
      </header>
      <section
        aria-label="Triage filters"
        className="mt-6 flex flex-wrap items-center gap-3"
      >
        <label className="relative min-w-60 flex-1">
          <span className="sr-only">Filter triage</span>
          <Input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Filter by title or author  /"
            className="h-11 rounded-full bg-surface"
          />
        </label>
      </section>

      {library.isPending && (
        <div className="py-24 text-center text-muted-foreground" role="status">
          Loading inbox…
        </div>
      )}
      {library.isError && (
        <div className="py-24 text-center" role="alert">
          <h2 className="text-xl font-semibold">Inbox could not be loaded</h2>
          <Button
            className="mt-5 rounded-full px-5"
            onClick={() => void library.refetch()}
          >
            Try again
          </Button>
        </div>
      )}
      {firstPage?.items.length === 0 && (
        <section className="py-24 text-center">
          <h2 className="text-2xl font-semibold">Inbox is clear</h2>
          <p className="mt-2 text-muted-foreground">
            Import books to start triaging.
          </p>
        </section>
      )}

      {entries.length > 0 && (
        <>
          {/* Bulk action bar */}
          {selectionCount > 0 && (
            // Transform and opacity only. The bar sits in normal flow, so
            // animating its height or margin would push the table underneath it
            // on every selection change. No exit either: dismissing a selection
            // should feel immediate.
            <m.div
              className="sticky top-3 z-20 mt-4 flex flex-wrap items-center gap-3 rounded-2xl bg-surface-raised p-3 shadow-lg"
              role="toolbar"
              aria-label="Bulk actions"
              initial={presets.actionBar.initial}
              animate={presets.actionBar.animate}
            >
              <span className="px-2 text-sm text-foreground">
                {selectionCount} selected
              </span>
              {/* An action menu, not a stateful field: it fires and resets, so
                  it carries no value and shows its prompt as a placeholder. */}
              <Select
                value=""
                onValueChange={(value) =>
                  bulkMutation.mutate(
                    buildBulkBody({ status: value as EntryStatus }),
                  )
                }
              >
                <SelectTrigger
                  aria-label="Set status for selected"
                  className="h-11 w-auto gap-2 rounded-full bg-surface-raised text-sm"
                >
                  <SelectValue placeholder="Set status…" />
                </SelectTrigger>
                <SelectContent>
                  {chooseableStatuses.map((status) => (
                    <SelectItem key={status} value={status}>
                      {statusLabels[status]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value=""
                onValueChange={(value) =>
                  bulkMutation.mutate(buildBulkBody({ score: Number(value) }))
                }
              >
                <SelectTrigger
                  aria-label="Set score for selected"
                  className="h-11 w-auto gap-2 rounded-full bg-surface-raised text-sm"
                >
                  <SelectValue placeholder="Set score…" />
                </SelectTrigger>
                <SelectContent>
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((score) => (
                    <SelectItem key={score} value={String(score)}>
                      {score}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="secondary"
                className="rounded-full text-sm"
                onClick={() =>
                  bulkMutation.mutate(
                    buildBulkBody({ clear_provisional: true }),
                  )
                }
              >
                Clear provisional
              </Button>
              <Button
                variant="secondary"
                className="rounded-full text-sm"
                onClick={() => {
                  setSelectedIds(new Set());
                  setAllMatching(false);
                  setExcludedIds(new Set());
                }}
              >
                Clear selection
              </Button>
            </m.div>
          )}

          {/* Virtualized table */}
          <div
            ref={parentRef}
            className="triage-scroll mt-4 h-[min(70vh,760px)] overflow-auto rounded-2xl bg-surface/40"
            // A feed, not a table: these rows carry no column headers and no
            // cells, so `role="table"` promised a structure that was not there
            // and axe reported the missing children as critical (DEC-038).
            role="feed"
            aria-label="Triage inbox"
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
                    role="article"
                    aria-posinset={row.index + 1}
                    aria-setsize={firstPage?.total ?? entries.length}
                    tabIndex={0}
                    className={`absolute left-0 top-0 flex w-full items-center gap-3 border-b border-border px-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${selected ? "bg-primary/10" : ""}`}
                    style={{
                      height: rowHeight,
                      transform: `translateY(${row.start}px)`,
                    }}
                    onClick={(e) => {
                      if (
                        e.target instanceof HTMLElement &&
                        e.target.closest(
                          'button, a, select, input, [role="checkbox"]',
                        )
                      )
                        return;
                      setFocusedId(entry.id);
                      toggleSelect(entry.id, row.index, e.shiftKey);
                    }}
                    onFocus={() => setFocusedId(entry.id)}
                  >
                    <Checkbox
                      className="shrink-0"
                      checked={selected}
                      aria-label={`Select ${entry.item.title}`}
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
                      <p className="truncate text-xs text-muted-foreground">
                        {entry.item.creator ?? "Unknown"}
                      </p>
                    </div>
                    {hasConflict && (
                      <span
                        className="shrink-0 rounded-full bg-primary/15 px-2 py-0.5 text-xs text-primary"
                        title={`Suggested: ${statusLabels[entry.suggested_status!]}`}
                      >
                        {statusLabels[entry.suggested_status!]}
                      </span>
                    )}
                    <span
                      className={cn(
                        scoreChipShape,
                        scoreChipClass(entry.score),
                        "shrink-0 text-xs",
                        entry.score === null && "px-0",
                      )}
                      title={
                        entry.score_provisional
                          ? "Provisional score, carried from the import"
                          : undefined
                      }
                    >
                      {entry.score ?? "—"}
                      {entry.score_provisional ? (
                        <>
                          <span aria-hidden="true">*</span>
                          <span className="sr-only"> (provisional)</span>
                        </>
                      ) : null}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 shrink-0 rounded-full p-0 text-muted-foreground"
                      aria-label={`Open ${entry.item.title}`}
                      onClick={() => void navigate(`/books/${entry.id}`)}
                    >
                      <ChevronRight />
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
