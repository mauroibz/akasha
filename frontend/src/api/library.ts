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
  /** Under way: what the library's Now strip shows (Sprint 098). */
  in_progress?: boolean;
  /** Waiting to be started: where a goal's picks come from (Sprint 103). */
  planned?: boolean;
  /** Stopped partway: setting it asks how far it got (DEC-172). */
  abandoned?: boolean;
  /** Done with: finishing again asks whether the score holds (Sprint 115). */
  finished?: boolean;
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
  /**
   * A `rows` field of parts and their sizes — a series' seasons — when the domain has
   * one (DEC-171). Absent or empty on an item, the outline is one part of the total.
   */
  parts_field?: string | null;
}

/** One part of what progress marks are drawn against: a season and its episodes. */
export interface OutlinePart {
  part: number;
  size: number;
}

/** Which episodes or chapters are done, by part: `{"1": [1, 2, 3]}`. */
export type ProgressMarks = Record<string, number[]>;

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
   * The label counted: "Books", "Anime" (Sprint 102). Optional on the client so a
   * stub written before it existed still renders; `countLabel` falls back.
   */
  plural_label?: string;
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
  const response = await request("/api/item-types", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await apiFailure(response, "Item types could not be loaded");
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
  /** Opaque: what is in here is the domain's business, not this type's. */
  metadata: Record<string, unknown>;
  /** What progress marks are drawn against; absent where nothing says how many. */
  outline?: OutlinePart[] | null;
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
  /** Which episodes or chapters were ticked; when present, `progress` is their count. */
  progress_marks?: ProgressMarks | null;
  score_provisional: boolean;
  suggested_status: EntryStatus | null;
  item: LibraryItem;
  shelves: Shelf[];
  /** How you hold this copy, in the domain's declared order (DEC-059). */
  formats: EntryFormat[];
  /** Where it is kept, in the owner's words (Sprint 110). */
  location?: string | null;
  /** Place among the entries sharing its score, 1 the best (Sprint 116). */
  score_rank?: number | null;
  /** The loan that is out now, if any. */
  loan?: Loan | null;
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
  /** Only what is kept here, as written (Sprint 111). Absent means anywhere. */
  location?: string;
  /** Only what is out on loan now. */
  lent?: boolean;
  /** `missing`: only what has no cover (Sprint 112's *Find a cover*). */
  cover?: "missing";
  /** Only entries with exactly this score (Sprint 116's ranking). */
  score?: number;
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
  if (filters.location) params.set("location", filters.location);
  if (filters.lent) params.set("lent", "true");
  if (filters.cover) params.set("cover", filters.cover);
  if (filters.score) params.set("score", String(filters.score));
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
  const response = await request(
    `/api/entries?${libraryQueryString(filters, cursor, limit)}`,
    { headers: { Accept: "application/json" }, signal },
  );
  if (!response.ok)
    throw await apiFailure(response, "Your library could not be loaded");
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
  /** Up to three cover URLs from this row's own members, highest scored first. */
  covers: string[];
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
  /** The ranked set's own totals — independent of `key`, not a sum of rows. */
  total_entries: number;
  rated_entries: number;
}

