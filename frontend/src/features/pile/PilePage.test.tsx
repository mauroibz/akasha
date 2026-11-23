import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { entry, renderWithRouter, types } from "@/features/home/testHome";

import { PilePage } from "./PilePage";

const pile = [
  {
    entry: entry(61, "Mistborn", "book", { status: "to_read" }),
    score: 3,
    reasons: [{ signal: "series", text: "Next in Mistborn" }],
  },
  {
    entry: entry(62, "Paris, Texas", "movie", { status: "watchlist" }),
    score: 2,
    reasons: [],
  },
  {
    entry: entry(63, "It", "book", { status: "to_read" }),
    score: 1,
    reasons: [{ signal: "waiting", text: "Waiting since Sep 2025" }],
  },
];

function stub(patches: Array<Record<string, unknown>> = []) {
  const fetchMock = vi.fn(
    async (request: string | URL | Request, init?: RequestInit) => {
      const url = String(request);
      if (init?.method === "PATCH") {
        patches.push(JSON.parse(String(init.body)) as Record<string, unknown>);
        return new Response(JSON.stringify(pile[0].entry));
      }
      if (url.startsWith("/api/item-types"))
        return new Response(JSON.stringify(types));
      return new Response(JSON.stringify(pile));
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("PilePage (DEC-192)", () => {
  it("lists the whole pile in order, with its reasons and the deck beside it", async () => {
    const fetchMock = stub();
    renderWithRouter(<PilePage />);
    const list = await screen.findByRole("list");
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Mistborn");
    expect(rows[0]).toHaveTextContent("Next in Mistborn");
    expect(rows[2]).toHaveTextContent("Waiting since Sep 2025");
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).startsWith("/api/pile?limit=1000"),
      ),
    ).toBe(true);
    expect(
      screen.getByRole("link", { name: "Sort in cards →" }),
    ).toHaveAttribute("href", "/deck/planned");
  });

  it("narrows to one library", async () => {
    stub();
    renderWithRouter(<PilePage />);
    await screen.findByRole("list");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /^Books/ }));
    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining("Mistborn"),
      expect.stringContaining("It"),
    ]);
  });

  it("starts a book and offers to mark a film as watched", async () => {
    const patches: Array<Record<string, unknown>> = [];
    stub(patches);
    renderWithRouter(<PilePage />);
    await screen.findByRole("list");
    const user = userEvent.setup();
    expect(
      screen.getByRole("button", { name: "Mark Paris, Texas as watched" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Start Mistborn" }));
    await waitFor(() => expect(patches).toEqual([{ status: "reading" }]));
  });
});
