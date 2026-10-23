import type { Page } from "@playwright/test";

import { bookType, series } from "./progress-fixture";

/**
 * A finished book with a score and a chapter count, its score history kept as the
 * server keeps it (Sprint 114), shared by the rescore spec and the accessibility suite.
 */

export const finishingBook = {
  ...bookType,
  statuses: bookType.statuses.map((status) => ({
    ...status,
    finished: status.value === "read",
    in_progress: status.value === "reading",
  })),
};

export async function stubRescore(
  page: Page,
  patches: Array<Record<string, unknown>> = [],
) {
  let current: Record<string, unknown> = series({
    status: "read",
    score: 8,
    date_started: "2019-04-01",
    date_finished: "2019-05-01",
    progress: 3,
    item: {
      ...series().item,
      type: "book",
      title: "Rayuela",
      metadata: { creators: ["Julio Cortázar"], chapters: 3 },
      outline: [{ part: 1, size: 3 }],
    },
  });
  const history: Array<Record<string, unknown>> = [
    {
      score: 8,
      previous: null,
      reason: null,
      note: null,
      recorded_at: "2019-05-01",
    },
  ];
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [finishingBook] }),
  );
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/locations", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/items/3/attachments", (route) =>
    route.fulfill({ json: { attachments: [] } }),
  );
  await page.route("**/api/entries/7/loans", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/entries/7/score-history", (route) =>
    route.fulfill({ json: history }),
  );
  await page.route("**/api/entries/7", async (route) => {
    const request = route.request();
    if (request.method() === "PATCH") {
      const body = request.postDataJSON() as Record<string, unknown>;
      patches.push(body);
      const before = current.score;
      current = { ...current, ...body };
      if ("progress_marks" in body) {
        const marks = (body.progress_marks ?? {}) as Record<string, number[]>;
        current.progress = Object.values(marks).flat().length;
      }
      if ("progress" in body) current.progress_marks = null;
      if ("score" in body && (body.score !== before || body.score_reason))
        history.push({
          score: body.score,
          previous: before,
          reason: body.score_reason ?? "time",
          note: body.score_note ?? null,
          recorded_at: new Date().toISOString(),
        });
    }
    await route.fulfill({ json: current });
  });
}
