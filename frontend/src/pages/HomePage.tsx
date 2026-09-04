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
  type ItemType,
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
import { StatusFilter } from "@/features/library/StatusFilter";
import { VirtualLibrary } from "@/features/library/VirtualLibrary";
import {
  domainsFrom,
  insightKeyOptions,
  labelFor,
  sortLabels,
} from "@/features/library/labels";
import { AddForm } from "@/features/add/AddForm";
import { ResultsGrid } from "@/features/add/ResultsGrid";
import { useWebSearch } from "@/features/add/useWebSearch";
import { ProviderHealthNotice } from "@/components/ProviderHealthNotice";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { SearchCandidate } from "@/api/add";
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
    // An insights ranking row links here as `/?type=...&key=...&value=...` — without
    // reading them back out, the library page would silently ignore the link.
    key: params.get("key") ?? "",
    value: params.get("value") ?? "",
    valueLabel: params.get("label") ?? "",
  };
}

function paramsFromFilters(filters: LibraryFilters): URLSearchParams {
  const params = new URLSearchParams();
  filters.statuses.forEach((s) => params.append("status", s));
  filters.shelves.forEach((s) => params.append("shelf", s));
  filters.formats.forEach((s) => params.append("format", s));
  filters.types.forEach((s) => params.append("type", s));
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (filters.key && filters.value) {
    params.set("key", filters.key);
    params.set("value", filters.value);
    if (filters.valueLabel) params.set("label", filters.valueLabel);
  }
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
  const [selectedCandidate, setSelectedCandidate] =
    useState<SearchCandidate | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  /**
   * When the reader last touched the box.
   *
   * The settle rule is "still for ~800 ms", and the conditions that let a search
   * fire — the URL caught up, the library answered, it answered with nothing —
   * become true at their own pace. Measuring the wait from the last keystroke rather
   * than from the last of those means a slow library does not push the search out by
   * however long it took.
   */
  const lastTypedAt = useRef(0);
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

  const itemTypes = useItemTypes();
  const domains = useMemo(() => domainsFrom(itemTypes.data), [itemTypes.data]);
  /**
   * Whether the library can be asked for rows yet.
   *
   * Every list request names a domain now, and on a cold visit the domain is not
   * known until the registry answers — so firing before that spends a request on an
   * unfiltered page that is replaced a moment later, and flashes another domain's
   * rows on the way. Waiting is one condition; the two ways of being ready are a
   * `type` already resolved into the URL, and a build whose registry declares nothing
   * to filter by, which includes the registry having failed. A registry outage must
   * not be the reason the library is blank.
   */
  const domainReady =
    filters.types.length > 0 || (!itemTypes.isPending && domains.length === 0);
  const library = useInfiniteQuery({
    queryKey: ["library", filters],
    queryFn: ({ pageParam, signal }) =>
      getLibraryPage(filters, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: domainReady,
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
  /**
   * A fresh visit lands on the domain last used, and always on exactly one.
   *
   * It writes the value into the URL — from there the choice is an ordinary filter,
   * so a reload, the back button and a shared link all behave without this effect
   * being involved again. A `type` already in the URL wins, because that is somebody
   * being explicit.
   *
   * The fallback is the **first declared domain**, not "everything" (DEC-065). Three
   * cases reach it and they are deliberately one branch: never having chosen, the
   * literal `""` Sprint 027 stored as its way of saying "All", and a remembered domain
   * this build no longer declares. None of them can be honoured as a filter now, and
   * a library filtered by no domain is exactly the state this sprint removes.
   *
   * It waits for the registry, because the fallback is a value only the registry has.
   *
   * **It answers to the URL, not to the mount.** It used to run once per mount, which
   * is right for every way of arriving that remounts the page and wrong for the one
   * that does not: the shell's *Library* link points at `/` with no query, so pressing
   * it while already here strips `type` and leaves a mounted page whose restore has
   * already fired. Every list request names a domain, so the library then waits for a
   * domain nothing was going to give it and says "Loading your library…" forever. A
   * URL without a `type` is exactly the state this effect exists to fix, whenever it
   * occurs; writing the value back makes the effect its own guard against repeating.
   */
  useEffect(() => {
    if (searchParams.has("type")) return;
    if (itemTypes.isPending) return;
    if (!domains.length) return;
    const remembered = readDomainPreference();
    const chosen = domains.some((type) => type.id === remembered)
      ? remembered
      : domains[0].id;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("type", chosen);
        return next;
      },
      { replace: true },
    );
  }, [searchParams, setSearchParams, domains, itemTypes.isPending]);
  // One domain at a time is the whole point of the strip, so the filter carries at
  // most one value even though the API accepts a repeated parameter.
  const selectedDomain = filters.types[0] ?? "";
  // The domain the chips and the format list describe. Always exactly one once the
  // registry has loaded, which is what lets one control mean both "these rows" and
  // "these providers" (DEC-065). It is a list only because the registry may not have
  // answered yet, and because `.map` over nothing is the whole empty case.
  const shownDomains = useMemo(
    () => domains.filter((type) => type.id === selectedDomain),
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
      /**
       * The shortcuts belong to the surface the reader is in.
       *
       * `j`/`k` and the digits address library rows. With web results on screen
       * there are two lists on one page, and the rule this sprint adopts is that
       * focus decides: standing on a provider result, `j` must not scroll a
       * different list and `7` must not score a row the reader is not looking at.
       * Nothing else changes — the results are reached by Tab, and the confirm
       * dialog is covered already, since `isEditableTarget` refuses anything
       * inside `[role="dialog"]`.
       */
      if (
        event.target instanceof HTMLElement &&
        event.target.closest("[data-web-results]")
      )
        return;
      if (event.key === "/") {
        event.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (event.key === "a") {
        event.preventDefault();
        searchRef.current?.focus();
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
      domains
        .filter((type) => type.id === id)
        .flatMap((type) => type.statuses.map((status) => status.value)),
    );
    localStorage.setItem(domainPreferenceKey, id);
    updateFilters({
      types: [id],
      statuses: filters.statuses.filter((value) => kept.has(value)),
    });
  };
  const setLibraryView = (next: LibraryView) => {
    setView(next);
    localStorage.setItem(viewPreferenceKey, next);
  };

  const inboxCount = firstPage?.facets.status_counts.unsorted ?? 0;
  const domainLabel = labelFor(selectedDomain, domains);
  const web = useWebSearch(selectedDomain);

  /**
   * Settled and empty: the only way typing reaches a provider (DEC-065).
   *
   * Every condition here is load-bearing. Three characters, because two is a
   * fragment of a word. The URL caught up with the box, because until it has, the
   * library on screen answers a different question. The library actually answered —
   * pending or errored is not "the library has nothing", it is "we do not know yet",
   * and guessing costs a request. Zero rows, strictly: searching `dune` while owning
   * *Dune* returns one row and may well be somebody looking for *Dune Messiah*, and a
   * strict rule is the only one that never guesses on the reader's behalf.
   *
   * The literal reading of the ask — search whenever the library misses — fires once
   * per keystroke while typing any title not already owned, which is every add.
   * `Kind of Blue` would cost twelve searches at a five-second timeout each.
   */
  useEffect(() => {
    const trimmed = search.trim();
    if (trimmed.length < 3) return;
    if (trimmed !== filters.query) return;
    if (!library.isSuccess || library.isFetching) return;
    if ((firstPage?.items.length ?? 0) > 0) return;
    if (web.hasSearched(trimmed)) return;
    const wait = Math.max(0, 800 - (Date.now() - lastTypedAt.current));
    const timer = window.setTimeout(() => web.search(trimmed), wait);
    return () => window.clearTimeout(timer);
  }, [
    search,
    filters.query,
    library.isSuccess,
    library.isFetching,
    firstPage,
    web,
  ]);

  /**
   * The override: search now, whatever the library holds.
   *
   * Cached when the string has already been searched, because pressing a button is
   * not new information about the world — it is the reader saying "show me the web
   * for this", and the web for this is already here.
   */
  const searchTheWeb = () => {
    const trimmed = search.trim();
    if (!trimmed) {
      searchRef.current?.focus();
      return;
    }
    web.search(trimmed);
  };

  /**
   * Empty the bar, the query and the results together.
   *
   * The three are one state as far as the reader is concerned: what they asked. A
   * clear that left any of them behind would leave the library filtered by a string
   * no longer on screen. The URL is written directly rather than left to the 250 ms
   * debounce, because a button press should not have a quarter second of lag on it.
   */
  const clearSearch = ({ refocus }: { refocus: boolean }) => {
    setSearch("");
    web.clear();
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("q");
        return next;
      },
      { replace: true },
    );
    // The button hands focus back to the box it just emptied. The add path does
    // not: there the reader's attention is the row that just appeared.
    if (refocus) searchRef.current?.focus();
  };

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
            onClick={() => void navigate("/import?tab=triage")}
          >
            Inbox {inboxCount}
          </Button>
          <Button
            className="rounded-full px-5"
            onClick={() => searchRef.current?.focus()}
          >
            Add to library
          </Button>
        </div>
      </header>
      {/* One bar, one row: which domain, the query, and the override.
          The domain strip sits inside it rather than under the filters, because it
          now picks two things at once — the rows shown and the providers a search
          would reach — and a control that means both belongs beside the thing it
          means them about. */}
      <section
        aria-label="Search and add"
        className="mt-6 flex flex-wrap items-center gap-3"
      >
        {domains.length > 1 && (
          <div
            role="radiogroup"
            aria-label="Choose a domain"
            className="inline-flex shrink-0 rounded-full bg-surface p-1"
          >
            {domains.map((choice) => (
              <button
                key={choice.id}
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
        <label className="relative min-w-60 flex-1">
          <span className="sr-only">
            Search your library, or add something new
          </span>
          <Input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => {
              lastTypedAt.current = Date.now();
              setSearch(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                searchTheWeb();
              }
            }}
            placeholder="Title, creator, ISBN or link  /"
            // The trailing padding is the button's room: without it a long query
            // runs underneath it. `appearance-none` removes WebKit's own tiny
            // cancel glyph, which would otherwise sit beside this one saying the
            // same thing in a style nothing else here uses -- and which Firefox
            // does not render at all, so it could never have been the control.
            className="h-11 rounded-full bg-surface pr-12 [&::-webkit-search-cancel-button]:appearance-none"
          />
          {search && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => clearSearch({ refocus: true })}
              className="focus-ring absolute right-1 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground"
            >
              <span aria-hidden="true" className="text-lg leading-none">
                ×
              </span>
            </button>
          )}
        </label>
        <Button
          className="h-11 shrink-0 rounded-full px-6"
          onClick={searchTheWeb}
        >
          Search
        </Button>
      </section>
      {/* Hidden exactly when the library has nothing for the current query: sort,
          shelf, format and view apply to rows that are not on screen, and a reader
          who searched the web because their own library came up empty gets those
          results sooner without a row of now-meaningless controls above them. */}
      {!(filters.query && firstPage?.items.length === 0) && (
        <section
          aria-label="Library controls"
          className="mt-3 flex flex-wrap items-center gap-3"
        >
          <Select
            value={`${filters.sort}:${filters.order}`}
            onValueChange={(value) => {
              const [sort, order] = value.split(":") as [
                SortKey,
                "asc" | "desc",
              ];
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
          {/* The fourth filter, in the row of filters.
            It was a row of chips of its own -- one whole row of chrome above the
            library for the vocabulary the tab already names. `shownDomains` is at
            most one domain, and empty only until the registry answers, so this
            renders exactly when there is a vocabulary to render. */}
          {shownDomains.map((type) => (
            <StatusFilter
              key={type.id}
              statuses={type.statuses}
              counts={firstPage?.facets.status_counts_by_type?.[type.id] ?? {}}
              value={filters.statuses}
              onChange={(statuses) => updateFilters({ statuses })}
            />
          ))}
          {filters.key && filters.value && (
            <InsightFilterChip
              keyLabel={insightKeyLabel(
                filters.key,
                filters.types[0],
                itemTypes.data,
              )}
              value={filters.valueLabel || filters.value}
              onClear={() =>
                updateFilters({ key: "", value: "", valueLabel: "" })
              }
            />
          )}
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
      )}
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
      {/* Two different silences, and only one of them is worth a screen.
          An empty library is news: there is nothing here and here is what to do
          about it. An empty *result* is the ordinary case of looking something up
          before adding it -- the settled-and-empty rule is about to search the web
          for exactly this string -- so it gets one line, and the results land where
          the screenful of encouragement used to push them. */}
      {firstPage?.items.length === 0 &&
        (filters.query ? (
          <p className="py-6 text-center text-muted-foreground">
            Nothing in your library matches “{filters.query}”.
          </p>
        ) : (
          <section className="py-24 text-center">
            <h2 className="text-2xl font-semibold">Your library is waiting</h2>
            <p className="mt-2 text-muted-foreground">
              Search above to add something, or visit the inbox to get started.
            </p>
          </section>
        ))}
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
      {/* Below the library, and a region of its own.
          The library is a `role="feed"` carrying server-side `aria-posinset` and
          `aria-setsize` (DEC-038); these are not feed items and must never be
          counted as some. A plain labelled section is what keeps the two apart, and
          below rather than above is also what keeps the virtualizer's `scrollMargin`
          still — a variable-height block over a window-virtualized list is the
          Sprint 013 class of bug. */}
      {web.query && (
        <section
          aria-labelledby="web-results-title"
          data-web-results=""
          className="mt-12"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="web-results-title" className="text-xl font-semibold">
              From the web
            </h2>
            <Button
              variant="ghost"
              size="sm"
              className="rounded-full"
              onClick={() => clearSearch({ refocus: true })}
            >
              Clear
            </Button>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Not in your library. Results for “{web.query}”.
          </p>
          <ProviderHealthNotice />
          {web.pending && <p role="status">Searching metadata providers…</p>}
          {web.error && <p role="alert">{web.error}</p>}
          {web.warning && <p role="status">{web.warning}</p>}
          {!web.pending && (
            <ResultsGrid
              results={web.results}
              onSelect={setSelectedCandidate}
              onManual={() => void navigate("/add")}
            />
          )}
        </section>
      )}
      {/* The confirm step, over the library rather than instead of it. Escape is
          already the way out of every other dialog here, and the library staying
          behind it is what makes adding stop being a place you go. */}
      <Dialog
        open={selectedCandidate !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedCandidate(null);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Add to your library</DialogTitle>
          </DialogHeader>
          {selectedCandidate && (
            <AddForm
              itemType={selectedDomain}
              itemTypes={domains}
              candidate={selectedCandidate}
              manual={false}
              onAdded={(entryId, alreadyExists) => {
                setSelectedCandidate(null);
                if (alreadyExists) {
                  toast("Already in your library", {
                    description: "Opened the entry you already have.",
                  });
                  void navigate(`/books/${entryId}`);
                  return;
                }
                toast.success(`${domainLabel} added`);
                /**
                 * Clearing the query is what makes the highlight mean anything.
                 *
                 * The web search only ran because the library had nothing for this
                 * string, so the library behind the dialog is showing an empty
                 * filtered view. Closing the dialog onto it and highlighting a row
                 * that the filter excludes shows the reader nothing at all — which
                 * is what the walkthrough found. The old flow got this for free by
                 * navigating to an unfiltered `/`; here it has to be done.
                 *
                 * The domain filter stays: that is a choice the reader made, and the
                 * thing just added is in it.
                 */
                clearSearch({ refocus: false });
                // On `/` the handoff is a dialog closing rather than a
                // navigation, so the highlight is set directly instead of
                // travelling as router state.
                setHighlightId(entryId);
                setFocusedId(entryId);
                void queryClient.invalidateQueries({ queryKey: ["library"] });
              }}
              onOpenExisting={(entryId) => {
                setSelectedCandidate(null);
                void navigate(`/books/${entryId}`);
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </main>
  );
}

/**
 * What a `key`/`value` filter is, and how to drop it.
 *
 * Sprint 065 linked here from an insights ranking and left the params applying
 * invisibly: a library filtered to one author looked like a library that had lost
 * most of its books, with nothing on screen saying why or how to undo it.
 */
function InsightFilterChip({
  keyLabel,
  value,
  onClear,
}: {
  keyLabel: string;
  value: string;
  onClear: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClear}
      className="flex min-h-11 items-center gap-2 rounded-full bg-primary/15 px-4 text-sm font-medium text-primary hover:bg-primary/25 focus-ring"
    >
      <span>
        Insights · {keyLabel} · {value}
      </span>
      <span aria-hidden="true">✕</span>
      <span className="sr-only">Clear this filter</span>
    </button>
  );
}

/** The domain's own name for the key a ranking filtered by, when it has one. */
function insightKeyLabel(
  key: string,
  type: string | undefined,
  types: ItemType[] | undefined,
): string {
  const domain = types?.find((candidate) => candidate.id === type);
  const options = domain ? insightKeyOptions(domain.fields) : [];
  return options.find((option) => option.name === key)?.label ?? key;
}
