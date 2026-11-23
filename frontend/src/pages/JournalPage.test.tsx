import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { widgetKey } from "@/features/journal/JournalWidgets";
import { JournalPage } from "@/pages/JournalPage";

afterEach(() => vi.restoreAllMocks());
beforeEach(() => localStorage.clear());

const bookType = {
  id: "book",
  label: "Book",
  plural_label: "Books",
  fields: [],
  statuses: [
    { value: "read", label: "Read", finished: true },
    { value: "to_read", label: "To read", planned: true },
  ],
  default_status: "to_read",
  entry_fields: ["date_started", "date_finished"],
  formats: [],
};

function serve() {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      urls.push(url);
      if (url.startsWith("/api/item-types"))
        return new Response(JSON.stringify([bookType]));
      if (url.startsWith("/api/diary"))
        return new Response(
          JSON.stringify({ year: 2026, years: [2026], months: [] }),
        );
      if (url.startsWith("/api/goals")) return new Response("[]");
      if (url.startsWith("/api/lit-days"))
        return new Response(JSON.stringify({ days: [] }));
      if (url.startsWith("/api/insights/summary"))
        return new Response(JSON.stringify({ held: 0 }));
      if (url.startsWith("/api/insights/scores"))
        return new Response(
          JSON.stringify({
            type: "book",
            counts: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            rated_count: 0,
            unrated_count: 0,
          }),
        );
      if (url.startsWith("/api/insights"))
        return new Response(
          JSON.stringify({ rows: [], next_cursor: null, suppressed: [] }),
        );
      if (url.startsWith("/api/entries"))
        return new Response(
          JSON.stringify({ items: [], total: 0, next_cursor: null }),
        );
      return new Response("[]");
    }),
  );
  return urls;
}

function renderJournal(at = "/journal") {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={[at]}>
        <Routes>
          <Route path="/journal" element={<JournalPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("JournalPage (Sprint 146, DEC-193)", () => {
  it("is one page: something to do, then the timeline, then the patterns", async () => {
    serve();
    renderJournal();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Journal" }),
    ).toBeVisible();
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((heading) => heading.textContent);
    expect(headings.indexOf("Timeline")).toBeGreaterThanOrEqual(0);
    expect(headings.indexOf("Patterns")).toBeGreaterThan(
      headings.indexOf("Timeline"),
    );
    // Neither part brings its own page title along.
    expect(screen.queryByRole("heading", { name: "Diary" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Insights" })).toBeNull();
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });

  it("opens on a widget, switches to another without leaving, and remembers it", async () => {
    serve();
    const { unmount } = renderJournal();
    const tabs = await screen.findByRole("tablist", { name: "Journal widget" });
    // Every day leads (Sprint 147).
    expect(
      within(tabs).getByRole("tab", { name: "Every day" }),
    ).toHaveAttribute("aria-selected", "true");
    await userEvent.click(within(tabs).getByRole("tab", { name: "Goal" }));
    expect(within(tabs).getByRole("tab", { name: "Goal" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    // The Diary's invitation, now the Goal widget's.
    expect(
      await within(screen.getByRole("tabpanel")).findByText(
        /Want something to aim at/,
      ),
    ).toBeVisible();
    expect(localStorage.getItem(widgetKey)).toBe("goal");

    unmount();
    renderJournal();
    expect(await screen.findByRole("tab", { name: "Goal" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("moves between the widgets with the arrow keys", async () => {
    serve();
    renderJournal();
    const play = await screen.findByRole("tab", { name: "Play" });
    await userEvent.click(play);
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Goal" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Goal" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("offers the decks from the Play widget, which had no door but Settings", async () => {
    serve();
    renderJournal();
    await userEvent.click(await screen.findByRole("tab", { name: "Play" }));
    const panel = await screen.findByRole("tabpanel");
    expect(
      within(panel).getByRole("link", { name: "Tidy up" }),
    ).toHaveAttribute("href", "/deck");
    expect(within(panel).getByRole("link", { name: "Tiers" })).toHaveAttribute(
      "href",
      "/tiers",
    );
  });

  it("lands an old address on its part of the page", async () => {
    serve();
    renderJournal("/journal#patterns");
    const patterns = await screen.findByRole("heading", { name: "Patterns" });
    expect(patterns).toHaveFocus();
  });
});
