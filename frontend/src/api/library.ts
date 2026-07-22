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
    cover_url?: string | null;
    cover_path?: string | null;
    metadata: {
      authors?: string[];
      publisher?: string | null;
      language?: string | null;
      page_count?: number | null;
      description?: string | null;
      subjects?: string[];
      series?: string | null;
      original_year?: number | null;
    };
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
  changes: Partial<
    Pick<
      LibraryEntry,
      | "score"
      | "status"
      | "notes"
      | "date_started"
      | "date_finished"
      | "reread_count"
    >
  > & { shelf_ids?: number[] },
): Promise<LibraryEntry> {
  const response = await fetch(`/api/entries/${entryId}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok) throw new Error("Your change could not be saved");
  return (await response.json()) as LibraryEntry;
}

export async function getEntry(entryId: number): Promise<LibraryEntry> {
  const response = await fetch(`/api/entries/${entryId}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Book detail could not be loaded");
  return response.json() as Promise<LibraryEntry>;
}

export async function patchItem(
  itemId: number,
  changes: {
    title?: string;
    subtitle?: string | null;
    year?: number | null;
    metadata?: Partial<LibraryEntry["item"]["metadata"]>;
  },
): Promise<LibraryEntry["item"]> {
  const response = await fetch(`/api/items/${itemId}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok) throw new Error("Book metadata could not be saved");
  return response.json() as Promise<LibraryEntry["item"]>;
}

export async function refreshItem(
  itemId: number,
): Promise<LibraryEntry["item"]> {
  const response = await fetch(`/api/items/${itemId}/refresh`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ overwrite: true }),
  });
  if (!response.ok)
    throw new Error("Provider refresh failed; your metadata was not changed");
  return response.json() as Promise<LibraryEntry["item"]>;
}

export async function replaceCover(
  itemId: number,
  cover: File,
): Promise<LibraryEntry["item"]> {
  const body = new FormData();
  body.set("cover", cover);
  const response = await fetch(`/api/items/${itemId}/cover`, {
    method: "POST",
    headers: { Accept: "application/json" },
    body,
  });
  if (!response.ok)
    throw new Error(
      "Cover could not be replaced; the previous cover is unchanged",
    );
  return response.json() as Promise<LibraryEntry["item"]>;
}

export async function deleteEntry(entryId: number): Promise<void> {
  const response = await fetch(`/api/entries/${entryId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Entry could not be deleted");
}

export interface BulkSet {
  status?: EntryStatus;
  score?: number;
  add_shelves?: number[];
  remove_shelves?: number[];
  clear_provisional?: boolean;
}

export interface BulkBody {
  entry_ids?: number[];
  filter?: {
    status?: EntryStatus[];
    shelf?: string[];
    q?: string;
  };
  excluded_entry_ids?: number[];
  set: BulkSet;
}

export async function bulkUpdateEntries(body: BulkBody): Promise<number> {
  const response = await fetch("/api/entries/bulk", {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error("Bulk update failed");
  const data = (await response.json()) as { affected: number };
  return data.affected;
}

export async function acceptSuggestedStatuses(filter: {
  status?: EntryStatus[];
  shelf?: string[];
  q?: string;
}): Promise<number> {
  const response = await fetch("/api/entries/accept-suggested", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ filter }),
  });
  if (!response.ok) throw new Error("Could not accept suggested statuses");
  const data = (await response.json()) as { affected: number };
  return data.affected;
}
