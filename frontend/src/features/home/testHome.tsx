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

const months = Array.from({ length: 12 }, (_, index) => ({
  month: index + 1,
  count: 0,
  counts: {},
  covers: [] as Home["year"]["months"][number]["covers"],
}));

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
    year: {
      year: 2026,
      months: months.map((m) => ({ ...m, covers: [] })),
      goals: [],
    },
    domains: [],
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
      reason: "creator",
      creator: "Brandon Sanderson",
      mean_score: 8.5,
    },
    {
      entry: entry(11, "Mushishi", "anime", { status: "plan_to_watch" }),
      reason: "waiting",
      since: "2025-09-01",
    },
  ];
  home.year.months[7] = {
    month: 8,
    count: 1,
    counts: { book: 1 },
    covers: [
      {
        entry_id: 20,
        item_id: 120,
        item_type: "book",
        title: "Slaughterhouse-Five",
        cover_url: null,
        score: 8,
      },
    ],
  };
  home.year.months[10] = {
    month: 11,
    count: 2,
    counts: { book: 1, anime: 1 },
    covers: [
      {
        entry_id: 21,
        item_id: 121,
        item_type: "book",
        title: "Pálido fuego",
        cover_url: null,
        score: 7,
      },
      {
        entry_id: 22,
        item_id: 122,
        item_type: "anime",
        title: "Odd Taxi",
        cover_url: null,
        score: 9,
      },
    ],
  };
  home.year.goals = [
    { item_type: "book", period: "month", count: 2, target: 24, done: 2 },
  ];
  home.domains = [
    {
      item_type: "book",
      count: 105,
      status_counts: { read: 57, reading: 1, to_read: 41, dropped: 6 },
      scores: [0, 1, 1, 2, 6, 8, 5, 3, 1, 1],
      mean_score: 6.1,
      covers: [
        {
          entry_id: 30,
          item_id: 130,
          item_type: "book",
          title: "La milla verde",
          cover_url: null,
          score: 10,
        },
      ],
      without_cover: 11,
    },
    {
      item_type: "album",
      count: 148,
      status_counts: { owned: 148 },
      scores: [0, 0, 0, 0, 0, 2, 5, 10, 12, 6],
      mean_score: 7.8,
      covers: [],
      without_cover: 21,
    },
  ];
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
