import type { LibraryEntry, LibraryFilters } from "@/api/library";

export type LibraryView = "grid" | "table";
export const viewPreferenceKey = "akasha.library.view";

export const defaultLibraryFilters: LibraryFilters = {
  statuses: [],
  shelves: [],
  formats: [],
  query: "",
  sort: "date_added",
  order: "desc",
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
    filters.query.trim(),
  ].join("|");
}

export function readViewPreference(): LibraryView {
  return localStorage.getItem(viewPreferenceKey) === "table" ? "table" : "grid";
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
