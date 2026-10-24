import type { Page } from "@playwright/test";

import { bookType } from "./progress-fixture";
import { stubImporters } from "./seed";

/**
 * The deck's chores (Sprint 112), stubbed as the API answers them: a planned pile
 * across two domains and a book without a cover with two editions to choose from.
 * Shared by the chores spec and the accessibility suite.
 */

/** Two editions' covers at a size the server accepts (a 1px cover is dropped). */
const editionCovers = [
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPAAAAFoCAIAAADmdeFfAAAD00lEQVR4nO3SQQ3AIADAwDE7OEISqjFBQtLcKeijY6/5QcX/OgBuMjQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUg6lqgPfIM1lJgAAAABJRU5ErkJggg==",
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPAAAAFoCAIAAADmdeFfAAAD1ElEQVR4nO3SQQ3AIADAwDEjOEIA/oVggoSkuVPQR8dc+4OK/3UA3GRoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQca60Dl1hlXTcAAAAASUVORK5CYII=",
];

export const plannedBook = {
  ...bookType,
  statuses: bookType.statuses.map((status) =>
    status.value === "to_read" ? { ...status, planned: true } : status,
  ),
};

export function choreEntry(id: number, title: string, status = "to_read") {
  return {
    id,
    item_id: id + 100,
    status,
    score: null,
    notes: null,
    date_added: "2023-03-01",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: null,
    score_provisional: false,
    suggested_status: null,
    item: {
      id: id + 100,
      type: "book",
      title,
      subtitle: null,
      year: 1965,
      creator: "John Williams",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    shelves: [],
    formats: [],
  };
}

export async function stubChores(
  page: Page,
  calls: Array<{ method: string; url: string; body: unknown }> = [],
) {
  const pile = [
    choreEntry(1, "Stoner"),
    choreEntry(
      2,
      "The Remains of the Day: A Novel About Duty, Dignity and What Is Left",
    ),
    choreEntry(3, "Ficciones"),
  ];
  await stubImporters(page);
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [plannedBook] }),
  );
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/entries?**", (route) => {
    const url = route.request().url();
    const items = url.includes("cover=missing") ? pile.slice(0, 1) : pile;
    return route.fulfill({
      json: {
        items,
        next_cursor: null,
        total: url.includes("status=unsorted") ? 0 : items.length,
        facets: {
          status_counts: {},
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    });
  });
  await page.route("**/api/items/101/cover-candidates", (route) =>
    route.fulfill({
      json: {
        candidates: [
          {
            cover_url: editionCovers[0],
            source_id: "OL1M",
            title: "Stoner",
            year: 2006,
          },
          {
            cover_url: editionCovers[1],
            source_id: "OL2M",
            title: "Stoner",
            year: 1965,
          },
        ],
        reason: null,
      },
    }),
  );
  const record = async (route: Parameters<Parameters<Page["route"]>[1]>[0]) => {
    const request = route.request();
    calls.push({
      method: request.method(),
      url: new URL(request.url()).pathname,
      body: request.postDataJSON(),
    });
    await route.fulfill({
      json: { affected: 1, ...choreEntry(1, "Stoner").item },
    });
  };
  await page.route("**/api/revisit", (route) =>
    route.fulfill({
      json: {
        cards: [
          {
            entry: {
              ...choreEntry(1, "Stoner"),
              status: "read",
              score: 9,
              notes:
                "The quietest book I have read, and the one I think about most.",
            },
            scored_at: "2021-10-24",
          },
        ],
        total: 1,
      },
    }),
  );
  await page.route("**/api/entries/1", (route) => {
    calls.push({
      method: route.request().method(),
      url: "/api/entries/1",
      body: route.request().postDataJSON(),
    });
    return route.fulfill({ json: { ...choreEntry(1, "Stoner"), score: 9 } });
  });
  await page.route("**/api/duplicates", (route) =>
    route.fulfill({
      json: [
        {
          a: { ...choreEntry(1, "Stoner"), status: "read", score: 9 },
          b: {
            ...choreEntry(4, "Stoner (New York Review Books Classics)"),
            status: "read",
            score: 7,
            item: {
              ...choreEntry(4, "x").item,
              title: "Stoner (New York Review Books Classics)",
              cover_url: editionCovers[1],
            },
          },
          reason: "Same title and creator",
        },
      ],
    }),
  );
  await page.route("**/api/duplicates/merge", record);
  await page.route("**/api/duplicates/dismiss", record);
  await page.route("**/api/entries/bulk", record);
  await page.route("**/api/items/101/cover", record);
}
