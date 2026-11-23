import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { daysOf, iso } from "./days";
import { EveryDay } from "./EveryDay";

afterEach(() => vi.restoreAllMocks());
beforeEach(() => localStorage.clear());

// Monday 23 November 2026, the day of the mockup.
const today = new Date(2026, 10, 23);

const entry = (id: number, title: string) => ({
  id,
  status: "reading",
  score: null,
  item: { id, type: "book", title, cover_url: null, year: 1963 },
});

function serve(lit: Array<{ day: string; entries: unknown[] }> = []) {
  const calls: Array<{ method: string; url: string; body?: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      calls.push({
        method,
        url,
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      });
      if (url.startsWith("/api/lit-days") && method === "PUT")
        return new Response(JSON.stringify({ day: "x", entries: [] }));
      if (url.startsWith("/api/lit-days") && method === "DELETE")
        return new Response(null, { status: 204 });
      if (url.startsWith("/api/lit-days"))
        return new Response(JSON.stringify({ days: lit }));
      if (url.startsWith("/api/now"))
        return new Response(
          JSON.stringify([entry(1, "Rayuela"), entry(2, "Frieren")]),
        );
      return new Response("[]");
    }),
  );
  return calls;
}

function renderWidget() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <EveryDay today={today} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("daysOf", () => {
  it("is this week, Monday to Sunday", () => {
    const { days, lead } = daysOf("week", new Date(2026, 10, 25));
    expect(days.map(iso)).toEqual([
      "2026-11-23",
      "2026-11-24",
      "2026-11-25",
      "2026-11-26",
      "2026-11-27",
      "2026-11-28",
      "2026-11-29",
    ]);
    expect(lead).toBe(0);
  });

  it("is this month, with the first day under its weekday", () => {
    // 1 November 2026 is a Sunday: six empty places before it, Monday first.
    const { days, lead } = daysOf("month", today);
    expect(days).toHaveLength(30);
    expect(iso(days[0])).toBe("2026-11-01");
    expect(lead).toBe(6);
  });
});

describe("EveryDay (Sprint 147, DEC-193)", () => {
  it("draws this month, never more, with the lit days lit and today marked", async () => {
    const calls = serve([
      { day: "2026-11-21", entries: [entry(1, "Rayuela")] },
      { day: "2026-11-22", entries: [] },
    ]);
    renderWidget();
    const grid = await screen.findByRole("list", {
      name: "2 days lit in November",
    });
    expect(within(grid).getAllByRole("button")).toHaveLength(30);
    expect(
      within(grid).getByRole("button", {
        name: "Saturday 21 November, lit for Rayuela",
      }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      within(grid).getByRole("button", { name: "Sunday 22 November, lit" }),
    ).toHaveAttribute("aria-pressed", "true");
    const now = within(grid).getByRole("button", {
      name: "Monday 23 November, not lit",
    });
    expect(now).toHaveAttribute("aria-current", "date");
    // A day to come cannot be lit.
    expect(
      within(grid).getByRole("button", {
        name: "Tuesday 24 November, to come",
      }),
    ).toBeDisabled();
    expect(calls[0].url).toBe("/api/lit-days?from=2026-11-01&to=2026-11-30");
  });

  it("switches to this week and remembers it", async () => {
    const calls = serve();
    renderWidget();
    await userEvent.click(
      await screen.findByRole("button", { name: "This week" }),
    );
    const grid = await screen.findByRole("list", {
      name: "0 of 7 days lit this week",
    });
    expect(within(grid).getAllByRole("button")).toHaveLength(7);
    expect(
      calls.some(
        (call) => call.url === "/api/lit-days?from=2026-11-23&to=2026-11-29",
      ),
    ).toBe(true);
    expect(localStorage.getItem("akasha.journal.everyday")).toBe("week");
  });

  it("asks what a day was for, offering what is under way, and lights it for what is chosen", async () => {
    const calls = serve();
    renderWidget();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", {
        name: "Monday 23 November, not lit",
      }),
    );
    const question = await screen.findByRole("group", {
      name: "What was it for?",
    });
    expect(question).toHaveTextContent("What was Monday 23 November for?");
    // Nothing chosen yet: it can be lit for nothing in particular.
    expect(
      within(question).getByRole("button", { name: "Just light it" }),
    ).toBeVisible();
    await user.click(
      await within(question).findByRole("button", { name: "Rayuela" }),
    );
    await user.click(
      within(question).getByRole("button", { name: "Light it" }),
    );
    await waitFor(() =>
      expect(calls.find((call) => call.method === "PUT")).toMatchObject({
        body: { entry_ids: [1] },
      }),
    );
    expect(calls.find((call) => call.method === "PUT")!.url).toMatch(
      /^\/api\/lit-days\/2026-11-23/,
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("group", { name: "What was it for?" }),
      ).toBeNull(),
    );
  });

  it("lights a day for nothing in particular in one more tap", async () => {
    const calls = serve();
    renderWidget();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", {
        name: "Sunday 22 November, not lit",
      }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Just light it" }),
    );
    await waitFor(() =>
      expect(calls.find((call) => call.method === "PUT")).toMatchObject({
        body: { entry_ids: [] },
      }),
    );
  });

  it("says what a lit day was for, and unlights it", async () => {
    const calls = serve([
      { day: "2026-11-21", entries: [entry(1, "Rayuela")] },
    ]);
    renderWidget();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", {
        name: "Saturday 21 November, lit for Rayuela",
      }),
    );
    const day = await screen.findByRole("group", {
      name: "Saturday 21 November",
    });
    expect(
      within(day).getByRole("link", { name: "Open Rayuela" }),
    ).toHaveAttribute("href", "/books/1");
    await user.click(within(day).getByRole("button", { name: "Unlight" }));
    await waitFor(() =>
      expect(calls.find((call) => call.method === "DELETE")?.url).toBe(
        "/api/lit-days/2026-11-21",
      ),
    );
  });

  it("can be left without lighting anything", async () => {
    const calls = serve();
    renderWidget();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", {
        name: "Monday 23 November, not lit",
      }),
    );
    await user.click(await screen.findByRole("button", { name: "Not now" }));
    expect(
      screen.queryByRole("group", { name: "What was it for?" }),
    ).toBeNull();
    expect(calls.some((call) => call.method === "PUT")).toBe(false);
  });
});
