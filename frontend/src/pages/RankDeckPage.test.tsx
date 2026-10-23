import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RankDeckPage } from "./RankDeckPage";

function entry(id: number, title: string, rank: number | null) {
  return {
    id,
    item_id: id,
    status: "read",
    score: 8,
    score_rank: rank,
    notes: null,
    date_added: "2024-01-01",
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
      year: 1960,
      creator: "Someone",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
  };
}

const bookType = {
  id: "book",
  label: "Book",
  plural_label: "Books",
  fields: [],
  statuses: [],
};

afterEach(() => vi.restoreAllMocks());

describe("RankDeckPage (Sprint 116)", () => {
  it("places each new entry by asking between two, and saves the order as it goes", async () => {
    const puts: unknown[] = [];
    const lists: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify([bookType]));
      if (init?.method === "PUT") {
        puts.push(JSON.parse(String(init.body)));
        return new Response("[]");
      }
      if (url.startsWith("/api/entries?")) {
        lists.push(url);
        return new Response(
          JSON.stringify({
            items: [
              entry(1, "Stoner", 1),
              entry(2, "Solaris", null),
              entry(3, "Ficciones", null),
            ],
            next_cursor: null,
            total: 3,
            facets: {
              status_counts: {},
              status_counts_by_type: {},
              format_counts: {},
            },
          }),
        );
      }
      return new Response("[]");
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/rank/book/8"]}>
          <Routes>
            <Route path="/rank/:type/:score" element={<RankDeckPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();
    expect(
      await screen.findByRole("heading", { name: "Which did you like more?" }),
    ).toBeVisible();
    expect(lists[0]).toContain("score=8");
    expect(lists[0]).toContain("type=book");
    await user.click(screen.getByRole("button", { name: "Solaris" }));
    await waitFor(() => expect(puts).toEqual([{ entry_ids: [2, 1] }]));
    await user.click(
      await screen.findByRole("button", { name: "About the same" }),
    );
    await waitFor(() =>
      expect(puts).toEqual([{ entry_ids: [2, 1] }, { entry_ids: [2, 1, 3] }]),
    );
    const order = await screen.findByRole("list", {
      name: "Your 8s, in order",
    });
    expect(
      within(order)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual([
      expect.stringContaining("Solaris"),
      expect.stringContaining("Stoner"),
      expect.stringContaining("Ficciones"),
    ]);
  });
});
