import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { YearReviewPage } from "./YearReviewPage";

const types = [
  {
    id: "book",
    label: "Book",
    plural_label: "Books",
    fields: [],
    statuses: [],
  },
  {
    id: "anime",
    label: "Anime",
    plural_label: "Anime",
    fields: [],
    statuses: [],
  },
];

const entry = (id: number, type: string, title: string) => ({
  id,
  status: "read",
  score: 9,
  shelves: [],
  formats: [],
  item: { id, type, title, cover_url: null, metadata: {}, identifiers: {} },
});

function renderPage(review: unknown) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/item-types") return new Response(JSON.stringify(types));
    if (url === "/api/diary/2025/review")
      return new Response(JSON.stringify(review));
    return new Response("[]");
  });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/diary/2025/review"]}>
        <Routes>
          <Route path="/diary/:year/review" element={<YearReviewPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("YearReviewPage (Sprint 120)", () => {
  it("reads the year back in sentences, section by section", async () => {
    renderPage({
      year: 2025,
      finished: 3,
      counts: { book: 2, anime: 1 },
      best: [
        { entry: entry(1, "anime", "Monster"), score: 10, at: "2025-10-04" },
        {
          entry: entry(2, "book", "The Dispossessed"),
          score: 9,
          at: "2025-03-02",
        },
      ],
      scores: [0, 0, 0, 0, 0, 0, 0, 1, 1, 1],
      months: [0, 0, 2, 0, 0, 0, 0, 0, 0, 1, 0, 0],
      leader: { name: "Ursula K. Le Guin", count: 2 },
      changes: [
        {
          entry: entry(2, "book", "Solaris"),
          score: 9,
          previous: 8,
          reason: "reread",
          note: "Kelvin stays",
          at: "2025-05-01T00:00:00Z",
        },
      ],
      quote: {
        text: "Anarres stays with me.",
        title: "The Dispossessed",
        entry_id: 2,
        at: "2025-03-02",
      },
    });
    expect(
      await screen.findByRole("heading", { level: 1, name: "2025" }),
    ).toBeVisible();
    expect(
      (await screen.findByText(/You finished/)).closest("p"),
    ).toHaveTextContent(
      "You finished 3 things: 2 books and 1 anime. You returned most to Ursula K. Le Guin.",
    );
    expect(
      screen.getByRole("heading", { name: "The best of it" }),
    ).toBeVisible();
    expect(
      screen.getByText(/Your highest score was/).closest("p"),
    ).toHaveTextContent(
      "Your highest score was a 10, for Monster, in October.",
    );
    expect(
      screen.getByRole("heading", { name: "Month by month" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "What you changed your mind about" }),
    ).toBeVisible();
    expect(screen.getByText(/went up after a reread/)).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "In your words" }),
    ).toBeVisible();
    expect(screen.getByText("“Anarres stays with me.”")).toBeVisible();
  });

  it("says so when nothing was finished", async () => {
    renderPage({
      year: 2025,
      finished: 0,
      counts: {},
      best: [],
      scores: Array(10).fill(0),
      months: Array(12).fill(0),
      leader: null,
      changes: [],
      quote: null,
    });
    expect(
      await screen.findByText("Nothing was finished in 2025."),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "The best of it" }),
    ).toBeNull();
  });
});
