import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InsightsPage } from "./InsightsPage";

const bookType = {
  id: "book",
  label: "Book",
  fields: [
    {
      name: "creators",
      label: "Authors",
      type: "text",
      multiplicity: "many",
      groupable: true,
    },
    {
      name: "subjects",
      label: "Subjects",
      type: "text",
      multiplicity: "many",
      groupable: true,
    },
    {
      name: "publisher",
      label: "Publisher",
      type: "text",
      multiplicity: "one",
      groupable: true,
    },
    {
      name: "language",
      label: "Language",
      type: "text",
      multiplicity: "one",
      groupable: true,
    },
    {
      name: "description",
      label: "Description",
      type: "long_text",
      multiplicity: "one",
      groupable: false,
    },
  ],
  statuses: [],
  default_status: "to_read",
  entry_fields: [],
  entry_field_labels: {},
  progress: null,
  formats: [],
  entry_panel_label: "Your reading data",
  plural_label: "Books",
  chooses_covers: false,
};

/** The same key, named differently by its own domain: `Authors` against `Artists`. */
const albumType = {
  ...bookType,
  id: "album",
  label: "Album",
  fields: [
    {
      name: "creators",
      label: "Artists",
      type: "text",
      multiplicity: "many",
      groupable: true,
    },
  ],
  entry_panel_label: "Your listening data",
  plural_label: "Albums",
};

const itemTypes = [bookType, albumType];

function row(
  label: string,
  count: number,
  rated: number,
  mean: number | null,
  spread: number | null = null,
  covers: string[] = [],
) {
  return {
    key: label.toLowerCase(),
    label,
    count,
    rated_count: rated,
    mean_score: mean,
    score_spread: spread,
    covers,
  };
}

/**
 * One ranking carrying every case the screen has to draw: a clear leader, groups
 * that are rated enough to place under the score order, and two that are not.
 */
function ranking(
  rows = defaultRows(),
  totals: { total_entries?: number; rated_entries?: number } = {},
) {
  return {
    type: "book",
    key: "creators",
    metric: "count",
    min_rated: 2,
    rows,
    next_cursor: null,
    suppressed: [],
    no_rated_groups: false,
    null_count: 0,
    total_entries: totals.total_entries ?? 20,
    rated_entries: totals.rated_entries ?? 17,
  };
}

/** In the order the server returns: count descending, then normalized key. */
function defaultRows() {
  return [
    row("Julio Cortázar", 7, 6, 8.8, 0.9, [
      "/api/items/1/cover?v=1",
      "/api/items/2/cover?v=1",
    ]),
    row("Ursula K. Le Guin", 5, 5, 9.2, 0.7),
    row("Italo Calvino", 3, 3, 7.7, 1.2),
    // Below `min_rated`: present in the ranking, not placeable by score.
    row("Gene Wolfe", 2, 1, 5.0),
    row("Mariana Enríquez", 2, 2, 3.0, 0.5),
    row("Samanta Schweblin", 2, 0, null),
  ];
}

/**
 * A decade row, in the server's real shape: `key` is the plain decade start
 * (`"1960"`), `label` is `"1960s"` — distinct from `row()`'s
 * `key = label.toLowerCase()`, which would give a decade row the label text
 * itself as its key and break `chronologyBuckets`' `Number(row.key)`.
 */
function decadeRow(
  decade: number,
  count: number,
  rated: number,
  mean: number | null,
) {
  return {
    key: String(decade),
    label: `${decade}s`,
    count,
    rated_count: rated,
    mean_score: mean,
    score_spread: null,
    covers: [],
  };
}

type Rows = ReturnType<typeof defaultRows>;

/**
 * A ranking per key. The page asks for all of a domain's keys at once now, and
 * four cards of identical rows would make every assertion ambiguous.
 */
const defaultRankings: Record<string, Rows> = {
  creators: defaultRows(),
  publisher: [
    row("Alfaguara", 4, 3, 8.0),
    row("Minotauro", 3, 2, 6.5),
    row("Anagrama", 2, 2, 9.0),
    row("Gollancz", 1, 0, null),
  ],
  // The fine grain of the merged Decade/Year card, not a card of its own.
  year: [row("1963", 2, 2, 9.5), row("1974", 1, 1, 10)],
  decade: [
    decadeRow(1960, 4, 3, 9.1),
    decadeRow(1970, 3, 2, 8.2),
    decadeRow(2000, 2, 1, 6.0),
  ],
  // Many values, several held more than once: typeset by weight.
  subjects: [
    row("Fiction", 12, 9, 8.1),
    row("Magic realism", 6, 5, 8.6),
    row("Short stories", 4, 3, 8.0),
    row("Fantasy", 3, 2, 7.0),
    row("History", 2, 1, 6.0),
    row("Poetry", 2, 2, 9.0),
    row("Memoir", 1, 0, null),
    row("Essays", 1, 0, null),
  ],
  // Two values, each appearing once: a share, drawn as one bar.
  language: [row("Spanish", 1, 0, null), row("English", 1, 0, null)],
};

