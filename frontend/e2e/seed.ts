import type { Page } from "@playwright/test";

/**
 * The deterministic library fixture every large-list test runs against.
 *
 * Lives here rather than in one spec because the accessibility suite, the
 * virtualization bounds and the motion samples all need the same shape, and
 * three near-copies of it would drift.
 */

export const pixelCover =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

const longTitle =
  "A Ludicrously Long Title About The Consequences Of Unbounded Metadata In Virtualized Grids And Their Discontents";
const longAuthor =
  "Vandermeer-Vandermeer de la Fuente y Castellanos de Arag\u00f3n, Mar\u00eda Purificaci\u00f3n";

export function entry(id: number) {
  return {
    id,
    item_id: id,
    status: "read",
    score: (id % 10) + 1,
    notes: null,
    date_added: "2026-07-22T00:00:00Z",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    score_provisional: id % 3 === 0,
    suggested_status: null,
    item: {
      id,
      type: "book",
      // The first two entries carry deliberately hostile metadata so layout
      // assertions cover long titles/authors, and every other entry carries a
      // real cover so both populated and empty covers are exercised.
      title:
        id <= 2
          ? `${longTitle} ${String(id).padStart(4, "0")}`
          : `Seeded book ${String(id).padStart(4, "0")}`,
      subtitle: null,
      year: 1900 + (id % 126),
      sort_author: id <= 2 ? longAuthor : `Author ${id % 200}`,
      cover_url: id % 2 === 0 ? pixelCover : null,
      cover_path: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    shelves: [],
  };
}

export async function seedLibrary(page: Page, count = 5000) {
  const items = Array.from({ length: count }, (_, index) => entry(index + 1));
  await page.route("**/api/entries?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items,
        next_cursor: null,
        total: count,
        facets: { status_counts: { read: count, unsorted: 27 } },
      }),
    });
  });
}
