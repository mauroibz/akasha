import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ItemType } from "@/api/library";

import { PlaySection } from "./PlaySection";

const book = {
  id: "book",
  label: "Book",
  plural_label: "Books",
  statuses: [
    { value: "read", label: "Read", finished: true },
    { value: "to_read", label: "To read", planned: true },
  ],
  formats: [],
} as unknown as ItemType;

const card = (id: number, title: string, score: number | null = 8) => ({
  id,
  score,
  date_added: "2026-07-02T10:00:00Z",
  item: { id, type: "book", title, cover_url: null },
});

function stub({
  counts = [0, 0, 0, 0, 0, 0, 0, 3, 1, 0],
  revisit = [card(1, "Tokio blues", 10)],
  pile = [card(2, "Release It!", null)],
  gaps = [card(3, "Rayuela")],
}: Record<string, unknown> = {}) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const json = (body: unknown) => new Response(JSON.stringify(body));
    if (url.startsWith("/api/insights/scores"))
      return json({ counts, total: 4, mean: 8 });
    if (url.startsWith("/api/revisit"))
      return json({
        cards: (revisit as unknown[]).map((entry) => ({
          entry,
          scored_at: "2024-01-01",
        })),
        total: (revisit as unknown[]).length,
      });
    if (url.startsWith("/api/gaps"))
      return json({ entries: gaps, total: (gaps as unknown[]).length });
    if (url.includes("score=8"))
      return json({ items: [card(4, "Matadero cinco")], total: 3 });
    if (url.startsWith("/api/entries"))
      return json({ items: pile, total: (pile as unknown[]).length });
    return json([]);
  });
}

const mount = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PlaySection type="book" types={[book]} />
      </MemoryRouter>
    </QueryClientProvider>,
  );

afterEach(() => vi.restoreAllMocks());

describe("PlaySection (Sprint 125)", () => {
  it("asks about your own books, each game a link", async () => {
    stub();
    mount();
    const section = await screen.findByRole("region", {
      name: "Play with your library",
    });
    const best = await within(section).findByRole("link", {
      name: /Which 8 is your best 8\?/,
    });
    expect(best).toHaveAttribute("href", "/rank/book/8");
    expect(best).toHaveTextContent("3 books");
    expect(
      await within(section).findByRole("link", {
        name: /Is Tokio blues still a 10\?/,
      }),
    ).toHaveAttribute("href", "/deck/revisit");
    expect(
      await within(section).findByRole("link", { name: /The pile/ }),
    ).toHaveAttribute("href", "/deck/planned");
    expect(
      await within(section).findByRole("link", { name: /Fill in the gaps/ }),
    ).toHaveAttribute("href", "/play/gaps");
  });

  it("draws no game that has nothing to ask, and no section when none does", async () => {
    stub({
      counts: [0, 0, 0, 0, 0, 0, 0, 1, 1, 0],
      revisit: [],
      pile: [],
      gaps: [],
    });
    const { container } = mount();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
