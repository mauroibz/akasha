import type { Page } from "@playwright/test";

import { bookItemType } from "./seed";

/** Five books sharing an 8, one already placed, as Sprint 116's API answers. */
export function rankEntry(id: number, title: string, rank: number | null) {
  return {
    id,
    item_id: id,
    status: "read",
    score: 8,
    score_rank: rank,
    notes: null,
    date_added: "2024-01-01",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: null,
    score_provisional: false,
    suggested_status: null,
    shelves: [],
    formats: [],
    item: {
      id,
      type: "book",
      title,
      subtitle: null,
      year: 1960 + id,
      creator: "Someone",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
  };
}

export async function stubRank(page: Page, puts: unknown[] = []) {
  const entries = [
    rankEntry(1, "Stoner", 1),
    rankEntry(2, "Solaris", null),
    rankEntry(3, "Ficciones", null),
    rankEntry(4, "The Dispossessed: An Ambiguous Utopia", null),
    rankEntry(5, "Piranesi", null),
  ];
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [bookItemType] }),
  );
  await page.route("**/api/insights/scores**", (route) =>
    route.fulfill({
      json: {
        type: "book",
        counts: [0, 0, 0, 0, 0, 0, 2, 5, 1, 0],
        rated_count: 8,
        unrated_count: 0,
      },
    }),
  );
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: {
          status_counts: {},
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/rank", (route) => {
    puts.push(route.request().postDataJSON());
    return route.fulfill({ json: [] });
  });
}
