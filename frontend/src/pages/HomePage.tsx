import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import {
  entryStatuses,
  getLibraryPage,
  patchEntry,
  type EntryStatus,
  type LibraryEntry,
  type LibraryFilters,
  type LibraryPage,
  type SortKey,
} from "@/api/library";
import { getShelves } from "@/api/shelves";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { VirtualLibrary } from "@/features/library/VirtualLibrary";
import { sortLabels, statusLabels } from "@/features/library/labels";
import {
  isEditableTarget,
  mergeUniqueEntries,
  readViewPreference,
  viewPreferenceKey,
  type LibraryView,
} from "@/features/library/library";

/** Radix Select rejects an empty item value, so "no shelf filter" needs a name. */
const allShelves = "__all__";

function filtersFromParams(params: URLSearchParams): LibraryFilters {
  const statuses = params.getAll("status") as EntryStatus[];
  return {
    statuses,
    shelves: params.getAll("shelf"),
    query: params.get("q") ?? "",
    sort: (params.get("sort") as SortKey) ?? "date_added",
    order: (params.get("order") as "asc" | "desc") ?? "desc",
  };
}

function paramsFromFilters(filters: LibraryFilters): URLSearchParams {
  const params = new URLSearchParams();
  filters.statuses.forEach((s) => params.append("status", s));
  filters.shelves.forEach((s) => params.append("shelf", s));
  if (filters.query.trim()) params.set("q", filters.query.trim());
  params.set("sort", filters.sort);
  params.set("order", filters.order);
  return params;
}

