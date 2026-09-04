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
      name: "publisher",
      label: "Publisher",
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
};

const itemTypes = [bookType, albumType];

function row(
  label: string,
  count: number,
  rated: number,
  mean: number | null,
  spread: number | null = null,
) {
  return {
    key: label.toLowerCase(),
    label,
    count,
    rated_count: rated,
    mean_score: mean,
    score_spread: spread,
  };
}

/**
 * One ranking carrying every case the screen has to draw: a clear leader, groups
 * that are rated enough to place under the score order, and two that are not.
 */
function ranking(rows = defaultRows()) {
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
  };
}

/** In the order the server returns: count descending, then normalized key. */
function defaultRows() {
  return [
    row("Julio Cortázar", 7, 6, 8.8, 0.9),
    row("Ursula K. Le Guin", 5, 5, 9.2, 0.7),
    row("Italo Calvino", 3, 3, 7.7, 1.2),
    // Below `min_rated`: present in the ranking, not placeable by score.
    row("Gene Wolfe", 2, 1, 5.0),
    row("Mariana Enríquez", 2, 2, 3.0, 0.5),
    row("Samanta Schweblin", 2, 0, null),
  ];
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
    row("Anagrama", 2, 2, 9.0),
    row("Gollancz", 1, 0, null),
  ],
  year: [row("1963", 2, 2, 9.5), row("1974", 1, 1, 10)],
  decade: [row("1960s", 4, 3, 9.1), row("1970s", 3, 2, 8.2)],
};

/** Every screen request, with the rankings swappable per key. */
function stubApi(rankings: Record<string, Rows> = defaultRankings) {
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    calls.push(url);
    if (url === "/api/item-types")
      return new Response(JSON.stringify(itemTypes));
    if (url.startsWith("/api/insights")) {
      const key = new URL(url, "http://library.test").searchParams.get("key");
      return new Response(JSON.stringify(ranking(rankings[key ?? ""] ?? [])));
    }
    return new Response("[]");
  });
  return calls;
}