export async function getInsights(params: {
  type: string;
  key: string;
  metric: "count" | "score";
  minRated?: number;
  includeSuppressed?: boolean;
  /** Rank inside the library's current filters (Sprint 067), off by default. */
  statuses?: EntryStatus[];
  shelves?: string[];
  formats?: EntryFormat[];
  q?: string;
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
  params.statuses?.forEach((status) => query.append("status", status));
  params.shelves?.forEach((shelf) => query.append("shelf", shelf));
  params.formats?.forEach((format) => query.append("format", format));
  if (params.q?.trim()) query.set("q", params.q.trim());
  if (params.after) query.set("after", params.after);
  const response = await request(`/api/insights?${query.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await apiFailure(response, "Insights could not be loaded");
  return (await response.json()) as Insight;
}

/** Per-score counts for one domain (Sprint 073), the score distribution band. */
export interface ScoreDistribution {
  type: string;
  /** Index `i` is the count of entries scored `i + 1`. Always length 10. */
  counts: number[];
  rated_count: number;
  unrated_count: number;
}

export async function getScoreDistribution(params: {
  type: string;
  statuses?: EntryStatus[];
  shelves?: string[];
  formats?: EntryFormat[];
  q?: string;
}): Promise<ScoreDistribution> {
  const query = new URLSearchParams({ type: params.type });
  params.statuses?.forEach((status) => query.append("status", status));
  params.shelves?.forEach((shelf) => query.append("shelf", shelf));
  params.formats?.forEach((format) => query.append("format", format));
  if (params.q?.trim()) query.set("q", params.q.trim());
  const response = await request(`/api/insights/scores?${query.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await apiFailure(response, "Insights could not be loaded");
  return (await response.json()) as ScoreDistribution;
}

/** The figures the insights page's lead sentence reads (Sprint 102). */
export type InsightSummary = components["schemas"]["InsightSummaryResponse"];

export async function getInsightSummary(params: {
  type: string;
  statuses?: EntryStatus[];
  shelves?: string[];
  formats?: EntryFormat[];
  q?: string;
}): Promise<InsightSummary> {
  const query = new URLSearchParams({ type: params.type });
  params.statuses?.forEach((status) => query.append("status", status));
  params.shelves?.forEach((shelf) => query.append("shelf", shelf));
  params.formats?.forEach((format) => query.append("format", format));
  if (params.q?.trim()) query.set("q", params.q.trim());
  const response = await request(`/api/insights/summary?${query.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await apiFailure(response, "Insights could not be loaded");
  return (await response.json()) as InsightSummary;
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
      | "progress_marks"
    >
  > & {
    shelf_ids?: number[];
    formats?: EntryFormat[];
    /** Qualifies `score`: write it back as provisional (Sprint 109). */
    score_provisional?: boolean;
    /** Where it is kept; blank clears it (Sprint 110). */
    location?: string | null;
    /** Why the score sent is what it is (Sprint 114). */
    score_reason?: "reread" | "time";
    score_note?: string;
  },
): Promise<LibraryEntry> {
  const response = await request(`/api/entries/${entryId}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok)
    throw await apiFailure(response, "Your change could not be saved");
  return (await response.json()) as LibraryEntry;
}

/**
 * Fetch a season list or chapter count the item has none of (DEC-171). An explicit
 * action: never called while drawing a page.
 */
export async function fetchOutline(itemId: number): Promise<LibraryItem> {
  const response = await request(`/api/items/${itemId}/outline`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await apiFailure(response, "The list could not be found");
  return (await response.json()) as LibraryItem;
}

/** Entries under way across every domain: the Now strip (Sprint 098). */
export async function getNow(signal?: AbortSignal): Promise<LibraryEntry[]> {
  const response = await request("/api/now", {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok)
    throw await apiFailure(
      response,
      "What you are in the middle of could not be loaded",
    );
  return response.json() as Promise<LibraryEntry[]>;
}

export interface DiaryMonth {
  month: string;
  counts: Record<string, number>;
  entries: LibraryEntry[];
}

export interface Diary {
  year: number;
  years: number[];
  months: DiaryMonth[];
}

/** What was finished in a year, by month (Sprint 098). */
export async function getDiary(
  year?: number,
  signal?: AbortSignal,
): Promise<Diary> {
  const response = await request(
    year ? `/api/diary?year=${year}` : "/api/diary",
    { headers: { Accept: "application/json" }, signal },
  );
  if (!response.ok)
    throw await apiFailure(response, "The diary could not be loaded");
  return response.json() as Promise<Diary>;
}

/** How many entries wait in the Inbox: the nav's Import badge (Sprint 096). */
export async function getInboxCount(signal?: AbortSignal): Promise<number> {
  const response = await request("/api/entries?status=unsorted&limit=1", {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok)
    throw await apiFailure(response, "The Inbox could not be counted");
  const page = (await response.json()) as { total?: number };
  return page.total ?? 0;
}

/** One item, as the import check shows an existing copy (Sprint 096). */
export async function getItem(itemId: number): Promise<LibraryItem> {
  const response = await request(`/api/items/${itemId}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await apiFailure(response, "That item could not be read");
  return response.json() as Promise<LibraryItem>;
}

/** Your entries for a query, best first: the command bar's library half (Sprint 094). */
export async function searchLibrary(
  q: string,
  signal?: AbortSignal,
): Promise<LibraryEntry[]> {
  const response = await request(
    `/api/search/library?q=${encodeURIComponent(q)}`,
    { headers: { Accept: "application/json" }, signal },
  );
  if (!response.ok)
    throw await apiFailure(response, "Your library could not be searched");
  return response.json() as Promise<LibraryEntry[]>;
}

/**
 * Move an entry into another library through that library's own record (Sprint 100).
 * The answer is the new entry: the old one, and its item, are gone.
 */
export async function refileEntry(
  entryId: number,
  candidate: Pick<SearchCandidate, "source" | "source_id" | "source_refs">,
): Promise<LibraryEntry> {
  const response = await request(`/api/entries/${entryId}/refile`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      source: candidate.source,
      source_id: candidate.source_id,
      source_refs: candidate.source_refs,
    }),
  });
  if (!response.ok)
    throw await apiFailure(response, "The entry could not be moved");
  return response.json() as Promise<LibraryEntry>;
}

export async function getEntry(entryId: number): Promise<LibraryEntry> {
  const response = await request(`/api/entries/${entryId}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await apiFailure(response, "Detail could not be loaded");
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
  const response = await request(`/api/items/${itemId}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok)
    throw await apiFailure(response, "Metadata could not be saved");
  return response.json() as Promise<LibraryEntry["item"]>;
}

/**
 * Refresh and cover fetch surface the server's own refusal, so the owner reads why
 * rather than one canned sentence for every cause — a provider outage, a disabled
 * provider, and an item with no provider source all want a different next step.
 */
/** What `POST /api/items/{id}/fill` answers (Sprint 109). */
export type FillResult = {
  item: LibraryEntry["item"];
  /** Field names written; `cover` when a cover was installed. */
  filled: string[];
  /** The provider asked, as a person reads its name. */
  provider: string | null;
  /** Background lookups queued, for an item with no provider to ask directly. */
  queued: number;
};

/**
 * Fill the item's empty fields from its provider, never replacing a value.
 *
 * The non-destructive sibling of `refreshItem`, so it asks for no confirmation.
 */
export async function fillItem(itemId: number): Promise<FillResult> {
  const response = await request(`/api/items/${itemId}/fill`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await readApiError(
      response,
      "The provider could not be reached; nothing was changed",
    );
  return response.json() as Promise<FillResult>;
}

export async function refreshItem(
  itemId: number,
): Promise<LibraryEntry["item"]> {
  const response = await request(`/api/items/${itemId}/refresh`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ overwrite: true }),
  });
  if (!response.ok)
    throw await readApiError(
      response,
      "Provider refresh failed; your metadata was not changed",
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
  const response = await request(`/api/items/${itemId}/cover/fetch`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await readApiError(response, "Cover could not be fetched");
  return response.json() as Promise<LibraryEntry["item"]>;
}

export async function replaceCover(
  itemId: number,
  cover: File,
): Promise<LibraryEntry["item"]> {
  const body = new FormData();
  body.set("cover", cover);
  const response = await request(`/api/items/${itemId}/cover`, {
    method: "POST",
    headers: { Accept: "application/json" },
    body,
  });
  if (!response.ok)
    throw await apiFailure(
      response,
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
  const response = await request(`/api/items/${itemId}/cover-candidates`);
  if (!response.ok)
    throw await apiFailure(response, "Cover options could not be loaded");
  return response.json() as Promise<CoverCandidates>;
}

export async function chooseCover(
  itemId: number,
  coverUrl: string,
): Promise<LibraryEntry["item"]> {
  const response = await request(`/api/items/${itemId}/cover`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ cover_url: coverUrl }),
  });
  if (!response.ok)
    throw await apiFailure(
      response,
      "Cover could not be changed; the previous cover is unchanged",
    );
  return response.json() as Promise<LibraryEntry["item"]>;
}

export async function deleteEntry(entryId: number): Promise<void> {
  const response = await request(`/api/entries/${entryId}`, {
    method: "DELETE",
  });
  if (!response.ok)
    throw await apiFailure(response, "Entry could not be deleted");
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

export interface BulkSelection {
  entry_ids?: number[];
  filter?: {
    status?: EntryStatus[];
    shelf?: string[];
    q?: string;
  };
  excluded_entry_ids?: number[];
}

export interface BulkBody extends BulkSelection {
  set: BulkSet;
}

export async function bulkUpdateEntries(body: BulkBody): Promise<number> {
  const response = await request("/api/entries/bulk", {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await apiFailure(response, "Bulk update failed");
  const data = (await response.json()) as { affected: number };
  return data.affected;
}

export async function bulkDeleteEntries(body: BulkSelection): Promise<number> {
  const response = await request("/api/entries/bulk", {
    method: "DELETE",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await apiFailure(response, "Bulk delete failed");
  const data = (await response.json()) as { affected: number };
  return data.affected;
}

export async function acceptSuggestedStatuses(filter: {
  status?: EntryStatus[];
  shelf?: string[];
  q?: string;
}): Promise<number> {
  const response = await request("/api/entries/accept-suggested", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ filter }),
  });
  if (!response.ok)
    throw await apiFailure(response, "Could not accept suggested statuses");
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
  const response = await request(`/api/items/${itemId}/attachments`);
  if (!response.ok)
    throw await apiFailure(response, "Files could not be loaded");
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
  const response = await request(`/api/items/${itemId}/attachments`, {
    method: "POST",
    headers: { Accept: "application/json" },
    body,
  });
  if (!response.ok) {
    const fields = await readErrorFields(
      response,
      "The file could not be attached",
    );
    throw new ApiError(
      fields.code === "attachment_too_large"
        ? "That file is larger than the limit for attachments"
        : "The file could not be attached",
      fields.code,
      fields,
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
  const response = await request(
    `/api/items/${itemId}/attachments/${attachmentId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    },
  );
  if (!response.ok)
    throw await apiFailure(response, "The file could not be renamed");
  return response.json() as Promise<Attachment>;
}

export async function deleteAttachment(
  itemId: number,
  attachmentId: number,
): Promise<void> {
  const response = await request(
    `/api/items/${itemId}/attachments/${attachmentId}`,
    { method: "DELETE" },
  );
  if (!response.ok)
    throw await apiFailure(response, "The file could not be removed");
}

/** Where a browser fetches the bytes. Served as a forced download, never inline. */
export function attachmentHref(itemId: number, attachmentId: number): string {
  return `/api/items/${itemId}/attachments/${attachmentId}`;
}
import {
  ApiError,
  apiFailure,
  readApiError,
  readErrorFields,
  request,
} from "./request";
import type { SearchCandidate } from "./add";
import type { Loan } from "./loans";
import type { components } from "./schema";

/** One change of a score: what it became, from what, why and when (Sprint 114). */
export interface ScoreEvent {
  score: number | null;
  previous: number | null;
  /** `null` for a first score, else `time` or `reread`. */
  reason: "time" | "reread" | null;
  note: string | null;
  recorded_at: string;
}

export async function getScoreHistory(
  entryId: number,
  signal?: AbortSignal,
): Promise<ScoreEvent[]> {
  const response = await request(`/api/entries/${entryId}/score-history`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok)
    throw await apiFailure(response, "The score history could not be loaded");
  return response.json() as Promise<ScoreEvent[]>;
}

/** Put entries that share a score in this order, best first (Sprint 116). */
export async function rankEntries(entryIds: number[]): Promise<LibraryEntry[]> {
  const response = await request("/api/entries/rank", {
    method: "PUT",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ entry_ids: entryIds }),
  });
  if (!response.ok)
    throw await apiFailure(response, "The order could not be saved");
  return response.json() as Promise<LibraryEntry[]>;
}

/** One thing that happened: an entry finished, or its score changed (Sprint 118). */
export interface TimelineEvent {
  kind: "finished" | "score";
  /** A day for a finish; when the change was recorded for a score. */
  at: string;
  entry: LibraryEntry;
  score: number | null;
  previous?: number | null;
  reason?: "time" | "reread" | null;
  note?: string | null;
}

export interface Timeline {
  events: TimelineEvent[];
  next_cursor: string | null;
}

export async function getTimeline(
  before?: string,
  signal?: AbortSignal,
): Promise<Timeline> {
  const params = new URLSearchParams({ limit: "60" });
  if (before) params.set("before", before);
  const response = await request(`/api/diary/timeline?${params}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok)
    throw await apiFailure(response, "The timeline could not be loaded");
  return response.json() as Promise<Timeline>;
}
