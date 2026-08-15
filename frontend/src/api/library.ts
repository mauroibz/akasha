/**
 * The union of every domain's statuses, which is what a *filter* spans and what the
 * API can return for any row. Which of them a given entry may hold is its domain's
 * business, published per item type at `/api/item-types` (seam 5b, DEC-057).
 */
export const entryStatuses = [
  "unsorted",
  "read",
  "reading",
  "to_read",
  "wishlist",
  "dropped",
  "pending",
  "owned",
] as const;

/** The union of every domain's formats, for the same reason (DEC-059). */
export const entryFormats = [
  "physical",
  "borrowed",
  "digital",
  "vinyl",
  "cd",
] as const;

export type EntryStatus = (typeof entryStatuses)[number];
export type EntryFormat = (typeof entryFormats)[number];
export type SortKey =
  "date_added" | "score" | "title" | "creator" | "year" | "date_finished";
export type SortOrder = "asc" | "desc";

export interface Shelf {
  id: number;
  name: string;
  slug: string;
}

/** One cell of a `rows` field — a tracklist's position, title or length. */
export interface ColumnSpec {
  name: string;
  label: string;
  type: "text" | "number" | "duration";
}

/** One metadata field, as the domain that owns it describes it. */
export interface FieldSpec {
  name: string;
  label: string;
  type: "text" | "long_text" | "number" | "rows";
  multiplicity: "one" | "many";
  minimum?: number | null;
  maximum?: number | null;
  /** Present only on a `rows` field: what one row of it holds. */
  columns?: ColumnSpec[] | null;
}

/** One status a domain's entries can be in, with the key that sets it in triage. */
export interface StatusSpec {
  value: EntryStatus;
  label: string;
  choosable: boolean;
  hotkey: string | null;
}

export interface FormatSpec {
  value: EntryFormat;
  label: string;
}

export interface ItemType {
  id: string;
  label: string;
  fields: FieldSpec[];
  /**
   * The statuses this domain's entries can hold, in the order a control offers them.
   * An album is not a book with different words: `read` is not a state it can be in.
   */
  statuses: StatusSpec[];
  default_status: EntryStatus;
  /** Which of `date_started`, `date_finished`, `reread_count` this domain has. */
  entry_fields: string[];
  formats: FormatSpec[];
  /** The heading over the personal region of the detail page. */
  entry_panel_label: string;
}

/**
 * What each domain says its metadata fields are. Fetched once and cached: it changes
 * with a deployment, never with a library edit, so a screen renders whatever the
 * server declares instead of hardcoding one domain's vocabulary (DEC-052 seam 3).
 */
