import type { Page } from "@playwright/test";

import { rankEntry } from "./rank-fixture";
import { bookItemType, movieItemType } from "./seed";

/** The Diary's timeline as Sprint 118's API answers it: two pages, two libraries. */
export async function stubTimeline(page: Page) {
  const book = { ...rankEntry(1, "Dune", null), score: 9 };
  const film = {
    ...rankEntry(2, "Dune", null),
    score: 8,
    item: { ...rankEntry(2, "Dune", null).item, type: "movie" },
  };
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [bookItemType, movieItemType] }),
  );
  await page.route("**/api/goals", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/diary**", (route) =>
    route.fulfill({
      json: { year: 2026, years: [2026, 2021, 2019], months: [] },
    }),
  );
  await page.route("**/api/diary/timeline**", (route) => {
    const before = new URL(route.request().url()).searchParams.get("before");
    return route.fulfill({
      json: before
        ? {
            events: [
              { kind: "finished", at: "2019-03-02", entry: book, score: 9 },
            ],
            next_cursor: null,
          }
        : {
            events: [
              {
                kind: "score",
                at: "2026-03-02T10:00:00Z",
                entry: book,
                score: 9,
                previous: 7,
                reason: "reread",
                note: "The second time it was about ecology, not prophecy",
              },
              { kind: "finished", at: "2021-10-22", entry: film, score: 8 },
            ],
            next_cursor: "MjAyMS0xMC0yMnwxfDAwMDAwMDAwMDI",
          },
    });
  });
}
