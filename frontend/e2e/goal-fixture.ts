import type { Page } from "@playwright/test";

import { bookItemType, stubItemTypes } from "./seed";

/**
 * The Diary with a gentle goal (Sprint 104): the band, its slots (Sprint 127) and
 * the picks, in both themes, and the goal dialog open; without a goal, the invitation.
 */
export async function stubDiaryWithGoal(
  page: Page,
  goals: unknown[] = [
    { item_type: "book", count: 2, period: "month", suggest: true },
  ],
) {
  const year = new Date().getFullYear();
  await stubItemTypes(page, [
    {
      ...bookItemType,
      plural_label: "Books",
      entry_fields: ["date_started", "date_finished", "reread_count"],
      statuses: [
        { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
        { value: "read", label: "Read", choosable: true, hotkey: "r" },
        {
          value: "reading",
          label: "Reading",
          choosable: true,
          hotkey: "g",
          in_progress: true,
        },
        {
          value: "to_read",
          label: "To read",
          choosable: true,
          hotkey: "t",
          planned: true,
        },
      ],
    },
  ] as Parameters<typeof stubItemTypes>[1]);
  const entry = (id: number, title: string) => ({
    id,
    item_id: id,
    status: "to_read",
    score: null,
    notes: null,
    date_added: "2024-03-01T00:00:00Z",
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
      year: 1974,
      creator: "Ursula K. Le Guin",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
  });
  const finished = [
    { ...entry(20, "Rayuela"), status: "read", date_finished: `${year}-02-03` },
    {
      ...entry(21, "Ficciones"),
      status: "read",
      date_finished: `${year}-03-04`,
    },
  ];
  await page.route("**/api/diary**", (route) =>
    route.fulfill({
      json: {
        year,
        years: [year],
        months: [
          { month: `${year}-03`, counts: { book: 1 }, entries: [finished[1]] },
          { month: `${year}-02`, counts: { book: 1 }, entries: [finished[0]] },
        ],
      },
    }),
  );
  await page.route("**/api/goals", (route) => route.fulfill({ json: goals }));
  await page.route("**/api/goals/book/progress**", (route) =>
    route.fulfill({
      json: {
        item_type: "book",
        year,
        months: [2, 1, 3, 2, 0, 2, 4, 1, 1, 1, 0, 0],
        total: 17,
        target: 24,
      },
    }),
  );
  await page.route("**/api/goals/book/picks**", (route) =>
    route.fulfill({
      json: [
        {
          entry: entry(10, "The Dispossessed"),
          reason: "creator",
          creator: "Ursula K. Le Guin",
          mean_score: 9,
          since: null,
        },
        {
          entry: entry(11, "The Lathe of Heaven"),
          reason: "waiting",
          creator: null,
          mean_score: null,
          since: "2024-03-01T00:00:00Z",
        },
      ],
    }),
  );
}