/** The entries behind a ranking row, as `/api/entries` returns them. */
function entriesPage() {
  const item = (
    id: number,
    title: string,
    year: number,
    score: number | null,
  ) => ({
    id,
    item_id: id,
    status: "read",
    score,
    notes: null,
    date_added: "2026-01-01T00:00:00Z",
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
      year,
      creator: "Julio Cortázar",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
  });
  return {
    items: [item(1, "Rayuela", 1963, 10), item(2, "Bestiario", 1951, 9)],
    next_cursor: null,
    total: 7,
    facets: { status_counts: {}, status_counts_by_type: {}, format_counts: {} },
  };
}

/** A plausible score distribution, for the domain-wide band (Sprint 073). */
function distribution(counts = [0, 0, 1, 0, 0, 1, 0, 2, 1, 0]) {
  return {
    type: "book",
    counts,
    rated_count: counts.reduce((sum, count) => sum + count, 0),
    unrated_count: 1,
  };
}

/** The lead sentence's figures (Sprint 102). */
function summary(overrides: Record<string, unknown> = {}) {
  return {
    type: "book",
    held: 20,
    finished: 9,
    rated: 17,
    unrated: 3,
    modal_score: 8,
    earliest: { entry_id: 2, title: "Bestiario", year: 1951 },
    ...overrides,
  };
}

/** Every screen request, with the rankings swappable per key. */
function stubApi(
  rankings: Record<string, Rows> = defaultRankings,
  scoreDistribution = distribution(),
  leadFigures = summary(),
) {
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    calls.push(url);
    if (url === "/api/item-types")
      return new Response(JSON.stringify(itemTypes));
    if (url.startsWith("/api/insights/scores"))
      return new Response(JSON.stringify(scoreDistribution));
    if (url.startsWith("/api/insights/summary"))
      return new Response(JSON.stringify(leadFigures));
    if (url.startsWith("/api/insights")) {
      const key = new URL(url, "http://library.test").searchParams.get("key");
      return new Response(JSON.stringify(ranking(rankings[key ?? ""] ?? [])));
    }
    if (url.startsWith("/api/entries"))
      return new Response(JSON.stringify(entriesPage()));
    return new Response("[]");
  });
  return calls;
}

/** One section, by its heading. */
function section(name: string) {
  return within(screen.getByRole("region", { name }));
}