/** One card, by the name its own domain gives the key. */
function card(name: string) {
  return within(screen.getByRole("region", { name: new RegExp(`^${name}`) }));
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

afterEach(() => vi.restoreAllMocks());

describe("InsightsPage", () => {
  it("answers on arrival, with a card for every key the domain declares", async () => {
    // Sprint 065 asked one question per visit: a popover, a refetch, and no way
    // to see two answers beside each other.
    stubApi();
    renderPage();
    await screen.findByText("Julio Cortázar");

    expect(
      screen
        .getAllByRole("region")
        .map(
          (node) =>
            node.getAttribute("aria-label") ??
            within(node).getByRole("heading").textContent,
        ),
    ).toEqual(["Authors", "Publisher", "Year", "Decade"]);
  });

  it("titles a card the way the domain itself names that key", async () => {
    // <th>{key}</th> printed the raw field name, lowercased, for every domain
    // alike. The same field is Authors for books and Artists for albums.
    stubApi();
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Julio Cortázar");
    expect(screen.getByRole("heading", { name: "Authors" })).toBeVisible();

    await user.click(screen.getByRole("radio", { name: "Album" }));

    expect(
      await screen.findByRole("heading", { name: "Artists" }),
    ).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Authors" })).toBeNull();
  });

  it("paints a mean score with the band the ramp gives it", async () => {
    // DEC-026's whole point is that the colour means the same thing wherever the
    // eye lands, and this was the one screen showing a score that opted out.
    // Asserted through the class the shared helper returns, the way ScorePicker
    // and the detail page already assert theirs.
    stubApi();
    renderPage();

    await screen.findByText("Julio Cortázar");

    // 8.8 is nearly a 9 and reads as one; 7.7 is an 8; 3.0 is a 3.
    const authors = card("Authors");
    expect(authors.getByText("8.8").className).toContain("bg-score-top");
    expect(authors.getByText("7.7").className).toContain("bg-score-high");
    expect(authors.getByText("3.0").className).toContain("bg-score-low");
  });

  it("sizes each row's bar to its share of the ranking's leader", async () => {
    // A bare numeral carries no proportion: the shipped table drew 7 and 3 the
    // same size. The bar is the row, so the leader fills it and everyone else is
    // measured against them.
    stubApi();
    renderPage();
    await screen.findByText("Julio Cortázar");

    const bars = screen
      .getByRole("region", { name: /^Authors/ })
      .querySelectorAll<HTMLElement>("[data-magnitude]");
    expect([...bars].map((bar) => bar.dataset.magnitude)).toEqual([
      "1",
      "0.714",
      "0.429",
      "0.286",
      "0.286",
      "0.286",
    ]);
    expect(bars[0].style.width).toBe("100%");
  });

  it("shows how many and how good on every row, under both orders", async () => {
    // The toggle is a sort order, not a choice of which half of the response is
    // rendered. The shipped screen dropped rated_count and mean_score entirely
    // under `count`, which is half of every payload thrown away.
    const calls = stubApi();
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Julio Cortázar");

    // Sorted by how many: the leader is first, and its score is on the row.
    expect(rowOrder("Authors")).toEqual([
      "Julio Cortázar",
      "Ursula K. Le Guin",
      "Italo Calvino",
      "Gene Wolfe",
      "Mariana Enríquez",
      "Samanta Schweblin",
    ]);
    expect(card("Authors").getByText("8.8")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Best rated" }));

    // Sorted by score: the counts are still on every row.
    expect(rowOrder("Authors").slice(0, 4)).toEqual([
      "Ursula K. Le Guin",
      "Julio Cortázar",
      "Italo Calvino",
      "Mariana Enríquez",
    ]);
    expect(card("Authors").getByText("5")).toBeVisible();

    // And the order costs no second request: one ranking per key answers both.
    expect(calls.filter((url) => url.startsWith("/api/insights"))).toHaveLength(
      4,
    );
  });

  it("keeps a group that cannot be placed by score, below a divider", async () => {
    // The threshold is what min_rated means, drawn instead of configured. The
    // shipped screen asked the server to drop these rows, so a group with one
    // rating vanished with no explanation.
    stubApi();
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Julio Cortázar");

    await user.click(screen.getByRole("button", { name: "Best rated" }));

    const authors = card("Authors");
    expect(authors.getByText(/2 not rated enough to place/)).toBeVisible();
    expect(rowOrder("Authors").slice(4)).toEqual([
      "Gene Wolfe",
      "Samanta Schweblin",
    ]);
  });

  it("says plainly when nothing is rated enough to sort by score", async () => {
    stubApi({
      creators: [
        row("Gene Wolfe", 2, 1, 5.0),
        row("Kazuo Ishiguro", 1, 0, null),
      ],
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Gene Wolfe");

    await user.click(screen.getByRole("button", { name: "Best rated" }));

    expect(
      card("Authors").getByText(/Nothing is rated enough to sort by score/),
    ).toBeVisible();
  });

  it("links a ranking row into the filtered library", async () => {
    stubApi();
    const user = userEvent.setup();
    renderPage();
    // The row's accessible name carries what it holds, since its visible cells
    // are a label, a numeral and a chip.
    const row = await screen.findByRole("button", {
      name: "Julio Cortázar: 7 entries, mean score 8.8 from 6 rated",
    });

    await user.click(row);

    await waitFor(() => {
      const text = screen.getByText(/Library:/).textContent ?? "";
      expect(text).toContain("type=book");
      expect(text).toContain("key=creators");
      expect(text).toContain("value=julio+cort");
    });
  });
});

/** One card's row labels, in the order they are drawn. */
function rowOrder(name: string): string[] {
  return [
    ...screen
      .getByRole("region", { name: new RegExp(`^${name}`) })
      .querySelectorAll("[data-row-label]"),
  ].map((node) => node.textContent ?? "");
}
