import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import type { Home } from "@/api/home";
import type { ItemType, LibraryEntry } from "@/api/library";

/** Test-only: a library shaped like the owner's, for Home's module tests. */

function status(
  value: string,
  label: string,
  flags: Partial<
    Record<"in_progress" | "planned" | "finished" | "abandoned", boolean>
  > = {},
) {
  return { value, label, choosable: true, hotkey: null, ...flags };
}

function domain(
  id: string,
  label: string,
  plural: string,
  statuses: ReturnType<typeof status>[],
  progress: ItemType["progress"],
): ItemType {
  return {
    id,
    label,
    plural_label: plural,
    fields: [],
    statuses: [status("unsorted", "Unsorted"), ...statuses],
    default_status: statuses[0].value,
    entry_fields: ["date_started", "date_finished", "reread_count"],
    entry_field_labels: {},
    progress,
    formats: [],
    entry_panel_label: "Yours",
    chooses_covers: false,
  } as unknown as ItemType;
}

export const types: ItemType[] = [
  domain(
    "book",
    "Book",
    "Books",
    [
      status("read", "Read", { finished: true }),
      status("reading", "Reading", { in_progress: true }),
      status("to_read", "To read", { planned: true }),
      status("dropped", "Dropped", { abandoned: true }),
    ],
    {
      label: "Pages read",
      unit_label: "page",
      total_field: "page_count",
    } as ItemType["progress"],
  ),
  domain(
    "anime",
    "Anime",
    "Anime",
    [
      status("watching", "Watching", { in_progress: true }),
      status("completed", "Completed", { finished: true }),
      status("plan_to_watch", "Plan to watch", { planned: true }),
    ],
    {
      label: "Episodes watched",
      unit_label: "episode",
      total_field: "episodes",
    } as ItemType["progress"],
  ),
  domain("album", "Album", "Albums", [status("owned", "Owned")], null),
  domain(
    "movie",
    "Movie",
    "Movies",
    [
      status("watchlist", "Watchlist", { planned: true }),
      status("watched", "Watched", { finished: true }),
    ],
    null,
  ),
];

export function entry(
  id: number,
  title: string,
  type: string,
  values: Partial<LibraryEntry> & { metadata?: Record<string, unknown> } = {},
): LibraryEntry {
  const { metadata, ...rest } = values;
  return {
    id,
    item_id: id + 100,
    status: "reading",
    score: null,
    notes: null,
    date_added: "2026-10-21",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: null,
    score_provisional: false,
    suggested_status: null,
    shelves: [],
    formats: [],
    unknown_fields: [],
    item: {
      id: id + 100,
      type,
      title,
      subtitle: null,
      year: null,
      creator: "Someone",
      cover_path: null,
      cover_url: null,
      metadata: metadata ?? {},
      identifiers: {},
      sources: [],
    },
    ...rest,
  } as unknown as LibraryEntry;
}

export function emptyHome(): Home {
  return {
    greeting: {
      today: "2026-11-22",
      active: null,
      entries: 0,
      pile: 0,
      goals: [],
    },
    now: [],
    next: [],
    lately: [],
    question: null,
  };
}

export const reading = entry(
  1,
  "Designing Data-Intensive Applications",
  "book",
  {
    status: "reading",
    date_started: "2026-10-22",
    progress: 120,
    metadata: { page_count: 600 },
  },
);
export const watching = entry(2, "Frieren", "anime", {
  status: "watching",
  progress: 3,
  metadata: { episodes: 28 },
});

export function fullHome(): Home {
  const home = emptyHome();
  home.greeting = {
    today: "2026-11-22",
    active: { entry: reading, day: 32 },
    entries: 345,
    pile: 41,
    goals: [{ item_type: "book", target: 24, count: 2 }],
  };
  home.now = [reading, watching];
  home.next = [
    {
      entry: entry(10, "Mistborn", "book", { status: "to_read" }),
      score: 3.4,
      reasons: [
        {
          signal: "series",
          text: "Next in Mistborn; you gave book 1 a 9",
        },
        { signal: "waiting", text: "Waiting since Sep 2025" },
      ],
    },
    {
      entry: entry(11, "Mushishi", "anime", { status: "plan_to_watch" }),
      score: 0.3,
      reasons: [{ signal: "waiting", text: "Waiting since Sep 2025" }],
    },
  ];
  const finished = entry(40, "Pálido fuego", "book", {
    status: "read",
    score: 7,
  });
  home.lately = [
    {
      kind: "finished",
      at: "2026-11-06",
      entry: finished,
      score: 7,
      previous: null,
      count: 1,
    },
    {
      kind: "score",
      at: "2026-10-25T10:00:00Z",
      entry: entry(41, "A Clash of Kings", "book", { status: "read" }),
      score: 6,
      previous: 8,
      count: 1,
    },
    {
      kind: "added",
      at: "2026-10-02T09:00:00Z",
      entry: entry(42, "Why Nations Fail", "book", { status: "to_read" }),
      score: null,
      previous: null,
      count: 3,
    },
  ];
  home.question = {
    kind: "revisit",
    entry: entry(43, "Pet Sematary", "book", { status: "read", score: 9 }),
    scored_at: "2019-03-02T00:00:00Z",
  };
  return home;
}

/** Where the router is, so a link or navigation can be asserted. */
// A test helper, never hot-reloaded.
// eslint-disable-next-line react-refresh/only-export-components
function Where() {
  const location = useLocation();
  return (
    <div data-testid="where">{`${location.pathname}${location.search}`}</div>
  );
}

export function renderWithRouter(node: ReactNode, client?: QueryClient) {
  const queryClient =
    client ??
    new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    client: queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route
              path="*"
              element={
                <>
                  {node}
                  <Where />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}