/** Renders where an insights row's link lands, so a click's URL is observable. */
function LibraryStub() {
  const [params] = useSearchParams();
  return <div>Library: {params.toString()}</div>;
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/insights"]}>
        <Routes>
          <Route path="/insights" element={<InsightsPage />} />
          <Route path="/" element={<LibraryStub />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("InsightsPage", () => {
  it("opens on one sentence carrying the figures that matter", async () => {
    stubApi();
    renderPage();
    expect(
      await screen.findByText(
        (_, node) =>
          node?.tagName === "P" &&
          node.textContent ===
            "You keep 20 books and have finished 9. You rate generously. You return most to Julio Cortázar.",
      ),
    ).toBeInTheDocument();
  });

  it("numbers its sections, rating first, each titled the way the domain names it", async () => {
    stubApi();
    renderPage();
    await screen.findByRole("region", { name: "Authors" });
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((heading) => heading.textContent);
    expect(headings).toEqual([
      "How you rate",
      "Authors",
      "Subjects",
      "Decade",
      "Publisher",
      "Language",
    ]);
    expect(document.querySelectorAll("[data-insight-section]")).toHaveLength(6);
  });

  it("names the album's key as albums name it", async () => {
    stubApi();
    renderPage();
    await screen.findByRole("region", { name: "Authors" });
    await userEvent.click(screen.getByRole("radio", { name: "Albums" }));
    expect(
      await screen.findByRole("region", { name: "Artists" }),
    ).toBeInTheDocument();
  });

  it("draws how you rate small, beside the usual score drawn large", async () => {
    stubApi();
    renderPage();
    const rating = await screen.findByRole("region", { name: "How you rate" });
    expect(rating).toHaveTextContent("Most of what you rate lands at 8.");
    expect(rating.querySelectorAll("[data-score-bar]")).toHaveLength(10);
    expect(rating).toHaveTextContent("1 unrated, counted everywhere but here.");
  });

  it("ranks the leading key, and reorders it by average on request", async () => {
    stubApi();
    renderPage();
    const authors = await screen.findByRole("region", { name: "Authors" });
    const rows = () =>
      within(authors)
        .getAllByRole("button", { name: /entries|books|book,/ })
        .map((button) => button.getAttribute("aria-label")?.split(":")[0]);
    expect(rows()[0]).toBe("Julio Cortázar");
    await userEvent.click(
      within(authors).getByRole("button", { name: "Best rated" }),
    );
    expect(rows()[0]).toBe("Ursula K. Le Guin");
    expect(authors).toHaveTextContent(
      "Ursula K. Le Guin has your best average: 9.2 over 5 books.",
    );
    expect(authors).toHaveTextContent("2 not rated enough to place");
  });

  it("opens the entries behind a row in place, and still links out", async () => {
    stubApi();
    renderPage();
    await screen.findByRole("region", { name: "Authors" });
    const row = await section("Authors").findByRole("button", {
      name: /^Julio Cortázar: 7 books/,
    });
    await userEvent.click(row);
    expect(row).toHaveAttribute("aria-expanded", "true");
    expect(await screen.findByText("Rayuela")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("link", { name: /Open all 7 in the library/ }),
    );
    expect(
      await screen.findByText(/Library: type=book&key=creators&value=julio/),
    ).toBeInTheDocument();
  });

  it("typesets a many-valued key by weight, each term a way into the library", async () => {
    stubApi();
    renderPage();
    const subjects = await screen.findByRole("region", { name: "Subjects" });
    expect(subjects).toHaveTextContent(
      "Mostly Fiction, Magic realism and Short stories.",
    );
    const fiction = within(subjects).getByRole("link", { name: "Fiction: 12" });
    expect(fiction).toHaveClass("text-4xl");
    expect(
      within(subjects).getByRole("link", { name: "Memoir: 1" }),
    ).toHaveClass("text-lg");
    await userEvent.click(fiction);
    expect(
      await screen.findByText(/Library: type=book&key=subjects&value=fiction/),
    ).toBeInTheDocument();
  });

  it("draws a key of few values as one share", async () => {
    stubApi();
    renderPage();
    const publisher = await screen.findByRole("region", { name: "Publisher" });
    expect(publisher).toHaveTextContent("Alfaguara for 40%, then Minotauro.");
    expect(within(publisher).getByRole("img")).toHaveAccessibleName(
      "Alfaguara 40%, Minotauro 30%, Anagrama 20%, Gollancz 10%",
    );
  });

  it("switches Decade and Year in one section, costing no second request", async () => {
    const calls = stubApi();
    renderPage();
    const decade = await screen.findByRole("region", { name: "Decade" });
    expect(decade).toHaveTextContent("The oldest is Bestiario, from 1951.");
    const before = calls.length;
    await userEvent.click(within(decade).getByRole("button", { name: "Year" }));
    expect(
      within(decade).getByRole("link", { name: "1963: 2 books" }),
    ).toBeInTheDocument();
    expect(calls.length).toBe(before);
  });

  it("offers to read within the library's remembered filters, off by default", async () => {
    localStorage.setItem(
      "akasha.library.filters",
      JSON.stringify({
        statuses: ["read"],
        shelves: [],
        formats: [],
        query: "",
      }),
    );
    const calls = stubApi();
    renderPage();
    await screen.findByRole("region", { name: "Authors" });
    const box = screen.getByRole("checkbox", {
      name: "Only what the library is filtered to",
    });
    expect(box).not.toBeChecked();
    await userEvent.click(box);
    await waitFor(() =>
      expect(
        calls.some(
          (url) =>
            url.startsWith("/api/insights/summary") && url.includes("status="),
        ),
      ).toBe(true),
    );
  });

  it("says so when a domain holds nothing yet", async () => {
    stubApi(
      defaultRankings,
      distribution([0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
      summary({
        held: 0,
        finished: 0,
        rated: 0,
        unrated: 0,
        modal_score: null,
        earliest: null,
      }),
    );
    renderPage();
    expect(await screen.findByText(/Nothing here yet/)).toBeInTheDocument();
    expect(document.querySelectorAll("[data-insight-section]")).toHaveLength(0);
  });
});
