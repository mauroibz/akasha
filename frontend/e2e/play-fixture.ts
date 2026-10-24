import type { Page } from "@playwright/test";

import { choreEntry, plannedBook, stubChores } from "./chores-fixture";

/**
 * Play at the top of Insights, and Fill in the gaps (Sprint 125, DEC-179): the chores'
 * stubs, plus Insights' own figures and two finished books missing a date. Shared by the
 * play spec and the accessibility suite.
 */
export async function stubPlay(
  page: Page,
  calls: Array<{ method: string; url: string; body: unknown }> = [],
) {
  await stubChores(page, calls);
  // Read is finished and To read planned, as the registry declares them.
  await page.route("**/api/item-types", (route) =>
    route.fulfill({
      json: [
        {
          ...plannedBook,
          statuses: plannedBook.statuses.map((status) => ({
            ...status,
            finished: status.value === "read",
          })),
        },
      ],
    }),
  );
  const gaps = [
    { ...choreEntry(7, "Rayuela", "read"), score: 9, location: "Hall" },
    { ...choreEntry(8, "Ficciones", "read"), score: 10, location: "Hall" },
  ];
  await page.route("**/api/insights**", (route) =>
    route.fulfill({
      json: {
        type: "book",
        key: "creators",
        metric: "count",
        min_rated: 2,
        rows: [],
        next_cursor: null,
        suppressed: [],
        no_rated_groups: false,
        null_count: 0,
        total_entries: 3,
        rated_entries: 2,
      },
    }),
  );
  await page.route("**/api/insights/scores**", (route) =>
    route.fulfill({
      json: {
        type: "book",
        counts: [0, 0, 0, 0, 0, 0, 0, 0, 1, 2],
        rated_count: 3,
        unrated_count: 0,
      },
    }),
  );
  await page.route("**/api/insights/summary**", (route) =>
    route.fulfill({
      json: {
        type: "book",
        held: 6,
        finished: 3,
        rated: 3,
        unrated: 0,
        modal_score: 10,
        earliest: null,
      },
    }),
  );
  await page.route("**/api/entries/rank", async (route) => {
    const request = route.request();
    calls.push({
      method: request.method(),
      url: "/api/entries/rank",
      body: request.postDataJSON(),
    });
    await route.fulfill({ json: [] });
  });
  await page.route("**/api/gaps", (route) =>
    route.fulfill({ json: { entries: gaps, total: gaps.length } }),
  );
  for (const entry of gaps)
    await page.route(`**/api/entries/${entry.id}`, async (route) => {
      const request = route.request();
      if (request.method() === "PATCH") {
        const body = request.postDataJSON() as Record<string, unknown>;
        calls.push({ method: "PATCH", url: `/api/entries/${entry.id}`, body });
        Object.assign(entry, body);
      }
      await route.fulfill({ json: entry });
    });
}
