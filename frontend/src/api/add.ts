import type { EntryStatus, LibraryEntry, Shelf } from "./library";

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
  authors: string[];
  year: number | null;
  cover_url: string | null;
  identifiers: Record<string, string>;
  language: string | null;
  metadata: Record<string, unknown>;
}
export interface ManualItem {
  title: string;
  subtitle?: string;
  authors: string[];
  year?: number;
  publisher?: string;
  language?: string;
  isbn?: string;
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
export function searchBooks(value: string) {
  const resolved = /^(https?:\/\/|[\dXx -]{10,17}$)/.test(value.trim());
  const route = resolved
    ? `/api/search/resolve?url=${encodeURIComponent(value.trim())}`
    : `/api/search?q=${encodeURIComponent(value.trim())}`;
  return fetch(route, { headers: { Accept: "application/json" } }).then(
    async (response) => ({
      items: await json<SearchCandidate[]>(
        response,
        "Metadata providers are unavailable",
      ),
      warning: response.headers.get("X-Provider-Warning"),
    }),
  );
}
export function getShelves() {
  return fetch("/api/shelves").then((r) =>
    json<Shelf[]>(r, "Shelves could not be loaded"),
  );
}
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
    return json<CreateEntryResponse>(response, "Book could not be added");
  });
}
