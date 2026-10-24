import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RevisitDeckPage } from "./RevisitDeckPage";

function entry(
  id: number,
  title: string,
  score: number,
  notes: string | null = null,
) {
  return {
    id,
    item_id: id,
    status: "read",
    score,
    notes,
    date_added: "2020-01-01",
    date_started: null,
    date_finished: "2021-10-24",
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
      year: 1965,
      creator: "John Williams",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
  };
}

function stub() {
  const patches: Array<{ url: string; body: unknown }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (init?.method === "PATCH") {
      patches.push({ url, body: JSON.parse(String(init.body)) });
      return new Response(JSON.stringify(entry(1, "x", 9)));
    }
    if (url === "/api/revisit")
      return new Response(
        JSON.stringify({
          cards: [
            {
              entry: entry(1, "Stoner", 9, "The quietest book I have read."),
              scored_at: "2021-10-24",
            },
            { entry: entry(2, "Dune", 7), scored_at: "2019-10-22" },
          ],
          total: 2,
        }),
      );
    return new Response("[]");
  });
  return patches;
}

function renderDeck() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/deck/revisit"]}>
        <Routes>
          <Route path="/deck/revisit" element={<RevisitDeckPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("RevisitDeckPage (Sprint 121)", () => {
  it("asks whether an old score holds, and keeping it is history too", async () => {
    const patches = stub();
    renderDeck();
    const user = userEvent.setup();
    expect(
      await screen.findByRole("heading", { name: "Stoner" }),
    ).toBeVisible();
    expect(screen.getByText(/You gave it 9 in/)).toBeVisible();
    expect(screen.getByText("“The quietest book I have read.”")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Still a 9?" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Keep 9" }));
    await waitFor(() =>
      expect(patches).toEqual([
        { url: "/api/entries/1", body: { score: 9, score_reason: "time" } },
      ]),
    );
  });

  it("a changed score says why: going back to it, and a line", async () => {
    const patches = stub();
    renderDeck();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Stoner" });
    await user.click(screen.getByRole("button", { name: /later/i }));
    await screen.findByRole("heading", { name: "Dune" });
    await user.click(screen.getByRole("button", { name: "Score 6" }));
    await user.click(screen.getByRole("button", { name: "Went back to it" }));
    await user.type(
      screen.getByRole("textbox", { name: /why/i }),
      "Part Two made it look thin",
    );
    await user.click(screen.getByRole("button", { name: "Change to 6" }));
    await waitFor(() =>
      expect(patches).toEqual([
        {
          url: "/api/entries/2",
          body: {
            score: 6,
            score_reason: "reread",
            score_note: "Part Two made it look thin",
          },
        },
      ]),
    );
  });
});
