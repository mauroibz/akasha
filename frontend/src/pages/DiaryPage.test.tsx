import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DiaryPage } from "./DiaryPage";

const book = { id: "book", label: "Book", statuses: [], fields: [] };
const movie = { id: "movie", label: "Movie", statuses: [], fields: [] };
const entry = (id: number, type: string, title: string) => ({
  id,
  status: "read",
  item: { id, type, title, cover_url: null, metadata: {}, identifiers: {} },
});

afterEach(() => vi.restoreAllMocks());

describe("DiaryPage", () => {
  it("says what each month held, in the domains' words, with the covers", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/item-types"))
        return new Response(JSON.stringify([book, movie]));
      if (url.startsWith("/api/diary"))
        return new Response(
          JSON.stringify({
            year: 2026,
            years: [2026, 2025],
            months: [
              {
                month: "2026-03",
                counts: { book: 2, movie: 1 },
                entries: [
                  entry(1, "book", "Ficciones"),
                  entry(2, "movie", "Up"),
                  entry(3, "book", "Rayuela"),
                ],
              },
            ],
          }),
        );
      return new Response("[]");
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <DiaryPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(
      await screen.findByRole("heading", { level: 2, name: /march/i }),
    ).toBeVisible();
    expect(await screen.findByText("2 books, 1 movie")).toBeVisible();
    expect(screen.getByRole("button", { name: "Open Rayuela" })).toBeVisible();
    expect(screen.getByRole("button", { name: "2025" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
