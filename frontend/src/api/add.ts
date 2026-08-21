import type { EntryStatus, LibraryEntry } from "./library";

export interface SourceRef {
  source: string;
  source_id: string;
}
export interface SearchCandidate {
  source: string;
  source_id: string;
  source_refs: SourceRef[];
  title: string;
  subtitle: string | null;
  creators: string[];
  /** The credit as the source renders it, when it renders one. */
  credit: string | null;
  year: number | null;
  original_year?: number | null;
  cover_url: string | null;
  identifiers: Record<string, string>;
  language: string | null;
  metadata: Record<string, unknown>;
}
/**
 * One candidate's full record, fetched on demand and writing nothing.
 *
 * A search result carries an identity — title, creators, year, language, ISBNs —
 * but not a description, a page count or a tracklist. Those come from the per-item
 * fetch that used to run only at add time, so the confirm screen had nothing to
 * show. One provider request per call, which is why it is a button and not an
 * effect.
 */
export async function previewCandidate(
  source: string,
  sourceId: string,
  signal?: AbortSignal,
): Promise<SearchCandidate> {
  const params = new URLSearchParams({ source, source_id: sourceId });
  const response = await fetch(`/api/search/preview?${params.toString()}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok)
    throw new Error("The full record could not be loaded from the provider");
  return (await response.json()) as SearchCandidate;
}

export interface ManualItem {
  item_type: string;
  title: string;
  subtitle?: string;
  year?: number;
  metadata: Record<string, unknown>;
  identifiers?: Record<string, string>;
}
export interface CreateEntryResponse {
  entry: LibraryEntry;
  already_exists: boolean;
  near_matches: number[];
}
export class NearMatchError extends Error {
  constructor(public entryIds: number[]) {
    super("A similar edition is already in your library");
  }
}

async function json<T>(response: Response, message: string): Promise<T> {
  if (!response.ok) throw new Error(message);
  return response.json() as Promise<T>;
}
/**
 * `itemType` decides which providers are asked. It is not cosmetic: a search never
 * reaches a provider that serves another domain, so looking for an album spends no
 * Google Books quota and looking for a book spends no MusicBrainz request.
 */
export function searchCandidates(
  value: string,
  itemType: string,
  signal?: AbortSignal,
) {
  const resolved = /^(https?:\/\/|[\dXx -]{10,17}$)/.test(value.trim());
  const route = resolved
    ? `/api/search/resolve?url=${encodeURIComponent(value.trim())}`
    : `/api/search?q=${encodeURIComponent(value.trim())}&type=${encodeURIComponent(itemType)}`;
  return fetch(route, { headers: { Accept: "application/json" }, signal }).then(
    async (response) => ({
      items: await json<SearchCandidate[]>(
        response,
        "Metadata providers are unavailable",
      ),
      warning: response.headers.get("X-Provider-Warning"),
    }),
  );
}
export { getShelves, createShelf } from "./shelves";
export function createEntry(body: {
  manual?: ManualItem;
  source?: string;
  source_id?: string;
  source_refs?: SourceRef[];
  status: EntryStatus;
  score?: number;
  shelf_ids: number[];
  idempotency_key?: string;
  confirm_near_match?: boolean;
}) {
  return fetch("/api/entries", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (response) => {
    if (response.status === 409) {
      const value = (await response.json()) as {
        error?: { code?: string; details?: { entry_ids?: number[] } };
      };
      if (value.error?.code === "near_match_confirmation_required")
        throw new NearMatchError(value.error.details?.entry_ids ?? []);
    }
    // Neutral rather than the domain's label: this layer has no registry to ask,
    // and AddForm names the domain when it has one to name.
    return json<CreateEntryResponse>(response, "That could not be added");
  });
}