export async function getItemTypes(): Promise<ItemType[]> {
  const response = await fetch("/api/item-types", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Item types could not be loaded");
  return response.json() as Promise<ItemType[]>;
}

/** The edition. Shared by everyone who owns it; never carries opinion data. */
export interface LibraryItem {
  id: number;
  type: string;
  title: string;
  subtitle: string | null;
  year: number | null;
  creator: string | null;
  /** The name this edition sorts under: "García Márquez, Gabriel". */
  creator_sort?: string | null;
  /** Set only when the owner corrected it; absent means the automatic value. */
  creator_sort_override?: string | null;
  cover_url?: string | null;
  cover_path?: string | null;
  /** Opaque: what is in here is the domain's business, not this type's. */
  metadata: Record<string, unknown>;
  identifiers: Record<string, string>;
  sources: Array<{ source: string; source_id: string; is_primary: boolean }>;
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
  item: LibraryItem;
  shelves: Shelf[];
  /** How you hold this copy, in the domain's declared order (DEC-059). */
  formats: EntryFormat[];
}

export interface LibraryPage {
  items: LibraryEntry[];
  next_cursor: string | null;
  total: number;
  facets: {
    /** Whole-library totals: what the inbox badge counts. */
    status_counts: Partial<Record<EntryStatus, number>>;
    /** The same counts per item type, for a screen that lists domains separately. */
    status_counts_by_type: Record<string, Partial<Record<EntryStatus, number>>>;
    format_counts: Partial<Record<EntryFormat, number>>;
  };
}

export interface LibraryFilters {
  statuses: EntryStatus[];
  shelves: string[];
  formats: EntryFormat[];
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
  filters.formats.forEach((format) => params.append("format", format));
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (cursor) params.set("after", cursor);
  return params.toString();
}

/**
 * The `signal` is TanStack Query's, and passing it is the whole point: changing
 * a filter or sort abandons the previous key, and without a signal the browser
 * kept fetching a page nobody would render, holding one of six connections
 * while the user typed the next character (technical spec section 8).
 */
export async function getLibraryPage(
  filters: LibraryFilters,
  cursor?: string,
  signal?: AbortSignal,
): Promise<LibraryPage> {
  const response = await fetch(
    `/api/entries?${libraryQueryString(filters, cursor)}`,
    { headers: { Accept: "application/json" }, signal },
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
  > & { shelf_ids?: number[]; formats?: EntryFormat[] },
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
  if (!response.ok) throw new Error("Detail could not be loaded");
  return response.json() as Promise<LibraryEntry>;
}

export async function patchItem(
  itemId: number,
  changes: {
    title?: string;
    subtitle?: string | null;
    year?: number | null;
    /** Null drops the correction and goes back to the automatic sort name. */
    creator_sort_override?: string | null;
    metadata?: Record<string, unknown>;
  },
): Promise<LibraryEntry["item"]> {
  const response = await fetch(`/api/items/${itemId}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok) throw new Error("Metadata could not be saved");
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

export interface CoverCandidate {
  cover_url: string;
  source_id: string;
  title: string;
  year: number | null;
}

export interface CoverCandidates {
  candidates: CoverCandidate[];
  reason: string | null;
}

/** Other editions of this work, offered as covers. Fetched only when a chooser opens. */
export async function fetchCoverCandidates(
  itemId: number,
): Promise<CoverCandidates> {
  const response = await fetch(`/api/items/${itemId}/cover-candidates`);
  if (!response.ok) throw new Error("Cover options could not be loaded");
  return response.json() as Promise<CoverCandidates>;
}

export async function chooseCover(
  itemId: number,
  coverUrl: string,
): Promise<LibraryEntry["item"]> {
  const response = await fetch(`/api/items/${itemId}/cover`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ cover_url: coverUrl }),
  });
  if (!response.ok)
    throw new Error(
      "Cover could not be changed; the previous cover is unchanged",
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
  add_formats?: EntryFormat[];
  remove_formats?: EntryFormat[];
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

export interface Attachment {
  id: number;
  filename: string;
  byte_size: number;
  sha256: string;
  created_at: string;
}

export async function fetchAttachments(itemId: number): Promise<Attachment[]> {
  const response = await fetch(`/api/items/${itemId}/attachments`);
  if (!response.ok) throw new Error("Files could not be loaded");
  const body = (await response.json()) as { attachments: Attachment[] };
  return body.attachments;
}

/**
 * Upload one opaque file.
 *
 * The size cap is the server's to enforce, not ours: a client-side check is a
 * courtesy that a request built by hand walks straight past. This surfaces the
 * server's own refusal so the message the owner reads is the real reason.
 */
export async function uploadAttachment(
  itemId: number,
  file: File,
): Promise<Attachment> {
  const body = new FormData();
  body.set("file", file);
  const response = await fetch(`/api/items/${itemId}/attachments`, {
    method: "POST",
    headers: { Accept: "application/json" },
    body,
  });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null)) as {
      error?: { code?: string };
    } | null;
    throw new Error(
      detail?.error?.code === "attachment_too_large"
        ? "That file is larger than the limit for attachments"
        : "The file could not be attached",
    );
  }
  return response.json() as Promise<Attachment>;
}

/**
 * Rename an attached file.
 *
 * The name is metadata, so this moves no bytes and the download URL does not
 * change. What does change is the name the server sends the file under, which
 * is why the response carries a fresh validator.
 */
export async function renameAttachment(
  itemId: number,
  attachmentId: number,
  filename: string,
): Promise<Attachment> {
  const response = await fetch(
    `/api/items/${itemId}/attachments/${attachmentId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    },
  );
  if (!response.ok) throw new Error("The file could not be renamed");
  return response.json() as Promise<Attachment>;
}

export async function deleteAttachment(
  itemId: number,
  attachmentId: number,
): Promise<void> {
  const response = await fetch(
    `/api/items/${itemId}/attachments/${attachmentId}`,
    { method: "DELETE" },
  );
  if (!response.ok) throw new Error("The file could not be removed");
}

/** Where a browser fetches the bytes. Served as a forced download, never inline. */
export function attachmentHref(itemId: number, attachmentId: number): string {
  return `/api/items/${itemId}/attachments/${attachmentId}`;
}
