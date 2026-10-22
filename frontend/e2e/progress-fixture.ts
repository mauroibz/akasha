import type { Page } from "@playwright/test";

import { bookItemType } from "./seed";

/**
 * A series with two seasons and a book with chapters, as Sprint 107 publishes them,
 * shared by the progress-marks spec and the accessibility suite (Sprint 108).
 */

const seasons = [
  { part: 1, size: 3 },
  { part: 2, size: 4 },
];

export const seriesType = {
  id: "series",
  label: "Series",
  fields: [
    {
      name: "season_episodes",
      label: "Episodes per season",
      type: "rows",
      multiplicity: "many",
      columns: [
        { name: "season", label: "Season", type: "number" },
        { name: "episodes", label: "Episodes", type: "number" },
      ],
    },
  ],
  statuses: [
    { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
    { value: "watching", label: "Watching", choosable: true, hotkey: "w" },
    { value: "completed", label: "Completed", choosable: true, hotkey: "c" },
    {
      value: "dropped",
      label: "Dropped",
      choosable: true,
      hotkey: "d",
      abandoned: true,
    },
  ],
  default_status: "watching",
  entry_fields: ["date_started", "date_finished", "reread_count"],
  entry_field_labels: { reread_count: "Rewatches" },
  progress: {
    label: "Episodes watched",
    unit_label: "episode",
    total_field: "episodes",
    parts_field: "season_episodes",
  },
  formats: [{ value: "streaming", label: "Streaming" }],
  entry_panel_label: "Your watch data",
  chooses_covers: false,
};

/** Books, as Sprint 107 publishes them: chapters read, and `dropped` abandoned. */
export const bookType = {
  ...bookItemType,
  statuses: bookItemType.statuses.map((status) =>
    status.value === "dropped" ? { ...status, abandoned: true } : status,
  ),
  progress: {
    label: "Chapters read",
    unit_label: "chapter",
    total_field: "chapters",
    parts_field: null,
  },
};

export function series(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    item_id: 3,
    status: "watching",
    score: null,
    notes: null,
    date_added: "2026-10-01",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: 3,
    progress_marks: null,
    score_provisional: false,
    suggested_status: null,
    item: {
      id: 3,
      type: "series",
      title: "Breaking Bad",
      subtitle: null,
      year: 2008,
      creator: "Vince Gilligan",
      cover_url: null,
      metadata: {
        creators: ["Vince Gilligan"],
        season_episodes: [
          { season: 1, episodes: 3 },
          { season: 2, episodes: 4 },
        ],
      },
      outline: seasons,
      identifiers: { imdb: "tt0903747" },
      sources: [],
    },
    shelves: [],
    formats: [],
    ...overrides,
  };
}

/** A stateful entry: PATCH applies the body and keeps the count in step. */
export async function stubSeries(page: Page, patches: unknown[]) {
  let current: Record<string, unknown> = series();
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [seriesType, bookType] }),
  );
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/items/3/attachments", (route) =>
    route.fulfill({ json: { attachments: [] } }),
  );
  await page.route("**/api/entries/7", async (route) => {
    const request = route.request();
    if (request.method() === "PATCH") {
      const body = request.postDataJSON() as Record<string, unknown>;
      patches.push(body);
      current = { ...current, ...body };
      if ("progress_marks" in body) {
        const marks = (body.progress_marks ?? {}) as Record<string, number[]>;
        current.progress = Object.values(marks).flat().length;
      }
    }
    await route.fulfill({ json: current });
  });
}
