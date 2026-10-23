import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TiersPage } from "./TiersPage";

function entry(
  id: number,
  title: string,
  score: number,
  rank: number | null = null,
) {
  return {
    id,
    item_id: id,
    status: "read",
    score,
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

function stub() {
  const writes: Array<{ method: string; url: string; body: unknown }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url === "/api/item-types")
      return new Response(JSON.stringify([bookType]));
    if (method !== "GET") {
      const body = JSON.parse(String(init?.body));
      writes.push({ method, url, body });
      return new Response(
        JSON.stringify(
          method === "PUT" ? [] : { ...entry(1, "x", 9), ...body },
        ),
      );
    }
    if (url.startsWith("/api/entries?"))
      return new Response(
        JSON.stringify({
          items: [
            entry(1, "Piranesi", 9),
            entry(2, "Solaris", 8, 1),
            entry(3, "Stoner", 8, 2),
            entry(4, "Ficciones", 6),
          ],
          next_cursor: null,
          total: 4,
          facets: {
            status_counts: {},
            status_counts_by_type: {},
            format_counts: {},
          },
        }),
      );
    return new Response("[]");
  });
  return writes;
}

function renderBoard() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/tiers/book"]}>
        <Routes>
          <Route path="/tiers/:type" element={<TiersPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("TiersPage (Sprint 117)", () => {
  it("proposes a move to another score and writes it only on Apply", async () => {
    const writes = stub();
    renderBoard();
    const user = userEvent.setup();
    const eight = await screen.findByRole("group", { name: "8" });
    expect(
      within(eight)
        .getAllByRole("button")
        .map((b) => b.getAttribute("aria-label")),
    ).toEqual([
      expect.stringContaining("Solaris"),
      expect.stringContaining("Stoner"),
      "Place it here, as 8",
    ]);
    await user.click(within(eight).getByRole("button", { name: /Stoner/ }));
    await user.click(
      within(screen.getByRole("group", { name: "9" })).getByRole("button", {
        name: "Place it here, as 9",
      }),
    );
    const pending = screen.getByRole("region", { name: "Changes to apply" });
    expect(pending).toHaveTextContent("Stoner 8 → 9");
    expect(writes).toEqual([
      { method: "PUT", url: "/api/entries/rank", body: { entry_ids: [2] } },
    ]);
    await user.click(
      within(pending).getByRole("button", { name: "Apply 1 change" }),
    );
    await waitFor(() =>
      expect(writes.slice(1)).toEqual([
        {
          method: "PATCH",
          url: "/api/entries/3",
          body: { score: 9, score_reason: "time" },
        },
        {
          method: "PUT",
          url: "/api/entries/rank",
          body: { entry_ids: [1, 3] },
        },
      ]),
    );
  });

  it("discards proposals without writing them", async () => {
    const writes = stub();
    renderBoard();
    const user = userEvent.setup();
    const six = await screen.findByRole("group", { name: "6" });
    await user.click(within(six).getByRole("button", { name: /Ficciones/ }));
    await user.click(
      within(screen.getByRole("group", { name: "7" })).getByRole("button", {
        name: "Place it here, as 7",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Discard" }));
    expect(
      within(screen.getByRole("group", { name: "6" })).getByRole("button", {
        name: /Ficciones/,
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("region", { name: "Changes to apply" }),
    ).toBeNull();
    expect(writes).toEqual([]);
  });

  it("reorders inside a score at once, from the keyboard too", async () => {
    const writes = stub();
    renderBoard();
    const user = userEvent.setup();
    const eight = await screen.findByRole("group", { name: "8" });
    within(eight)
      .getByRole("button", { name: /Stoner/ })
      .focus();
    await user.keyboard("{Enter}{ArrowLeft}{Enter}");
    await waitFor(() =>
      expect(writes).toEqual([
        {
          method: "PUT",
          url: "/api/entries/rank",
          body: { entry_ids: [3, 2] },
        },
      ]),
    );
  });

  it("discarding a proposal keeps an order already saved", async () => {
    const writes = stub();
    renderBoard();
    const user = userEvent.setup();
    const eight = await screen.findByRole("group", { name: "8" });
    within(eight)
      .getByRole("button", { name: /Stoner/ })
      .focus();
    await user.keyboard("{Enter}{ArrowLeft}{Enter}");
    await waitFor(() => expect(writes).toHaveLength(1));
    await user.click(
      within(screen.getByRole("group", { name: "6" })).getByRole("button", {
        name: /Ficciones/,
      }),
    );
    await user.click(
      within(screen.getByRole("group", { name: "7" })).getByRole("button", {
        name: "Place it here, as 7",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Discard" }));
    const titles = within(screen.getByRole("group", { name: "8" }))
      .getAllByRole("button")
      .map((button) => button.getAttribute("aria-label"));
    expect(titles.slice(0, 2)).toEqual(["Stoner", "Solaris"]);
  });
});
