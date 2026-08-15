import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AnimatePresence, m } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import {
  getLibraryPage,
  patchEntry,
  type EntryFormat,
  type EntryStatus,
  type LibraryEntry,
  type LibraryFilters,
  type LibraryPage,
  type SortKey,
} from "@/api/library";
import { getShelves } from "@/api/shelves";
import { AkashaMark } from "@/components/AkashaMark";
import { useMotionPresets } from "@/lib/motion";
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
import { domainsFrom, sortLabels } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import {
  domainPreferenceKey,
  isEditableTarget,
  libraryMotionKey,
  mergeUniqueEntries,
  readDomainPreference,
  readViewPreference,
  viewPreferenceKey,
  type LibraryView,
} from "@/features/library/library";

/** Radix Select rejects an empty item value, so "no shelf filter" needs a name. */
const allShelves = "__all__";
const allFormats = "__all_formats__";
/** The same problem one tier up: "every domain" is a tab and needs a value. */
const allDomains = "__all_domains__";

function filtersFromParams(params: URLSearchParams): LibraryFilters {
  const statuses = params.getAll("status") as EntryStatus[];
  return {
    statuses,
    shelves: params.getAll("shelf"),
    formats: params.getAll("format") as EntryFormat[],
    types: params.getAll("type"),
    query: params.get("q") ?? "",
    sort: (params.get("sort") as SortKey) ?? "date_added",
    order: (params.get("order") as "asc" | "desc") ?? "desc",
  };
}

