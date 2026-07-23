import type { LibraryEntry, LibraryFilters } from "@/api/library";

export type LibraryView = "grid" | "table";
export const viewPreferenceKey = "akasha.library.view";

export const defaultLibraryFilters: LibraryFilters = {
  statuses: [],
  shelves: [],
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

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) ||
    target.closest('[role="dialog"]') !== null
  );
}
