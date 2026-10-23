import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("DiaryPage with a gentle goal", () => {
  const bookWithStatuses = {
    ...book,
    plural_label: "Books",
    entry_fields: ["date_started", "date_finished", "reread_count"],
    statuses: [
      {
        value: "reading",
        label: "Reading",
        choosable: true,
        hotkey: "g",
        in_progress: true,
      },
      {
        value: "to_read",
        label: "To read",
        choosable: true,
        hotkey: "t",
        planned: true,
      },
    ],
  };
  const albumType = {
    id: "album",
    label: "Album",
    plural_label: "Albums",
    statuses: [],
    fields: [],
    entry_fields: [],
  };
  const months = [2, 1, 3, 2, 0, 2, 4, 1, 1, 1, 0, 0];
  const pick = (id: number, title: string, reason: "creator" | "waiting") => ({
    entry: entry(id, "book", title),
    reason,
    creator: reason === "creator" ? "Julio Cortázar" : null,
    mean_score: reason === "creator" ? 9 : null,
    since: reason === "waiting" ? "2024-03-01T00:00:00Z" : null,
  });

  function stub(goals: unknown[]) {
    const calls: Array<{ url: string; method: string; body?: string }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      calls.push({
        url,
        method: init?.method ?? "GET",
        body: init?.body as string | undefined,
      });
      if (url.startsWith("/api/item-types"))
        return new Response(JSON.stringify([bookWithStatuses, albumType]));
      if (url.startsWith("/api/diary"))
        return new Response(
          JSON.stringify({
            year: new Date().getFullYear(),
            years: [],
            months: [],
          }),
        );
      if (url.includes("/progress"))
        return new Response(
          JSON.stringify({
            item_type: "book",
            year: new Date().getFullYear(),
            months,
            total: 17,
            target: 24,
          }),
        );
      if (url.includes("/picks"))
        return new Response(
          JSON.stringify([
            pick(10, "Bestiario", "creator"),
            pick(11, "The Dispossessed", "waiting"),
            pick(12, "Stoner", "waiting"),
          ]),
        );
      if (url.startsWith("/api/goals/book") && init?.method === "PUT")
        return new Response(
          JSON.stringify({
            item_type: "book",
            count: 3,
            period: "month",
            suggest: true,
          }),
        );
      if (url.startsWith("/api/entries/") && init?.method === "PATCH")
        return new Response(JSON.stringify(entry(10, "book", "Bestiario")));
      if (url === "/api/goals") return new Response(JSON.stringify(goals));
      return new Response("[]");
    });
    return calls;
  }

  function renderDiary() {
    return render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter>
          <DiaryPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  const goal = { item_type: "book", count: 2, period: "month", suggest: true };

  it("draws the year so far as a calendar of lights, nothing marked as missed", async () => {
    stub([goal]);
    renderDiary();
    const band = await screen.findByRole("region", { name: /books$/ });
    expect(band).toHaveTextContent("17 so far");
    const lit = band.querySelectorAll('[data-place="lit"]');
    expect(lit).toHaveLength(17);
    expect(band.querySelector('[data-place="missed"]')).toBeNull();
  });

  it("offers two picks with their reasons, swaps one, and starts one", async () => {
    const calls = stub([goal]);
    renderDiary();
    expect(
      await screen.findByText(
        "By Julio Cortázar, whose books you rate 9.0 on average.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Waiting since March 2024.")).toBeVisible();
    expect(screen.queryByText("Stoner")).toBeNull();

    const user = (await import("@testing-library/user-event")).default.setup();
    await user.click(
      screen.getAllByRole("button", { name: "Something else" })[1],
    );
    expect(await screen.findByText("Stoner")).toBeVisible();

    await user.click(screen.getAllByRole("button", { name: "Start" })[0]);
    const patch = calls.find((call) => call.method === "PATCH");
    expect(patch?.url).toBe("/api/entries/10");
    expect(JSON.parse(patch?.body ?? "{}")).toEqual({ status: "reading" });
  });

  it("invites a goal quietly when none is set, and sets one", async () => {
    const calls = stub([]);
    renderDiary();
    const user = (await import("@testing-library/user-event")).default.setup();
    await user.click(
      await screen.findByRole("button", { name: "Set a gentle goal" }),
    );
    // Only libraries that record a finish date can be counted.
    expect(screen.queryByRole("button", { name: "Albums" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "One more" }));
    expect(screen.getByText(/About 36 books in the year/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Set goal" }));
    const put = calls.find((call) => call.method === "PUT");
    expect(put?.url).toBe("/api/goals/book");
    expect(JSON.parse(put?.body ?? "{}")).toEqual({
      count: 3,
      period: "month",
      suggest: true,
    });
  });

  it("shows every year as one timeline, finishes and score changes together (Sprint 118)", async () => {
    const dune = (id: number, type: string) => ({
      ...entry(id, type, "Dune"),
      score: 9,
      shelves: [],
      formats: [],
    });
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/item-types"))
        return new Response(
          JSON.stringify([
            { ...book, plural_label: "Books" },
            { ...movie, plural_label: "Movies" },
          ]),
        );
      if (url.startsWith("/api/diary/timeline"))
        return new Response(
          JSON.stringify({
            events: [
              {
                kind: "score",
                at: "2026-03-02T10:00:00Z",
                entry: dune(1, "book"),
                score: 9,
                previous: 7,
                reason: "reread",
                note: "Better now",
              },
              {
                kind: "finished",
                at: "2021-10-22",
                entry: dune(2, "movie"),
                score: 8,
              },
              {
                kind: "finished",
                at: "2019-03-02",
                entry: dune(1, "book"),
                score: 9,
              },
            ],
            next_cursor: null,
          }),
        );
      if (url.startsWith("/api/diary"))
        return new Response(
          JSON.stringify({ year: 2026, years: [2026, 2021, 2019], months: [] }),
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
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "All years" }));
    const timeline = await screen.findByRole("list", { name: "Every year" });
    expect(
      within(timeline).getByRole("heading", { name: "2021" }),
    ).toBeVisible();
    const events = within(timeline)
      .getAllByRole("listitem")
      .filter((item) => item.hasAttribute("data-event"));
    expect(events.map((item) => item.textContent)).toEqual([
      expect.stringMatching(/Dune.*7 → 9.*reread.*Better now/),
      expect.stringMatching(/Dune.*Movie.*Finished/),
      expect.stringMatching(/Dune.*Book.*Finished/),
    ]);
  });
});
