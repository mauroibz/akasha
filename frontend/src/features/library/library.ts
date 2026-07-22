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
