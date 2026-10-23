import type { LibraryEntry } from "./library";
import { jsonOrApiError, readApiError, request } from "./request";

/** Two entries that look like one work entered twice (Sprint 113, DEC-176). */
export interface DuplicatePair {
  a: LibraryEntry;
  b: LibraryEntry;
  reason: string;
}

const json = { Accept: "application/json", "Content-Type": "application/json" };

export function getDuplicates(signal?: AbortSignal) {
  return request("/api/duplicates", { signal }).then((r) =>
    jsonOrApiError<DuplicatePair[]>(r, "Duplicates could not be found"),
  );
}

async function pair(method: "POST" | "DELETE", a: number, b: number) {
  const response = await request("/api/duplicates/dismiss", {
    method,
    headers: json,
    body: JSON.stringify({ a, b }),
  });
  if (!response.ok)
    throw await readApiError(response, "Your answer could not be saved");
}

/** These two differ: never offer them again. */
export const dismissDuplicate = (a: number, b: number) => pair("POST", a, b);
/** Take that answer back. */
export const undismissDuplicate = (a: number, b: number) =>
  pair("DELETE", a, b);

/** Fold `drop` into `keep`; nothing the owner wrote is lost. */
export function mergeEntries(keep: number, drop: number) {
  return request("/api/duplicates/merge", {
    method: "POST",
    headers: json,
    body: JSON.stringify({ keep, drop }),
  }).then((r) =>
    jsonOrApiError<LibraryEntry>(r, "The two could not be merged"),
  );
}