function paramsFromFilters(filters: LibraryFilters): URLSearchParams {
  const params = new URLSearchParams();
  filters.statuses.forEach((s) => params.append("status", s));
  filters.shelves.forEach((s) => params.append("shelf", s));
  filters.formats.forEach((s) => params.append("format", s));
  filters.types.forEach((s) => params.append("type", s));
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
  const [rollbackId, setRollbackId] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const presets = useMotionPresets();
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
    // The ring says "this is the one you just added" and then stops saying it.
    // Left permanent it becomes a second, meaningless selection state sitting
    // beside the keyboard focus ring. `focusedId` is deliberately not cleared:
    // it is where j/k resume from.
    const timer = window.setTimeout(() => setHighlightId(null), 2200);
    return () => window.clearTimeout(timer);
  }, [location.state]);

  // The shake runs once and is over in a third of a second; the marker is
  // held longer so the row stays identifiable while the toast is still up.
  useEffect(() => {
    if (rollbackId === null) return;
    const timer = window.setTimeout(() => setRollbackId(null), 1200);
    return () => window.clearTimeout(timer);
  }, [rollbackId]);

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

  /**
   * A fresh visit lands on the domain last used.
   *
   * It runs once, before anything is fetched, and writes the value into the URL —
   * from there the choice is an ordinary filter, so a reload, the back button and a
   * shared link all behave without this effect being involved again. A `type`
   * already in the URL wins, because that is somebody being explicit.
   */
  const restoredDomain = useRef(false);
  useEffect(() => {
    if (restoredDomain.current) return;
    restoredDomain.current = true;
    if (searchParams.has("type")) return;
    const remembered = readDomainPreference();
    if (!remembered) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("type", remembered);
        return next;
      },
      { replace: true },
    );
  }, [searchParams, setSearchParams]);

  const library = useInfiniteQuery({
    queryKey: ["library", filters],
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
  // Every shelf, not only the ones on the pages loaded so far: a shelf whose books
  // are all further down the list was previously unfilterable.
  // One cached request for the whole session, shared with every card on the page.
  const itemTypes = useItemTypes();
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
  const domains = useMemo(() => domainsFrom(itemTypes.data), [itemTypes.data]);
  // One domain at a time is the whole point of the strip, so the filter carries at
  // most one value even though the API accepts a repeated parameter.
  const selectedDomain = filters.types[0] ?? "";
  // The domains the chips and the format list describe: one when a tab is chosen,
  // all of them under "All".
  const shownDomains = useMemo(
    () =>
      selectedDomain
        ? domains.filter((type) => type.id === selectedDomain)
        : domains,
    [domains, selectedDomain],
  );
  // Every format the shown domains declare, once. The filter spans domains — an
  // entry carries formats, not a domain — so this is a flat list rather than a group
  // per domain, which offered `Digital` twice with one meaning.
  const formatChoices = useMemo(() => {
    const seen = new Map<string, { value: EntryFormat; label: string }>();
    for (const type of shownDomains) {
      for (const format of type.formats ?? []) {
        if (!seen.has(format.value)) seen.set(format.value, format);
      }
    }
    return Array.from(seen.values());
  }, [shownDomains]);
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
      // Captured here and carried in the context. Reading `filters` again in
      // `onError` would read whatever sort is on screen when the write fails,
      // which is not necessarily the one this snapshot came from.
      const key = ["library", filters] as const;
      await queryClient.cancelQueries({ queryKey: key });
      const snapshot = queryClient.getQueryData(key);
      queryClient.setQueryData<{ pages: LibraryPage[]; pageParams: unknown[] }>(
        key,
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
      return { key, snapshot };
    },
    onError: (_error, { entry }, context) => {
      if (context) queryClient.setQueryData(context.key, context.snapshot);
      // The toast names no book, so the row itself says which value reverted.
      // Visual state only: no text, no role, no second live region, so the
      // failure is still announced exactly once (DEC-028).
      setRollbackId(entry.id);
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
  /**
   * Choosing a domain, which is a filter change plus one piece of bookkeeping.
   *
   * Statuses that belong to the domain being left are dropped: keeping `reading`
   * while switching to records leaves the list filtered by a value none of the
   * visible chips can clear, so the library reads as empty for no reason the screen
   * can explain.
   */
  const chooseDomain = (id: string) => {
    const kept = new Set(
      (id ? domains.filter((type) => type.id === id) : domains).flatMap(
        (type) => type.statuses.map((status) => status.value),
      ),
    );
    localStorage.setItem(domainPreferenceKey, id);
    updateFilters({
      types: id ? [id] : [],
      statuses: filters.statuses.filter((value) => kept.has(value)),
    });
  };
  const setLibraryView = (next: LibraryView) => {
    setView(next);
    localStorage.setItem(viewPreferenceKey, next);
  };

  const inboxCount = firstPage?.facets.status_counts.unsorted ?? 0;

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-5 py-7 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-5 border-b border-border pb-6">
        {/* The horizontal lockup: mark at 48px, then the wide-tracked eyebrow
          over the tight-tracked wordmark. Mirrors
          docs/brand/source/lockup-horizontal.svg. */}
        <div className="flex items-center gap-4">
          <AkashaMark
            size={48}
            className="shrink-0 text-foreground"
            aria-hidden="true"
          />
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">
              Personal library
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight">
              Akasha
            </h1>
          </div>
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
            Add to library
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
            placeholder="Search title or creator  /"
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
        <Select
          value={filters.formats[0] ?? allFormats}
          onValueChange={(value) =>
            updateFilters({
              formats: value === allFormats ? [] : [value as EntryFormat],
            })
          }
        >
          <SelectTrigger
            aria-label="Filter by format"
            className="h-11 w-auto gap-2 rounded-full bg-surface"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={allFormats}>All formats</SelectItem>
            {/* One entry per distinct format, not one per domain that declares it:
                `digital` belongs to books and records both, and listing it twice
                gave two options with the same value and the same count. The filter
                itself spans domains, so a flat list is what it actually does. */}
            {formatChoices.map((format) => (
              <SelectItem key={format.value} value={format.value}>
                {format.label}{" "}
                {firstPage?.facets.format_counts[format.value] ?? 0}
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
      {/* The domain strip. Rendered from `/api/item-types`, so a third domain
          appears here by existing rather than by anybody editing this file.

          A radio group and not a Radix `Tabs`, for the same reason the add screen
          chooses its domain this way: a tab claims a panel it controls, and a
          `TabsTrigger` with no `TabsContent` behind it points `aria-controls` at
          an element that does not exist — which axe reports as a critical
          `aria-valid-attr-value` failure. This is a single-choice filter, and a
          radio group is what that is. */}
      {domains.length > 1 && (
        <div
          role="radiogroup"
          aria-label="Choose a domain"
          className="mt-6 inline-flex rounded-full bg-surface p-1"
        >
          {[{ id: "", label: "All" }, ...domains].map((choice) => (
            <button
              key={choice.id || allDomains}
              type="button"
              role="radio"
              aria-checked={selectedDomain === choice.id}
              className={`min-h-11 rounded-full px-5 py-2 text-sm font-medium transition-colors ${
                selectedDomain === choice.id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              } focus-ring`}
              onClick={() => chooseDomain(choice.id)}
            >
              {choice.label}
            </button>
          ))}
        </div>
      )}
      {/* One row per domain, each under its own name.
          A library holding books and records has no single status vocabulary to
          put in one row: "Read" and "Owned" beside each other with no indication
          of what they belong to reads as one confused list (DEC-060). With a tab
          chosen there is only one row and the tab already carries the name, so the
          heading comes off rather than saying it twice. */}
      {shownDomains.map((type) => (
        <div
          key={type.id}
          className="mt-4 flex flex-wrap items-center gap-2"
          aria-label={`Filter ${type.label.toLowerCase()}s by status`}
          role="group"
        >
          {!selectedDomain && (
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {type.label}
            </span>
          )}
          {type.statuses.map((status) => {
            const active = filters.statuses.includes(status.value);
            return (
              <button
                key={status.value}
                aria-pressed={active}
                className="min-h-11 rounded-full border border-border px-4 text-sm aria-pressed:border-primary aria-pressed:text-primary focus-ring"
                onClick={() =>
                  updateFilters({
                    statuses: active
                      ? filters.statuses.filter(
                          (value) => value !== status.value,
                        )
                      : [...filters.statuses, status.value],
                  })
                }
              >
                {status.label}{" "}
                {firstPage?.facets.status_counts_by_type?.[type.id]?.[
                  status.value
                ] ?? 0}
              </button>
            );
          })}
        </div>
      ))}
      {library.isPending && (
        // Holds the list's height while the new page resolves. Without it the
        // page collapses to a short message between two lists and the whole
        // layout jumps underneath the crossfade.
        <div
          className="flex min-h-[min(70vh,760px)] items-center justify-center py-24 text-center text-muted-foreground"
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
      {/* The crossfade is on the container and nowhere else. `mode="wait"` is
          not a stylistic choice: with the default, moving to a filter TanStack
          already has cached mounts the old and new lists in the same commit,
          and two virtualized stacks -- each with its own scroll container and
          its own total-size spacer -- double both the mounted-card count and
          the page height for the duration. */}
      <AnimatePresence mode="wait" initial={false}>
        {entries.length > 0 && (
          <m.div
            key={libraryMotionKey(filters)}
            data-library-container=""
            initial={presets.crossfade.initial}
            animate={presets.crossfade.animate}
            exit={presets.crossfade.exit}
          >
            <VirtualLibrary
              entries={entries}
              total={firstPage?.total ?? entries.length}
              view={view}
              focusedId={focusedId}
              highlightId={highlightId}
              rollbackId={rollbackId}
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
          </m.div>
        )}
      </AnimatePresence>
    </main>
  );
}