export function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(
    () => filtersFromParams(searchParams),
    [searchParams],
  );
  const [search, setSearch] = useState(filters.query);
  const [view, setView] = useState<LibraryView>(readViewPreference);
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const [highlightId, setHighlightId] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();

  // Highlight the newly added entry. The add page hands the id over as router
  // state; confirmation itself is a toast rendered by the app shell.
  useEffect(() => {
    const id = (location.state as { newEntryId?: number } | null)?.newEntryId;
    if (!id) return;
    setHighlightId(id);
    setFocusedId(id);
    // Consume it so a back/forward navigation does not re-highlight.
    window.history.replaceState({}, "");
  }, [location.state]);

  useEffect(() => {
    const trimmed = search.trim();
    // Nothing to write on mount, or when the box already agrees with the URL.
    // Replacing the entry anyway re-rendered the whole list a quarter second
    // after every page load, for no change.
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

  const library = useInfiniteQuery({
    queryKey: ["library", filters],
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
  // Every shelf, not only the ones on the pages loaded so far: a shelf whose books
  // are all further down the list was previously unfilterable.
  const shelfQuery = useQuery({
    queryKey: ["shelves"],
    queryFn: getShelves,
    retry: false,
  });
  const shelves = useMemo(() => {
    // The shelf filter is a convenience; a failed or odd-shaped shelves response must
    // not take the whole library page down with it.
    const rows = shelfQuery.data;
    if (!Array.isArray(rows)) return [];
    return [...rows].sort((a, b) => a.name.localeCompare(b.name));
  }, [shelfQuery.data]);
  const firstPage = library.data?.pages[0];

  const mutation = useMutation({
    mutationFn: ({
      entry,
      changes,
    }: {
      entry: LibraryEntry;
      changes: Partial<Pick<LibraryEntry, "score" | "status">>;
    }) => patchEntry(entry.id, changes),
    onMutate: async ({ entry, changes }) => {
      await queryClient.cancelQueries({ queryKey: ["library", filters] });
      const snapshot = queryClient.getQueryData(["library", filters]);
      queryClient.setQueryData<{ pages: LibraryPage[]; pageParams: unknown[] }>(
        ["library", filters],
        (old) =>
          old && {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((row) =>
                row.id === entry.id
                  ? {
                      ...row,
                      ...changes,
                      score_provisional:
                        changes.score === undefined
                          ? row.score_provisional
                          : false,
                    }
                  : row,
              ),
            })),
          },
      );
      return { snapshot };
    },
    onError: (_error, _variables, context) => {
      queryClient.setQueryData(["library", filters], context?.snapshot);
      toast.error("Your change could not be saved", {
        description: "The previous value was restored.",
      });
    },
    onSuccess: (saved, { changes }) => {
      const activeKeyChanged =
        (changes.score !== undefined && filters.sort === "score") ||
        (changes.status !== undefined && filters.statuses.length > 0);
      if (activeKeyChanged)
        void queryClient.resetQueries({ queryKey: ["library", filters] });
      else
        queryClient.setQueriesData<{
          pages: LibraryPage[];
          pageParams: unknown[];
        }>(
          { queryKey: ["library"] },
          (old) =>
            old && {
              ...old,
              pages: old.pages.map((page) => ({
                ...page,
                items: page.items.map((row) =>
                  row.id === saved.id ? saved : row,
                ),
              })),
            },
        );
    },
  });

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) return;
      if (event.key === "/") {
        event.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (event.key === "a") {
        event.preventDefault();
        void navigate("/add");
        return;
      }
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
      const score = event.key === "0" ? 10 : Number(event.key);
      const entry = entries.find((row) => row.id === focusedId);
      if (entry && score >= 1 && score <= 10)
        mutation.mutate({ entry, changes: { score } });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [entries, focusedId, mutation, navigate]);

  const updateFilters = (changes: Partial<LibraryFilters>) => {
    const next = { ...filters, ...changes };
    setSearchParams(paramsFromFilters(next), { replace: true });
  };
  const setLibraryView = (next: LibraryView) => {
    setView(next);
    localStorage.setItem(viewPreferenceKey, next);
  };

  const inboxCount = firstPage?.facets.status_counts.unsorted ?? 0;

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-5 py-7 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-5 border-b border-border pb-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">
            Personal library
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Akasha</h1>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="rounded-full aria-pressed:border-primary aria-pressed:text-primary"
            aria-pressed={filters.statuses.includes("unsorted")}
            onClick={() => void navigate("/triage")}
          >
            Inbox {inboxCount}
          </Button>
          <Button
            className="rounded-full px-5"
            onClick={() => void navigate("/add")}
          >
            Add book
          </Button>
        </div>
      </header>
      <section
        aria-label="Library controls"
        className="mt-6 flex flex-wrap items-center gap-3"
      >
        <label className="relative min-w-60 flex-1">
          <span className="sr-only">Search library</span>
          <Input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search title or author  /"
            className="h-11 rounded-full bg-surface"
          />
        </label>
        <Select
          value={`${filters.sort}:${filters.order}`}
          onValueChange={(value) => {
            const [sort, order] = value.split(":") as [SortKey, "asc" | "desc"];
            updateFilters({ sort, order });
          }}
        >
          <SelectTrigger
            aria-label="Sort library"
            className="h-11 w-auto gap-2 rounded-full bg-surface"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(sortLabels).flatMap(([key, label]) => [
              <SelectItem key={`${key}:desc`} value={`${key}:desc`}>
                {label} ↓
              </SelectItem>,
              <SelectItem key={`${key}:asc`} value={`${key}:asc`}>
                {label} ↑
              </SelectItem>,
            ])}
          </SelectContent>
        </Select>
        <Select
          value={filters.shelves[0] ?? allShelves}
          onValueChange={(value) =>
            updateFilters({ shelves: value === allShelves ? [] : [value] })
          }
        >
          <SelectTrigger
            aria-label="Filter by shelf"
            className="h-11 w-auto gap-2 rounded-full bg-surface"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={allShelves}>All shelves</SelectItem>
            {shelves.map((shelf) => (
              <SelectItem key={shelf.id} value={shelf.slug}>
                {shelf.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div
          className="flex rounded-full bg-surface p-1"
          aria-label="Library view"
        >
          <Button
            variant="ghost"
            size="sm"
            aria-label="Grid view"
            aria-pressed={view === "grid"}
            className="rounded-full aria-pressed:bg-surface-raised"
            onClick={() => setLibraryView("grid")}
          >
            Grid
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Table view"
            aria-pressed={view === "table"}
            className="rounded-full aria-pressed:bg-surface-raised"
            onClick={() => setLibraryView("table")}
          >
            Table
          </Button>
        </div>
      </section>
      <div className="mt-4 flex flex-wrap gap-2" aria-label="Filter by status">
        {entryStatuses.map((status) => {
          const active = filters.statuses.includes(status);
          return (
            <button
              key={status}
              aria-pressed={active}
              className="min-h-11 rounded-full border border-border px-4 text-sm aria-pressed:border-primary aria-pressed:text-primary focus-ring"
              onClick={() =>
                updateFilters({
                  statuses: active
                    ? filters.statuses.filter((value) => value !== status)
                    : [...filters.statuses, status],
                })
              }
            >
              {statusLabels[status]}{" "}
              {firstPage?.facets.status_counts[status] ?? 0}
            </button>
          );
        })}
      </div>
      {library.isPending && (
        <div
          className="py-24 text-center text-muted-foreground"
          aria-live="polite"
          role="status"
        >
          Loading your library…
        </div>
      )}
      {library.isError && (
        <div className="py-24 text-center" role="alert">
          <h2 className="text-xl font-semibold">
            Your library could not be loaded
          </h2>
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
          <h2 className="text-2xl font-semibold">Your library is waiting</h2>
          <p className="mt-2 text-muted-foreground">
            Add a book or visit the inbox to get started.
          </p>
        </section>
      )}
      {entries.length > 0 && (
        <VirtualLibrary
          entries={entries}
          view={view}
          focusedId={focusedId}
          highlightId={highlightId}
          hasNextPage={library.hasNextPage}
          isFetchingNextPage={library.isFetchingNextPage}
          loadNextPage={() => void library.fetchNextPage()}
          onFocusEntry={setFocusedId}
          onScore={(entry, score) =>
            mutation.mutate({ entry, changes: { score } })
          }
          onStatus={(entry, status) =>
            mutation.mutate({ entry, changes: { status } })
          }
        />
      )}
    </main>
  );
}
