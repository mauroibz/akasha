import type {
  EntryFormat,
  EntryStatus,
  LibraryEntry,
  LibraryFilters,
} from "@/api/library";

export type LibraryView = "grid" | "table";
export const viewPreferenceKey = "akasha.library.view";
/** The domain the library was last showing, so a fresh visit lands where you left. */
export const domainPreferenceKey = "akasha.library.domain";
/**
 * The library's current status/shelf/format/search filters, remembered so
 * Insights can offer to rank inside them (Sprint 067 deliverable 6) without a
 * shared store between two separate pages. Deliberately not `types`, `sort`,
 * `order`, `key` or `value`: those are not among the four `rank()` already
 * forwards to `_filtered_entries`, and the domain is remembered separately
 * (`domainPreferenceKey`).
 */
export const libraryFiltersPreferenceKey = "akasha.library.filters";

export interface RememberedLibraryFilters {
  statuses: EntryStatus[];
  shelves: string[];
  formats: EntryFormat[];
  query: string;
}

const emptyRememberedFilters: RememberedLibraryFilters = {
  statuses: [],
  shelves: [],
  formats: [],
  query: "",
};

export function rememberLibraryFilters(filters: LibraryFilters): void {
  const remembered: RememberedLibraryFilters = {
    statuses: filters.statuses,
    shelves: filters.shelves,
    formats: filters.formats,
    query: filters.query,
  };
  localStorage.setItem(libraryFiltersPreferenceKey, JSON.stringify(remembered));
}

/** The remembered filters, or the empty set if none were ever saved or the
 * stored value cannot be parsed (a private window, a cleared store, a shape
 * from an older version). */
export function readLibraryFiltersPreference(): RememberedLibraryFilters {
  const raw = localStorage.getItem(libraryFiltersPreferenceKey);
  if (!raw) return emptyRememberedFilters;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null)
      return emptyRememberedFilters;
    const candidate = parsed as Partial<RememberedLibraryFilters>;
    return {
      statuses: Array.isArray(candidate.statuses) ? candidate.statuses : [],
      shelves: Array.isArray(candidate.shelves) ? candidate.shelves : [],
      formats: Array.isArray(candidate.formats) ? candidate.formats : [],
      query: typeof candidate.query === "string" ? candidate.query : "",
    };
  } catch {
    return emptyRememberedFilters;
  }
}

/** Whether any of the remembered filters would actually narrow a ranking. */
export function hasRememberedFilters(
  filters: RememberedLibraryFilters,
): boolean {
  return (
    filters.statuses.length > 0 ||
    filters.shelves.length > 0 ||
    filters.formats.length > 0 ||
    filters.query.trim().length > 0
  );
}

export const defaultLibraryFilters: LibraryFilters = {
  statuses: [],
  shelves: [],
  formats: [],
  types: [],
  query: "",
  sort: "date_added",
  order: "desc",
  key: "",
  value: "",
  valueLabel: "",
};

/**
 * Fixed geometry of the virtualized library grid. Card height is constant so the
 * virtualizer keeps cheap fixed-size rows (technical spec §8) while the column
 * count adapts to the measured container width.
 */
export const gridLayout = {
  gap: 20,
  paddingX: 32,
  cardMinWidth: 260,
  cardHeight: 280,
  maxColumns: 4,
} as const;

export const gridRowHeight = gridLayout.cardHeight + gridLayout.gap;
export const tableRowHeight = 84;

/** Columns that fit `containerWidth` without any card dropping below its minimum. */
export function gridColumnCount(containerWidth: number): number {
  const usable = containerWidth - gridLayout.paddingX;
  if (!Number.isFinite(usable) || usable <= 0) return 1;
  return Math.max(
    1,
    Math.min(
      gridLayout.maxColumns,
      Math.floor(
        (usable + gridLayout.gap) / (gridLayout.cardMinWidth + gridLayout.gap),
      ),
    ),
  );
}

/**
 * The identity of the list container for crossfade purposes: every server-side
 * filter and sort value, and nothing else.
 *
 * What it deliberately excludes is the point. Appending a page during infinite
 * scroll and patching one row optimistically both leave the filters untouched,
 * so neither re-keys the container and neither triggers a fade. Technical spec
 * section 8: sort and filter changes crossfade the container; rows do not
 * animate.
 */
export function libraryMotionKey(filters: LibraryFilters): string {
  return [
    filters.sort,
    filters.order,
    [...filters.statuses].sort().join("+"),
    [...filters.shelves].sort().join("+"),
    // Formats were missed when Sprint 026 added them, so changing that filter
    // swapped the list out with no crossfade at all.
    [...filters.formats].sort().join("+"),
    [...filters.types].sort().join("+"),
    filters.query.trim(),
  ].join("|");
}

export function readViewPreference(): LibraryView {
  return localStorage.getItem(viewPreferenceKey) === "table" ? "table" : "grid";
}

/**
 * The remembered domain, or nothing.
 *
 * Read once on mount and then written into the URL, so from that moment on the
 * choice is an ordinary filter: a reload, the back button and a shared link all work
 * without this preference being consulted again. `""` is the stored form of "All",
 * which is deliberately distinct from never having chosen.
 */
export function readDomainPreference(): string {
  return localStorage.getItem(domainPreferenceKey) ?? "";
}

export function mergeUniqueEntries(pages: LibraryEntry[][]): LibraryEntry[] {
  const seen = new Set<number>();
  return pages.flat().filter((entry) => {
    if (seen.has(entry.id)) return false;
    seen.add(entry.id);
    return true;
  });
}

/**
 * Roles that own their keystrokes even though the element is not a native form
 * control. Radix renders a Select trigger as `button[role="combobox"]`, portals
 * its listbox to `document.body`, and does the same for Dialog and AlertDialog
 * content — so a tagName check alone stopped covering these the moment the app
 * adopted the component library, and `7` would have set a score while a status
 * dropdown had focus.
 */
const shortcutBlockingRoles = [
  "dialog",
  "alertdialog",
  "combobox",
  "listbox",
  "menu",
];
const shortcutBlockingSelector = shortcutBlockingRoles
  .map((role) => `[role="${role}"]`)
  .join(",");

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) ||
    target.closest(shortcutBlockingSelector) !== null
  );
}
