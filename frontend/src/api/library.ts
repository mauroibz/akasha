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
  "watching",
  "completed",
  "on_hold",
  "plan_to_watch",
  "watchlist",
  "watched",
] as const;

/** The union of every domain's formats, for the same reason (DEC-059). */
export const entryFormats = [
  "physical",
  "borrowed",
  "digital",
  "vinyl",
  "cd",
  "streaming",
  "bluray",
  "dvd",
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
  /** Whether an insights ranking may group by this field. */
  groupable?: boolean;
}

/** One status a domain's entries can be in, with the key that sets it in triage. */
export interface StatusSpec {
  value: EntryStatus;
  label: string;
  choosable: boolean;
  hotkey: string | null;
}

/** How a domain counts progress, when that means something to it (DEC-077). */
export interface ProgressSpec {
  label: string;
  unit_label: string;
  /**
   * A `number` metadata field on the item holding the total, for reading "20 / 170".
   * Display only — never a bound, because a cached total goes stale and an airing
   * series has none at all.
   */
  total_field: string | null;
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
  /**
   * What this domain calls those fields, where a neutral word is wrong: an anime has
   * rewatches, not rereads. Partial — anything absent uses the neutral label below.
   */
  entry_field_labels: Record<string, string>;
  /** How far through one of these you are, or `null` where that means nothing. */
  progress: ProgressSpec | null;
  formats: FormatSpec[];
  /** The heading over the personal region of the detail page. */
  entry_panel_label: string;
  /**
   * Whether to offer the cover chooser (DEC-067 row 7). The shared chooser is Open
   * Library's work-editions path, so a domain it does not serve declares `false` and
   * the control is not rendered rather than rendered and unable to answer.
   */
  chooses_covers: boolean;
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
  /** `null` is *not recorded*, which is a different fact from a recorded `0`. */
  progress: number | null;
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
  /** Which domains to show. Empty means every one of them. */
  types: string[];
  query: string;
  sort: SortKey;
  order: SortOrder;
  /**
   * A precise metadata (or `year`/`decade`) filter (Sprint 065) — how an insights
   * ranking row links back to the library. Both empty, or both set: a value with no
   * key (or vice versa) is not a filter that means anything.
   */
  key: string;
  value: string;
  /**
   * How to *say* `value`, which is normalized — case folded, diacritics
   * stripped — because that is what groups a ranking row. "julio cortazar" is
   * the filter; "Julio Cortázar" is the name, and the breadcrumb has to show
   * the name. Display only: `libraryQueryString` never sends it, and its
   * absence just means the breadcrumb falls back to the normalized value.
   */
  valueLabel: string;
}

export function libraryQueryString(
  filters: LibraryFilters,
  cursor?: string,
  /** The library's own page size, unless a caller wants a handful (Sprint 066). */
  limit = 100,
) {
  const params = new URLSearchParams({
    sort: filters.sort,
    order: filters.order,
    limit: String(limit),
  });
  filters.statuses.forEach((status) => params.append("status", status));
  filters.shelves.forEach((shelf) => params.append("shelf", shelf));
  filters.formats.forEach((format) => params.append("format", format));
  filters.types.forEach((type) => params.append("type", type));
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (filters.key && filters.value) {
    params.set("key", filters.key);
    params.set("value", filters.value);
  }
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
  limit?: number,
): Promise<LibraryPage> {
  const response = await fetch(
    `/api/entries?${libraryQueryString(filters, cursor, limit)}`,
    { headers: { Accept: "application/json" }, signal },
  );
  if (!response.ok) throw new Error("Your library could not be loaded");
  return (await response.json()) as LibraryPage;
}

/** One ranked row: a groupable key's value, and what the library says about it. */
export interface InsightRow {
  /** The normalized grouping value — pass straight through as `value` on `/`. */
  key: string;
  /** The commonest original spelling among this row's members. */
  label: string;
  count: number;
  rated_count: number;
  mean_score: number | null;
  score_spread: number | null;
}

export interface InsightSuppressed {
  key: string;
  label: string;
  count: number;
}

export interface Insight {
  type: string;
  key: string;
  metric: "count" | "score";
  min_rated: number;
  rows: InsightRow[];
  next_cursor: string | null;
  /** What a ranking left out by default — reported rather than silently shrunk. */
  suppressed: InsightSuppressed[];
  /** `metric="score"` and every group failed `min_rated` — distinct from "nothing to rank". */
  no_rated_groups: boolean;
  /** Entries excluded from a `year`/`decade` ranking for having no year. */
  null_count: number;
}

export async function getInsights(params: {
  type: string;
  key: string;
  metric: "count" | "score";
  minRated?: number;
  includeSuppressed?: boolean;
  limit?: number;
  after?: string;
}): Promise<Insight> {
  const query = new URLSearchParams({
    type: params.type,
    key: params.key,
    metric: params.metric,
  });
  if (params.limit) query.set("limit", String(params.limit));
  if (params.minRated) query.set("min_rated", String(params.minRated));
  if (params.includeSuppressed) query.set("include_suppressed", "true");
  if (params.after) query.set("after", params.after);
  const response = await fetch(`/api/insights?${query.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Insights could not be loaded");
  return (await response.json()) as Insight;
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
      | "progress"
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

/**
 * The server's own refusal, so the owner reads why rather than one canned
 * sentence for every cause — a provider outage, a disabled provider, and an
 * item with no provider source all want a different next step.
 */
async function providerErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  const detail = (await response.json().catch(() => null)) as {
    error?: { message?: string; user_message?: string };
  } | null;
  return detail?.error?.user_message ?? detail?.error?.message ?? fallback;
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
    throw new Error(
      await providerErrorMessage(
        response,
        "Provider refresh failed; your metadata was not changed",
      ),
    );
  return response.json() as Promise<LibraryEntry["item"]>;
}

/**
 * Install a cover from the item's own provider, and nothing else.
 *
 * `Refresh from provider` already does this as a side effect, but only after
 * overwriting every other field and behind a confirmation dialog — the wrong
 * shape for the one case this exists for: a cover that never installed (a
 * transient failure, a since-fixed outage) and nothing else wrong.
 */
export async function fetchProviderCover(
  itemId: number,
): Promise<LibraryEntry["item"]> {
  const response = await fetch(`/api/items/${itemId}/cover/fetch`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw new Error(
      await providerErrorMessage(response, "Cover could not be fetched"),
    );
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
