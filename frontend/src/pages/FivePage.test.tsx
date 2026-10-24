import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FivePage } from "./FivePage";

const book = {
  id: "book",
  label: "Book",
  plural_label: "Books",
  fields: [],
  statuses: [
    { value: "read", label: "Read", finished: true },
    { value: "to_read", label: "To read", planned: true },
  ],
  entry_fields: ["date_started", "date_finished", "reread_count"],
  formats: [{ value: "physical", label: "Physical" }],
};

const entry = (
  id: number,
  title: string,
  more: Record<string, unknown> = {},
) => ({
  id,
  status: "read",
  score: 8,
  score_rank: null,
  date_started: "2019-01-01",
  date_finished: "2019-02-01",
  formats: ["physical"],
  location: "Hall",
  unknown_fields: [],
  date_added: "2026-01-01T00:00:00Z",
  item: { id, type: "book", title, cover_url: null, metadata: {} },
  ...more,
});

afterEach(() => vi.restoreAllMocks());

describe("FivePage (Sprint 126)", () => {
  it("mixes a round, writes each answer as its game does, and ends with what changed", async () => {
    const calls: Array<{ url: string; method: string; body: unknown }> = [];
    const eights = [
      entry(1, "Matadero cinco", { score_rank: 1 }),
      entry(2, "Every day"),
    ];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const json = (body: unknown) => new Response(JSON.stringify(body));
      if (method !== "GET") {
        calls.push({ url, method, body: JSON.parse(String(init?.body)) });
        return json(url.endsWith("/rank") ? eights : eights[0]);
      }
      if (url === "/api/item-types") return json([book]);
      if (url.startsWith("/api/insights/scores"))
        return json({ counts: [0, 0, 0, 0, 0, 0, 0, 2, 0, 0] });
      if (url === "/api/gaps")
        return json({
          entries: [entry(3, "Rayuela", { date_finished: null })],
          total: 1,
        });
      if (url === "/api/revisit")
        return json({
          cards: [
            {
              entry: entry(4, "Tokio blues", { score: 10 }),
              scored_at: "2021-01-01",
            },
          ],
          total: 1,
        });
      if (url.includes("score=8")) return json({ items: eights, total: 2 });
      if (url.startsWith("/api/entries"))
        return json({
          items: [entry(5, "Release It!", { status: "to_read", score: null })],
          total: 1,
        });
      return json([]);
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <FivePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();
    expect(await screen.findByText("1 of 4")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Which did you like more?" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Every day/ }));
    await waitFor(() =>
      expect(calls[0]).toEqual({
        url: "/api/entries/rank",
        method: "PUT",
        body: { entry_ids: [2, 1] },
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "When did you finish it?" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "I don't remember" }));

    expect(
      await screen.findByRole("heading", {
        name: "Is Tokio blues still a 10?",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Keep 10" }));
    await waitFor(() =>
      expect(calls.at(-1)?.body).toEqual({ score: 10, score_reason: "time" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Still want Release It!?" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Let go" }));

    expect(
      await screen.findByRole("heading", { name: "Five minutes, done" }),
    ).toBeVisible();
    expect(screen.getByText("Every day above Matadero cinco")).toBeVisible();
    expect(screen.getByText("Tokio blues is still a 10")).toBeVisible();
    // Letting go is asked once more before anything is removed.
    expect(calls.some((call) => call.method === "DELETE")).toBe(false);
    expect(
      screen.getByRole("button", { name: "Remove the 1 you let go" }),
    ).toBeVisible();
  });
});
