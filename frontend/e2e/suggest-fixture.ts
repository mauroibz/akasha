import type { Page, Route } from "@playwright/test";

import { pixelCover } from "./seed";

/**
 * *More like this* (Sprint 134), stubbed statefully as Sprint 133's API answers it,
 * with the test-only `fake` source's shape: a round is queued, its `recommend` job
 * reports on `/api/events` as it selects and enriches, the page re-reads the stored
 * round, and answers are kept, so a reload shows them.
 */

export const ATTRIBUTION =
  "This product uses the TMDB API but is not endorsed or certified by TMDB.";

const statuses = [
  { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
  {
    value: "watchlist",
    label: "Watchlist",
    choosable: true,
    hotkey: "l",
    planned: true,
  },
  {
    value: "watched",
    label: "Watched",
    choosable: true,
    hotkey: "w",
    finished: true,
  },
];

export const MODEL_SOURCE = {
  name: "model",
  label: "Model",
  configured: true,
  hint: null,
  resolved_only: true,
  about: {
    provider: "anthropic",
    provider_label: "Claude",
    model: "claude-haiku-5-5",
    sends:
      "Titles, creators, years and your scores from this library; nothing else.",
  },
};

export function movieType(
  configured: boolean,
  { model }: { model?: boolean } = {},
) {
  return {
    id: "movie",
    label: "Movie",
    plural_label: "Movies",
    fields: [],
    statuses,
    default_status: "watchlist",
    entry_fields: ["date_finished", "reread_count"],
    entry_field_labels: {},
    progress: null,
    formats: [],
    entry_panel_label: "Your viewing data",
    chooses_covers: false,
    recommendation: {
      sources: [
        {
          name: "fake",
          label: "TMDB",
          configured,
          hint: configured
            ? null
            : "TMDB is not configured. Set TMDB_READ_TOKEN (a TMDB API read access token, free from themoviedb.org's API settings) in the server's environment and restart.",
        },
        ...(model === undefined
          ? []
          : [
              {
                ...MODEL_SOURCE,
                configured: model,
                hint: model
                  ? null
                  : "The model source is not configured. Set AKASHA_RECS_MODEL_KEY (or ANTHROPIC_API_KEY for the default provider, Claude) in the server's environment and restart.",
              },
            ]),
      ],
      attribution: { fake: ATTRIBUTION },
    },
  };
}

export const film = {
  id: 7,
  item_id: 3,
  status: "watched",
  score: 9,
  notes: null,
  date_added: "2026-10-01",
  date_started: null,
  date_finished: "2026-10-21",
  reread_count: 0,
  progress: null,
  progress_marks: null,
  score_provisional: false,
  suggested_status: null,
  item: {
    id: 3,
    type: "movie",
    title: "Seven Samurai",
    subtitle: null,
    year: 1954,
    creator: "Akira Kurosawa",
    cover_url: null,
    metadata: { creators: ["Akira Kurosawa"] },
    identifiers: { imdb: "tt0047478" },
    sources: [],
  },
  shelves: [],
  formats: [],
};

const titles: Array<[string, number]> = [
  ["Yojimbo", 1961],
  ["Kagemusha", 1980],
  ["After the Rain", 1999],
  ["Rashomon", 1950],
  ["Sanjuro", 1962],
];

function suggestion(index: number, enriched: boolean) {
  const [title, year] = titles[index];
  return {
    id: 100 + index,
    round_id: 7,
    item_type: "movie",
    source: "fake",
    title,
    year,
    creator: null,
    external_ids: { tmdb: String(1000 + index) },
    reason: { signal: "fake", text: "TMDB: often watched together" },
    source_score: null,
    display: {},
    enrichment: enriched ? "enriched" : "pending",
    item_id: enriched ? 50 + index : null,
    entry_id: null as number | null,
    cover_url: enriched ? pixelCover : null,
    seed: { entry_id: 7, title: "Seven Samurai" },
    answer: null as string | null,
    answered_at: null as string | null,
    created_at: "2026-11-23T10:00:00Z",
  };
}

type Suggestion = ReturnType<typeof suggestion>;

export interface SuggestState {
  /** Requests the page made, for asserting what was (not) asked. */
  requests: string[];
  /** How many `recommend` reports are still to come on the event stream. */
  phase: "idle" | "queued" | "enriching" | "done";
  suggestions: Suggestion[];
  /** Pending suggestions someone opened, reported found on the next connection. */
  opened: number[];
}

function round(state: SuggestState) {
  const status = state.phase === "idle" ? "queued" : state.phase;
  return {
    id: 7,
    item_type: "movie",
    seed_entry_id: 7,
    source: "fake",
    status,
    error: null,
    created_at: "2026-11-23T10:00:00Z",
    finished_at: status === "done" ? "2026-11-23T10:00:02Z" : null,
    suggestions: status === "queued" ? [] : state.suggestions,
  };
}

function job(id: string, kind: string, progress: Record<string, unknown>) {
  return `event: job\ndata: ${JSON.stringify({
    id,
    batch_id: null,
    kind,
    state:
      progress.status === "done" || kind !== "recommend"
        ? "succeeded"
        : "running",
    progress,
    error: null,
    error_code: null,
    attempts: 1,
    updated_at: new Date().toISOString(),
  })}\n\n`;
}

/** A model's round (Sprint 135): done, two picks found, one invented, one pending. */
function modelRound() {
  const rows: Array<[number, string, number, string]> = [
    [201, "Ran", 1985, "enriched"],
    [202, "The Hidden Fortress", 1958, "enriched"],
    [203, "Samurai of the Moonless Tide", 1963, "unresolved"],
    [204, "Red Beard", 1965, "pending"],
  ];
  return {
    id: 8,
    item_type: "movie",
    seed_entry_id: 7,
    source: "model",
    status: "done",
    error: null,
    created_at: "2026-11-23T10:00:00Z",
    finished_at: "2026-11-23T10:00:03Z",
    suggestions: rows.map(([id, title, year, enrichment]) => ({
      ...suggestion(0, enrichment === "enriched"),
      id,
      round_id: 8,
      source: "model",
      title,
      year,
      external_ids: {},
      reason: { signal: "model", text: "More Kurosawa, at his most epic." },
      enrichment,
      item_id: enrichment === "enriched" ? id : null,
      cover_url: enrichment === "enriched" ? pixelCover : null,
    })),
  };
}

export async function stubSuggestions(
  page: Page,
  { configured = true, model }: { configured?: boolean; model?: boolean } = {},
): Promise<SuggestState> {
  const state: SuggestState = {
    requests: [],
    phase: "idle",
    suggestions: [],
    opened: [],
  };
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/"))
      state.requests.push(`${request.method()} ${url.pathname}${url.search}`);
  });
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [movieType(configured, { model })] }),
  );
  await page.route("**/api/entries/7", (route) =>
    route.fulfill({ json: film }),
  );
  await page.route("**/api/entries/7/loans", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/locations", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/entries/7/score-history", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/entries/7/more-like-this*", (route) => {
    if (route.request().url().includes("source=model"))
      return route.fulfill({ status: 202, json: modelRound() });
    if (state.phase === "idle") state.phase = "queued";
    return route.fulfill({ status: 202, json: round(state) });
  });
  await page.route("**/api/suggestion-rounds/8", (route) =>
    route.fulfill({ json: modelRound() }),
  );
  await page.route("**/api/suggestion-rounds/7", (route) =>
    route.fulfill({ json: round(state) }),
  );
  // The event stream: each connection carries the next report and asks the
  // browser to come back shortly, as the real stream's reconnects do.
  await page.route("**/api/events", (route: Route) => {
    let body = "retry: 300\n\n";
    if (state.phase === "queued") {
      state.phase = "enriching";
      state.suggestions = titles.map((_, index) => suggestion(index, false));
      body += job("job-1", "recommend", { round_id: 7, status: "enriching" });
    } else if (state.phase === "enriching") {
      state.phase = "done";
      state.suggestions = state.suggestions.map((row, index) =>
        index < 3 ? suggestion(index, true) : row,
      );
      body += job("job-1", "recommend", {
        round_id: 7,
        status: "done",
        enriched: 3,
      });
    } else if (state.opened.length) {
      const id = state.opened.shift()!;
      state.suggestions = state.suggestions.map((row) =>
        row.id === id
          ? { ...suggestion(row.id - 100, true), answer: row.answer }
          : row,
      );
      body += job("job-2", "enrich_suggestion", {
        suggestion_id: id,
        enrichment: "enriched",
      });
    }
    return route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body,
    });
  });
  await page.route("**/api/suggestions/*/enrich", (route) => {
    const id = Number(route.request().url().split("/").slice(-2)[0]);
    state.opened.push(id);
    const row = state.suggestions.find((item) => item.id === id);
    return route.fulfill({
      status: 202,
      json: { suggestion: row, job_id: "job-2" },
    });
  });
  await page.route("**/api/suggestions/*", (route) => {
    if (route.request().method() !== "PATCH") return route.fallback();
    const id = Number(route.request().url().split("/").pop());
    const { answer } = route.request().postDataJSON() as {
      answer: string | null;
    };
    state.suggestions = state.suggestions.map((row) =>
      row.id === id
        ? {
            ...row,
            answer,
            answered_at: answer ? "2026-11-23T10:01:00Z" : null,
            entry_id: answer === "want" ? 90 : row.entry_id,
          }
        : row,
    );
    return route.fulfill({
      json: state.suggestions.find((row) => row.id === id),
    });
  });
  return state;
}
