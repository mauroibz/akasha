import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

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
import { VirtualLibrary } from "@/features/library/VirtualLibrary";
import {
  isEditableTarget,
  mergeUniqueEntries,
  readViewPreference,
  viewPreferenceKey,
  type LibraryView,
} from "@/features/library/library";

const statusLabels: Record<EntryStatus, string> = {
  unsorted: "Inbox",
  read: "Read",
  reading: "Reading",
  to_read: "To read",
  wishlist: "Wishlist",
  dropped: "Dropped",
};
const sortLabels: Record<SortKey, string> = {
  date_added: "Recently added",
  score: "Score",
  title: "Title",
  sort_author: "Author",
  year: "Year",
  date_finished: "Finished",
};

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
  const [announcement, setAnnouncement] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Restore toast from session storage (set by add page on exact duplicate)
  useEffect(() => {
    const toast = sessionStorage.getItem("akasha.toast");
    if (toast) {
      setAnnouncement(toast);
      sessionStorage.removeItem("akasha.toast");
    }
  }, []);

  // Highlight newly added entry (set by add page via location state)
  useEffect(() => {
    const stored = sessionStorage.getItem("akasha.new-entry");
    if (stored) {
      const id = Number(stored);
      if (id) {
        setHighlightId(id);
        setFocusedId(id);
      }
      sessionStorage.removeItem("akasha.new-entry");
    }
  }, []);

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
  const shelves = useMemo(
    () =>
      Array.from(
        new Map(
          entries
            .flatMap((entry) => entry.shelves)
            .map((shelf) => [shelf.slug, shelf]),
        ).values(),
      ).sort((a, b) => a.name.localeCompare(b.name)),
    [entries],
  );
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
      setAnnouncement(
        "Your change could not be saved. The previous value was restored.",
      );
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
      <header className="flex flex-wrap items-end justify-between gap-5 border-b border-zinc-800 pb-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-fuchsia-400">
            Personal library
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Akasha</h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            className="min-h-11 rounded-full border border-zinc-800 px-4 text-sm focus-ring aria-pressed:border-fuchsia-400 aria-pressed:text-fuchsia-300"
            aria-pressed={filters.statuses.includes("unsorted")}
            onClick={() => void navigate("/triage")}
          >
            Inbox {inboxCount}
          </button>
          <button
            className="min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring"
            onClick={() => void navigate("/add")}
          >
            Add book
          </button>
        </div>
      </header>
      <section
        aria-label="Library controls"
        className="mt-6 flex flex-wrap items-center gap-3"
      >
        <label className="relative min-w-60 flex-1">
          <span className="sr-only">Search library</span>
          <input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search title or author  /"
            className="h-11 w-full rounded-full bg-zinc-900 px-4 outline-none focus-ring"
          />
        </label>
        <label>
          <span className="sr-only">Sort library</span>
          <select
            aria-label="Sort library"
            className="h-11 rounded-full bg-zinc-900 px-4 focus-ring"
            value={`${filters.sort}:${filters.order}`}
            onChange={(event) => {
              const [sort, order] = event.target.value.split(":") as [
                SortKey,
                "asc" | "desc",
              ];
              updateFilters({ sort, order });
            }}
          >
            {Object.entries(sortLabels).flatMap(([key, label]) => [
              <option key={`${key}:desc`} value={`${key}:desc`}>
                {label} ↓
              </option>,
              <option key={`${key}:asc`} value={`${key}:asc`}>
                {label} ↑
              </option>,
            ])}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by shelf</span>
          <select
            aria-label="Filter by shelf"
            className="h-11 rounded-full bg-zinc-900 px-4 focus-ring"
            value={filters.shelves[0] ?? ""}
            onChange={(event) =>
              updateFilters({
                shelves: event.target.value ? [event.target.value] : [],
              })
            }
          >
            <option value="">All shelves</option>
            {shelves.map((shelf) => (
              <option key={shelf.id} value={shelf.slug}>
                {shelf.name}
              </option>
            ))}
          </select>
        </label>
        <div
          className="flex rounded-full bg-zinc-900 p-1"
          aria-label="Library view"
        >
          <button
            aria-label="Grid view"
            aria-pressed={view === "grid"}
            className="h-9 rounded-full px-3 aria-pressed:bg-zinc-700 focus-ring"
            onClick={() => setLibraryView("grid")}
          >
            Grid
          </button>
          <button
            aria-label="Table view"
            aria-pressed={view === "table"}
            className="h-9 rounded-full px-3 aria-pressed:bg-zinc-700 focus-ring"
            onClick={() => setLibraryView("table")}
          >
            Table
          </button>
        </div>
      </section>
      <div className="mt-4 flex flex-wrap gap-2" aria-label="Filter by status">
        {entryStatuses.map((status) => {
          const active = filters.statuses.includes(status);
          return (
            <button
              key={status}
              aria-pressed={active}
              className="min-h-11 rounded-full border border-zinc-800 px-4 text-sm aria-pressed:border-fuchsia-400 aria-pressed:text-fuchsia-300 focus-ring"
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
          className="py-24 text-center text-zinc-400"
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
          <h2 className="text-2xl font-semibold">Your library is waiting</h2>
          <p className="mt-2 text-zinc-400">
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
      <p className="sr-only" aria-live="assertive">
        {announcement}
      </p>
    </main>
  );
}
