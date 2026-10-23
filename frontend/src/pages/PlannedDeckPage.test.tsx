import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { PlannedDeckPage } from "./PlannedDeckPage";

const bookType = {
  id: "book",
  label: "Book",
  fields: [],
  statuses: [
    { value: "read", label: "Read", choosable: true },
    { value: "to_read", label: "To read", choosable: true, planned: true },
  ],
  default_status: "read",
  entry_fields: [],
  formats: [],
  entry_panel_label: "Your reading data",
};
const movieType = {
  ...bookType,
  id: "movie",
  label: "Movie",
  statuses: [
    { value: "watched", label: "Watched", choosable: true },
    { value: "watchlist", label: "Watchlist", choosable: true, planned: true },
  ],
};

function entry(id: number, title: string, type = "book") {
  return {
    id,
    item_id: id,
    status: type === "book" ? "to_read" : "watchlist",
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
      id,
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

function stub(
  entries = [
    entry(1, "Stoner"),
    entry(2, "Solaris", "movie"),
    entry(3, "Ficciones"),
  ],
) {
  const calls: Array<{ method: string; url: string; body?: unknown }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    calls.push({
      method,
      url,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    if (url === "/api/item-types")
      return new Response(JSON.stringify([bookType, movieType]));
    if (url.startsWith("/api/entries?"))
      return new Response(
        JSON.stringify({
          items: entries,
          next_cursor: null,
          total: entries.length,
          facets: {
            status_counts: {},
            status_counts_by_type: {},
            format_counts: {},
          },
        }),
      );
    if (method === "DELETE")
      return new Response(JSON.stringify({ affected: 1 }));
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
      <MemoryRouter initialEntries={["/deck/planned"]}>
        <Routes>
          <Route path="/deck/planned" element={<PlannedDeckPage />} />
          <Route path="/deck" element={<div>The chores</div>} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("PlannedDeckPage (Sprint 112)", () => {
  it("goes through every domain's planned pile, oldest first", async () => {
    const calls = stub();
    renderDeck();
    expect(
      await screen.findByRole("heading", { name: "Stoner" }),
    ).toBeVisible();
    const list = calls.find((call) =>
      call.url.startsWith("/api/entries?"),
    )!.url;
    expect(list).toContain("status=to_read");
    expect(list).toContain("status=watchlist");
    expect(list).toContain("sort=date_added");
    expect(list).toContain("order=asc");
  });

  it("deletes nothing until the end, and then only what was let go, once confirmed", async () => {
    const calls = stub();
    renderDeck();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Stoner" });
    await user.click(screen.getByRole("button", { name: "Keep" }));
    await screen.findByRole("heading", { name: "Solaris" });
    await user.click(screen.getByRole("button", { name: "Let go" }));
    await screen.findByRole("heading", { name: "Ficciones" });
    await user.click(screen.getByRole("button", { name: "Let go" }));
    // Undo before the end: Ficciones comes back, and nothing was ever sent.
    await user.click(screen.getByRole("button", { name: /undo/i }));
    await screen.findByRole("heading", { name: "Ficciones" });
    await user.click(screen.getByRole("button", { name: "Keep" }));
    expect(calls.filter((call) => call.method !== "GET")).toEqual([]);

    await user.click(
      await screen.findByRole("button", { name: "Remove the 1 you let go" }),
    );
    const confirm = await screen.findByRole("alertdialog");
    expect(confirm).toHaveTextContent("Solaris");
    await user.click(within(confirm).getByRole("button", { name: "Remove 1" }));
    await waitFor(() =>
      expect(calls.filter((call) => call.method === "DELETE")).toEqual([
        {
          method: "DELETE",
          url: "/api/entries/bulk",
          body: { entry_ids: [2] },
        },
      ]),
    );
    expect(await screen.findByText(/Removed 1/)).toBeVisible();
  });
});
