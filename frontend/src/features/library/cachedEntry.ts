import type { QueryClient } from "@tanstack/react-query";

import type { LibraryEntry, LibraryPage } from "@/api/library";

/** The lists an entry is opened from: the library, the Inbox, a shelf. */
const LIST_ROOTS = ["library", "triage", "shelf-entries"];

/**
 * The copy of one entry that a list already holds, if any (Sprint 092).
 *
 * Every list is a page of the same `EntryResponse` the detail read returns, so the
 * detail page can draw from it while its own read is in flight.
 */
export function cachedEntry(
  client: QueryClient,
  entryId: number,
): LibraryEntry | undefined {
  for (const root of LIST_ROOTS) {
    for (const [, data] of client.getQueriesData<{ pages?: LibraryPage[] }>({
      queryKey: [root],
    })) {
      for (const page of data?.pages ?? []) {
        const found = page.items.find((row) => row.id === entryId);
        if (found) return found;
      }
    }
  }
  return undefined;
}

/**
 * The name a cover carries on both the library card and the detail page, so the
 * browser's view transition morphs one into the other. Unique per entry.
 */
export function coverTransitionName(entryId: number): string {
  return `cover-${entryId}`;
}
