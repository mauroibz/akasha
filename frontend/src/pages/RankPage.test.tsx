import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RankPage } from "./RankPage";

const types = [
  {
    id: "book",
    label: "Book",
    plural_label: "Books",
    fields: [],
    statuses: [],
  },
  {
    id: "movie",
    label: "Movie",
    plural_label: "Movies",
    fields: [],
    statuses: [],
  },
];

afterEach(() => vi.restoreAllMocks());

describe("RankPage (Sprint 116)", () => {
  it("offers each score that two or more share, in the chosen library", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types") return new Response(JSON.stringify(types));
      if (url.startsWith("/api/insights/scores"))
        return new Response(
          JSON.stringify({
            type: "book",
            counts: [0, 0, 0, 0, 1, 3, 9, 14, 2, 1],
            rated_count: 30,
            unrated_count: 4,
          }),
        );
      return new Response("[]");
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <RankPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const list = await screen.findByRole("list", {
      name: "Scores to put in order",
    });
    const links = within(list).getAllByRole("link");
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/rank/book/9",
      "/rank/book/8",
      "/rank/book/7",
      "/rank/book/6",
    ]);
    expect(links[1]).toHaveTextContent("14 books");
  });
});
