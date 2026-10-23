import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CoversDeckPage } from "./CoversDeckPage";

function entry(id: number, title: string, type = "book") {
  return {
    id,
    item_id: id + 100,
    status: "read",
    score: null,
    notes: null,
    date_added: "2023-01-01T00:00:00Z",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: null,
    score_provisional: false,
    suggested_status: null,
    shelves: [],
    formats: [],
    item: {
      id: id + 100,
      type,
      title,
      subtitle: null,
      year: 1965,
      creator: "Someone",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
  };
}

function stub() {
  const calls: Array<{ method: string; url: string; body?: unknown }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    calls.push({
      method,
      url,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    if (url.startsWith("/api/entries?"))
      return new Response(
        JSON.stringify({
          items: [entry(1, "Stoner"), entry(2, "Kid A", "album")],
          next_cursor: null,
          total: 2,
          facets: {
            status_counts: {},
            status_counts_by_type: {},
            format_counts: {},
          },
        }),
      );
    if (url === "/api/items/101/cover-candidates")
      return new Response(
        JSON.stringify({
          candidates: [
            {
              cover_url: "https://covers.example/a.jpg",
              source_id: "OL1M",
              title: "Stoner",
              year: 2006,
            },
            {
              cover_url: "https://covers.example/b.jpg",
              source_id: "OL2M",
              title: "Stoner",
              year: 1965,
            },
          ],
          reason: null,
        }),
      );
    if (url === "/api/items/102/cover-candidates")
      return new Response(
        JSON.stringify({ candidates: [], reason: "not_supported" }),
      );
    if (method === "POST")
      return new Response(JSON.stringify(entry(1, "x").item));
    return new Response("[]");
  });
  return calls;
}

function renderDeck() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/deck/covers"]}>
        <Routes>
          <Route path="/deck/covers" element={<CoversDeckPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("CoversDeckPage (Sprint 112)", () => {
  it("offers covers for the card on screen only, and installs the one chosen", async () => {
    const calls = stub();
    renderDeck();
    const user = userEvent.setup();
    expect(
      await screen.findByRole("heading", { name: "Stoner" }),
    ).toBeVisible();
    expect(
      await screen.findByRole("list", { name: "Covers to choose from" }),
    ).toBeVisible();
    const asked = calls.filter((call) => call.url.includes("cover-candidates"));
    expect(asked.map((call) => call.url)).toEqual([
      "/api/items/101/cover-candidates",
    ]);

    expect(
      screen.getByRole("button", { name: "Use this cover" }),
    ).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "The 1965 edition's cover" }),
    );
    await user.click(screen.getByRole("button", { name: "Use this cover" }));
    await waitFor(() =>
      expect(calls.filter((call) => call.method === "POST")).toEqual([
        {
          method: "POST",
          url: "/api/items/101/cover",
          body: { cover_url: "https://covers.example/b.jpg" },
        },
      ]),
    );
  });

  it("asks a domain that chooses no covers for its provider's own", async () => {
    const calls = stub();
    renderDeck();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Stoner" });
    await user.click(screen.getByRole("button", { name: /later/i }));
    expect(await screen.findByRole("heading", { name: "Kid A" })).toBeVisible();
    await user.click(
      await screen.findByRole("button", {
        name: "Ask the provider for its cover",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Use this cover" }));
    await waitFor(() =>
      expect(
        calls.filter((call) => call.method === "POST").map((call) => call.url),
      ).toEqual(["/api/items/102/cover/fetch"]),
    );
  });

  it("drops a candidate whose image does not load, rather than offer it", async () => {
    stub();
    renderDeck();
    const list = await screen.findByRole("list", {
      name: "Covers to choose from",
    });
    const broken = within(list).getByRole("button", {
      name: "The 2006 edition's cover",
    });
    fireEvent.error(broken.querySelector("img")!);
    await waitFor(() =>
      expect(
        within(list).queryByRole("button", {
          name: "The 2006 edition's cover",
        }),
      ).toBeNull(),
    );
    expect(
      within(list).getByRole("button", { name: "The 1965 edition's cover" }),
    ).toBeVisible();
  });
});
