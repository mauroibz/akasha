import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { findToast } from "@/test/toast";
import { ShelfPage } from "./ShelfPage";

const bookType = {
  id: "book",
  label: "Book",
  fields: [],
  statuses: [
    { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
    { value: "read", label: "Read", choosable: true, hotkey: "r" },
  ],
  default_status: "read",
  entry_fields: [],
  formats: [{ value: "physical", label: "Physical" }],
  entry_panel_label: "Your reading data",
};

const albumType = {
  ...bookType,
  id: "album",
  label: "Album",
  statuses: [
    { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
    { value: "owned", label: "Owned", choosable: true, hotkey: "o" },
  ],
  default_status: "owned",
  formats: [{ value: "vinyl", label: "Vinyl" }],
};

const mixedShelf = {
  id: 1,
  name: "Mixed",
  slug: "mixed",
  entry_count: 2,
  covers: [],
  members_by_type: { book: 1, album: 1 },
};

function entry(id: number, type: string, title: string) {
  return {
    id,
    item_id: id,
    status: type === "book" ? "read" : "owned",
    score: null,
    notes: null,
    date_added: "2026-01-01T00:00:00Z",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: null,
    score_provisional: false,
    suggested_status: null,
    shelves: [{ id: 1, name: "Mixed", slug: "mixed" }],
    formats: [],
    item: {
      id,
      type,
      title,
      subtitle: null,
      year: 2020,
      creator: "Someone",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
  };
}

function stubApi({
  shelves = [mixedShelf],
  entries = [entry(1, "book", "Rayuela"), entry(2, "album", "Discovery")],
  types = [bookType, albumType],
} = {}) {
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url === "/api/item-types") return new Response(JSON.stringify(types));
    if (url === "/api/shelves") return new Response(JSON.stringify(shelves));
    if (url.startsWith("/api/entries?")) {
      const params = new URL(url, "http://library.test").searchParams;
      const type = params.get("type");
      const matched = type
        ? entries.filter((row) => row.item.type === type)
        : entries;
      return new Response(
        JSON.stringify({
          items: matched,
          next_cursor: null,
          total: matched.length,
          facets: {
            status_counts: { read: 1, owned: 1 },
            status_counts_by_type: {},
            format_counts: {},
          },
        }),
      );
    }
    if (init?.method === "PATCH" && url.includes("/api/shelves/1"))
      return new Response(
        JSON.stringify({ id: 1, name: "Best", slug: "best", entry_count: 2 }),
      );
    if (init?.method === "DELETE" && url.includes("/api/shelves/1"))
      return new Response(null, { status: 204 });
    return new Response("[]");
  });
  return calls;
}

function renderPage(slug = "mixed") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/shelves/${slug}`]}>
        <Routes>
          <Route path="/shelves/:slug" element={<ShelfPage />} />
          <Route path="/shelves" element={<div>Shelves board</div>} />
        </Routes>
      </MemoryRouter>
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("ShelfPage", () => {
  it("shows every domain the shelf holds by default, spanning both", async () => {
    stubApi();
    renderPage();
    await screen.findByRole("heading", { name: "Mixed" });
    await screen.findByText("Rayuela");
    expect(screen.getByText("Discovery")).toBeVisible();
  });

  it("offers only the domains this shelf actually holds in its strip", async () => {
    stubApi();
    renderPage();
    await screen.findByRole("heading", { name: "Mixed" });
    const strip = screen.getByRole("radiogroup", { name: "Choose a domain" });
    expect(
      within(strip).getByRole("radio", { name: "Everything" }),
    ).toBeVisible();
    expect(within(strip).getByRole("radio", { name: "Book" })).toBeVisible();
    expect(within(strip).getByRole("radio", { name: "Album" })).toBeVisible();
    expect(
      within(strip).queryByRole("radio", { name: "Anime" }),
    ).not.toBeInTheDocument();
  });

  it("narrows to one domain when chosen from the strip", async () => {
    stubApi();
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Rayuela");
    expect(screen.getByText("Discovery")).toBeVisible();

    await user.click(screen.getByRole("radio", { name: "Book" }));

    await waitFor(() => {
      expect(screen.queryByText("Discovery")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Rayuela")).toBeVisible();
  });

  it("the card's count equals the page's entry count for a mixed shelf", async () => {
    stubApi();
    renderPage();
    await screen.findByRole("heading", { name: "Mixed" });
    // The shelf's own entry_count (from the board) matches the page's total.
    expect(screen.getByText("2")).toBeVisible();
    await screen.findByText("Rayuela");
    expect(screen.getByText("Discovery")).toBeVisible();
  });

  it("renames the shelf, with the change reflected immediately", async () => {
    stubApi();
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Mixed" });

    await user.click(screen.getByRole("button", { name: "Rename" }));
    const input = await screen.findByDisplayValue("Mixed");
    await user.clear(input);
    await user.type(input, "Best");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await findToast('Shelf renamed to "Best"')).toBeInTheDocument();
  });

  it("deletes the shelf with confirmation, stating entries are retained", async () => {
    stubApi();
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Mixed" });

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(screen.getByText(/entries.*retained/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete shelf" }));

    expect(await findToast("Shelf deleted")).toBeInTheDocument();
  });

  it("pins and unpins the shelf, remembered across renders", async () => {
    stubApi();
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Mixed" });

    await user.click(screen.getByRole("button", { name: "Pin to library" }));
    expect(screen.getByRole("button", { name: "Pinned" })).toBeVisible();
    expect(localStorage.getItem("akasha.library.pinnedShelf")).toContain(
      "mixed",
    );

    await user.click(screen.getByRole("button", { name: "Pinned" }));
    expect(
      screen.getByRole("button", { name: "Pin to library" }),
    ).toBeVisible();
    expect(localStorage.getItem("akasha.library.pinnedShelf")).toBeNull();
  });
});
