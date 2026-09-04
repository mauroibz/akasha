import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InsightsPage } from "./InsightsPage";

const itemTypes = [
  {
    id: "book",
    label: "Book",
    fields: [
      {
        name: "creators",
        label: "Creators",
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
  },
];

function countInsight() {
  return {
    type: "book",
    key: "creators",
    metric: "count",
    min_rated: 2,
    rows: [
      {
        key: "julio cortazar",
        label: "Julio Cortázar",
        count: 3,
        rated_count: 2,
        mean_score: 9,
        score_spread: 1,
      },
    ],
    next_cursor: null,
    suppressed: [],
    no_rated_groups: false,
    null_count: 0,
  };
}

/** A score ranking with rows in it, spanning three bands of the ramp. */
function scoreInsight() {
  return {
    type: "book",
    key: "creators",
    metric: "score",
    min_rated: 2,
    rows: [
      {
        key: "julio cortazar",
        label: "Julio Cortázar",
        count: 7,
        rated_count: 6,
        mean_score: 8.8,
        score_spread: 0.9,
      },
      {
        key: "italo calvino",
        label: "Italo Calvino",
        count: 3,
        rated_count: 3,
        mean_score: 7.7,
        score_spread: 1.2,
      },
      {
        key: "mariana enriquez",
        label: "Mariana Enríquez",
        count: 2,
        rated_count: 2,
        mean_score: 3.0,
        score_spread: 0.5,
      },
    ],
    next_cursor: null,
    suppressed: [],
    no_rated_groups: false,
    null_count: 0,
  };
}

function scoreInsightWithNothingRated() {
  return {
    type: "book",
    key: "creators",
    metric: "score",
    min_rated: 2,
    rows: [],
    next_cursor: null,
    suppressed: [],
    no_rated_groups: true,
    null_count: 0,
  };
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
  it("ranks the first domain by its first groupable key on load", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url.startsWith("/api/insights"))
        return new Response(JSON.stringify(countInsight()));
      return new Response("[]");
    });
    renderPage();
    expect(await screen.findByText("Julio Cortázar")).toBeVisible();
    expect(screen.getByText("3")).toBeVisible();
  });

  it("switches to the score metric and shows the no-rated-groups message", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url.includes("metric=score"))
        return new Response(JSON.stringify(scoreInsightWithNothingRated()));
      if (url.startsWith("/api/insights"))
        return new Response(JSON.stringify(countInsight()));
      return new Response("[]");
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Julio Cortázar");

    await user.click(screen.getByRole("button", { name: "Rank by score" }));

    expect(
      await screen.findByText(/Nothing is rated enough to rank by score yet/),
    ).toBeVisible();
  });

  it("paints a mean score with the band the ramp gives it", async () => {
    // DEC-026's whole point is that the colour means the same thing wherever the
    // eye lands, and this was the one screen showing a score that opted out.
    // Asserted through the class the shared helper returns, the way ScorePicker
    // and the detail page already assert theirs.
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url.includes("metric=score"))
        return new Response(JSON.stringify(scoreInsight()));
      if (url.startsWith("/api/insights"))
        return new Response(JSON.stringify(countInsight()));
      return new Response("[]");
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Julio Cortázar");

    await user.click(screen.getByRole("button", { name: "Rank by score" }));

    // 8.8 is nearly a 9 and reads as one; 7.7 is an 8; 3.0 is a 3.
    expect((await screen.findByText("8.8")).className).toContain(
      "bg-score-top",
    );
    expect(screen.getByText("7.7").className).toContain("bg-score-high");
    expect(screen.getByText("3.0").className).toContain("bg-score-low");
  });

  it("sizes each row's bar to its share of the ranking's leader", async () => {
    // A bare numeral carries no proportion: the shipped table drew 7 and 3 the
    // same size. The bar is the row, so the leader fills it and everyone else is
    // measured against them.
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url.includes("metric=score"))
        return new Response(JSON.stringify(scoreInsight()));
      if (url.startsWith("/api/insights"))
        return new Response(JSON.stringify(countInsight()));
      return new Response("[]");
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Rank by score" }));
    await screen.findByText("Julio Cortázar");

    const bars = document.querySelectorAll<HTMLElement>("[data-magnitude]");
    expect([...bars].map((bar) => bar.dataset.magnitude)).toEqual([
      "1",
      "0.429",
      "0.286",
    ]);
    expect(bars[0].style.width).toBe("100%");
  });

  it("links a ranking row into the filtered library", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url.startsWith("/api/insights"))
        return new Response(JSON.stringify(countInsight()));
      return new Response("[]");
    });
    const user = userEvent.setup();
    renderPage();
    // The row's accessible name carries what it holds, since its visible cells are
    // a label, a numeral and a chip.
    const row = await screen.findByRole("button", {
      name: "Julio Cortázar: 3 entries, mean score 9.0 from 2 rated",
    });

    await user.click(row);

    await waitFor(() => {
      const text = screen.getByText(/Library:/).textContent ?? "";
      expect(text).toContain("type=book");
      expect(text).toContain("key=creators");
      expect(text).toContain("value=julio+cortazar");
    });
  });
});
