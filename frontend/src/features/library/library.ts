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

/** A shelf pinned into the library's command bar (Sprint 074 deliverable 6). */
export const pinnedShelfKey = "akasha.library.pinnedShelf";

export interface PinnedShelf {
  slug: string;
  /** Stored alongside the slug so the chip has a name to show without a
   * second fetch, the same reason the remembered domain does not. */
  name: string;
}

/** The pinned shelf, or `null` if none was ever pinned or the stored value
 * cannot be parsed (a private window, a cleared store, a shape from an
 * older version) -- its absence is not an error (AC9). */
export function readPinnedShelf(): PinnedShelf | null {
  const raw = localStorage.getItem(pinnedShelfKey);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const candidate = parsed as Partial<PinnedShelf>;
    if (
      typeof candidate.slug !== "string" ||
      typeof candidate.name !== "string"
    )
      return null;
    return { slug: candidate.slug, name: candidate.name };
  } catch {
    return null;
  }
}

export function writePinnedShelf(shelf: PinnedShelf | null): void {
  if (shelf) localStorage.setItem(pinnedShelfKey, JSON.stringify(shelf));
  else localStorage.removeItem(pinnedShelfKey);
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

const coverHeight = 300;
// Sprint 072 (DEC-139): below the pinned cover, the text band is everything
// — two-line title, creator, and one quiet line carrying year *and* formats.
//
// The number is the content's own height, not a budget with slack in it:
// 8 top padding + a two-line title at leading-5 (40) + the creator line
// (2 + 16) + the year/formats line (2 + 16) + 8 bottom padding = 92. It was
// 112 while the formats sat on a fourth line of their own, so every card
// without formats — nearly all of them — carried 20px of nothing, painted a
// lighter grey than the page (owner feedback after Sprints 072/073 shipped).
const textHeight = 92;

/**
 * Fixed geometry of the virtualized library wall. Card height is constant so the
 * virtualizer keeps cheap fixed-size rows (technical spec §8) while the column
 * count adapts to the measured container width.
 *
 * Sprint 072 moved DEC-023's numbers and kept its rule (DEC-139): the card is
 * vertical now — a cover pinned at coverHeight across the full card width, then
 * a text block of textHeight beneath it. The pin is what keeps the virtualizer
 * cheap: a poster crops (`object-cover`) rather than the row resizing.
 */
export const gridLayout = {
  gap: 20,
  /** The grid wrapper's horizontal padding; the column count subtracts it, so it
   * is part of the contract between this block and VirtualLibrary's row. */
  paddingX: 32,
  /** The narrowest card the wall will show; below this the wall has one fewer
   * column instead of narrower cards. Chosen so 1440px mounts at least five
   * columns and a phone mounts one wide cover (AC3). */
  cardMinWidth: 190,
  /** Pinned cover height, cropped at the full card width (DEC-139). */
  coverHeight,
  /** Text block below the cover: a two-line title at the full card measure, the
   * creator, and one quiet line carrying year and formats together. Sized to
   * that content exactly, so the block has no dead band under it. */
  textHeight,
  cardHeight: coverHeight + textHeight,
  /** A ceiling, not a target. The page container caps the wall at 1600px
   * (DEC-139), so it never mounts more than this many columns of DOM. */
  maxColumns: 6,
} as const;

export const gridRowHeight = gridLayout.cardHeight + gridLayout.gap;
// Sprint 072 D7: the list density is a genuinely tighter second density now —
// one ~56px band holding the 32×48 cover, title, creator, year, formats, status
// pill and score chip, about 16 rows under a 900px viewport against the 9 the
// old 84px row managed.
export const tableRowHeight = 52;

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
 * The container width HomePage's main row hands the wall at a given viewport
 * width — the same `px-5` / `sm:px-8` paddings, the `max-w-[1600px]` ceiling
 * and the 640px `sm:` breakpoint. Kept here so the wall's column contract
 * (1 / ≥5 / ≥6 columns at 390 / 1440 / 2560, AC3) is asserted against the same
 * constants VirtualLibrary measures, instead of drifting from them.
 */
export function containerWidthFor(viewportWidth: number): number {
  if (!Number.isFinite(viewportWidth) || viewportWidth <= 0) return 0;
  if (viewportWidth < 640) return Math.max(320, viewportWidth) - 40;
  return Math.min(viewportWidth, 1600) - 64;
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
