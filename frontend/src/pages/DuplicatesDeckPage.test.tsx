import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DuplicatesDeckPage } from "./DuplicatesDeckPage";

function entry(id: number, title: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    item_id: id,
    status: "read",
    score: null,
    notes: null,
    date_added: "2024-01-01T00:00:00Z",
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
      year: 1963,
      creator: "Julio Cortázar",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    ...extra,
  };
}

const pairs = [
  {
    a: entry(1, "Rayuela", { score: 9 }),
    b: entry(2, "Rayuela (Alfaguara)", { score: 6 }),
    reason: "Same title and creator",
  },
  {
    a: entry(1, "Rayuela", { score: 9 }),
    b: entry(3, "Rayuela: edición"),
    reason: "Same title and creator",
  },
  {
    a: entry(4, "Solaris"),
    b: entry(5, "Solaris (Faber)"),
    reason: "Same title and creator",
  },
];

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
    if (url === "/api/duplicates") return new Response(JSON.stringify(pairs));
    if (url === "/api/duplicates/merge")
      return new Response(JSON.stringify(entry(1, "Rayuela")));
    if (url === "/api/duplicates/dismiss")
      return new Response(null, { status: 204 });
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
      <MemoryRouter initialEntries={["/deck/duplicates"]}>
        <Routes>
          <Route path="/deck/duplicates" element={<DuplicatesDeckPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

const writes = (calls: ReturnType<typeof stub>) =>
  calls.filter((call) => call.method !== "GET");

describe("DuplicatesDeckPage (Sprint 113)", () => {
  it("merges into the one chosen, after saying what happens, and cannot be undone", async () => {
    const calls = stub();
    renderDeck();
    const user = userEvent.setup();
    const left = await screen.findByRole("group", { name: "Rayuela" });
    const right = screen.getByRole("group", { name: "Rayuela (Alfaguara)" });
    // What differs is marked.
    expect(within(left).getByText("9")).toBeVisible();
    expect(within(right).getByText("6")).toBeVisible();
    expect(screen.getByRole("button", { name: "Merge" })).toBeDisabled();
    await user.click(
      within(right).getByRole("button", { name: "Keep this one" }),
    );
    expect(screen.getByText(/Rayuela is removed/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Merge" }));
    await waitFor(() =>
      expect(writes(calls)).toEqual([
        {
          method: "POST",
          url: "/api/duplicates/merge",
          body: { keep: 2, drop: 1 },
        },
      ]),
    );
    // The pair that held the removed entry is gone; Solaris is next.
    expect(await screen.findByRole("group", { name: "Solaris" })).toBeVisible();
    expect(screen.getByRole("button", { name: /undo/i })).toBeDisabled();
  });

  it("remembers that two differ, and can take that back", async () => {
    const calls = stub();
    renderDeck();
    const user = userEvent.setup();
    await screen.findByRole("group", { name: "Rayuela" });
    await user.click(screen.getByRole("button", { name: "They’re different" }));
    await screen.findByRole("group", { name: "Rayuela: edición" });
    await user.click(screen.getByRole("button", { name: /undo/i }));
    await waitFor(() =>
      expect(writes(calls)).toEqual([
        {
          method: "POST",
          url: "/api/duplicates/dismiss",
          body: { a: 1, b: 2 },
        },
        {
          method: "DELETE",
          url: "/api/duplicates/dismiss",
          body: { a: 1, b: 2 },
        },
      ]),
    );
  });
});
