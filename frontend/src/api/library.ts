export const entryStatuses = [
  "unsorted",
  "read",
  "reading",
  "to_read",
  "wishlist",
  "dropped",
] as const;

export type EntryStatus = (typeof entryStatuses)[number];
export type SortKey =
  "date_added" | "score" | "title" | "sort_author" | "year" | "date_finished";
export type SortOrder = "asc" | "desc";

export interface Shelf {
  id: number;
  name: string;
  slug: string;
}

export interface LibraryEntry {
  id: number;
  item_id: number;
  status: EntryStatus;
  score: number | null;
  notes: string | null;
  date_added: string;
  date_started: string | null;
  date_finished: string | null;
  reread_count: number;
  score_provisional: boolean;
  suggested_status: EntryStatus | null;
  item: {
    id: number;
    type: string;
    title: string;
    subtitle: string | null;
    year: number | null;
    sort_author: string | null;
    cover_path: string | null;
    metadata: Record<string, unknown>;
    identifiers: Record<string, string>;
    sources: Array<{ source: string; source_id: string; is_primary: boolean }>;
  };
  shelves: Shelf[];
}

export interface LibraryPage {
  items: LibraryEntry[];
  next_cursor: string | null;
  total: number;
  facets: { status_counts: Partial<Record<EntryStatus, number>> };
}

export interface LibraryFilters {
  statuses: EntryStatus[];
  shelves: string[];
  query: string;
  sort: SortKey;
  order: SortOrder;
}

export function libraryQueryString(filters: LibraryFilters, cursor?: string) {
  const params = new URLSearchParams({
    sort: filters.sort,
    order: filters.order,
    limit: "100",
  });
  filters.statuses.forEach((status) => params.append("status", status));
  filters.shelves.forEach((shelf) => params.append("shelf", shelf));
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (cursor) params.set("after", cursor);
  return params.toString();
}

export async function getLibraryPage(
  filters: LibraryFilters,
  cursor?: string,
): Promise<LibraryPage> {
  const response = await fetch(
    `/api/entries?${libraryQueryString(filters, cursor)}`,
    { headers: { Accept: "application/json" }, signal: undefined },
  );
  if (!response.ok) throw new Error("Your library could not be loaded");
  return (await response.json()) as LibraryPage;
}

export async function patchEntry(
  entryId: number,
  changes: Partial<Pick<LibraryEntry, "score" | "status">>,
): Promise<LibraryEntry> {
  const response = await fetch(`/api/entries/${entryId}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok) throw new Error("Your change could not be saved");
  return (await response.json()) as LibraryEntry;
}
