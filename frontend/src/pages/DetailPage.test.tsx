import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { findToast } from "@/test/toast";
import { DetailPage } from "./DetailPage";

const entry = {
  id: 7,
  item_id: 3,
  status: "reading",
  score: 8,
  notes: "Cached note",
  date_added: "2026-07-22",
  date_started: null,
  date_finished: null,
  reread_count: 0,
  score_provisional: false,
  suggested_status: null,
  item: {
    id: 3,
    type: "book",
    title: "Rayuela",
    subtitle: null,
    year: 1963,
    sort_author: "Julio Cortázar",
    cover_path: null,
    cover_url: null,
    metadata: {
      authors: ["Julio Cortázar"],
      publisher: "Sudamericana",
      language: "es",
      page_count: 736,
      subjects: ["Argentine fiction"],
      series: null,
      description: "A novel",
      original_year: 1963,
    },
    identifiers: { isbn13: "9788437604572" },
    sources: [{ source: "openlibrary", source_id: "OL1M", is_primary: true }],
  },
  shelves: [{ id: 1, name: "Favorites", slug: "favorites" }],
};

function renderPage(initialPath = "/books/7", extraRoutes?: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/books/:entryId" element={<DetailPage />} />
          <Route path="/" element={extraRoutes ?? <div>Library page</div>} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("DetailPage", () => {
  it("renders cached detail and persists opinion and metadata edits", async () => {
    const request = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (url === "/api/shelves") return new Response("[]");
        if (!init) return new Response(JSON.stringify(entry));
        if (url.includes("/entries/"))
          return new Response(JSON.stringify({ ...entry, notes: "Loved it" }));
        return new Response(
          JSON.stringify({ ...entry.item, title: "Rayuela corregida" }),
        );
      });
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "Rayuela" }),
    ).toBeVisible();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /edit opinion/i }));
    await user.clear(screen.getByLabelText(/notes/i));
    await user.type(screen.getByLabelText(/notes/i), "Loved it");
    await user.click(screen.getByRole("button", { name: /save opinion/i }));
    await user.click(
      screen.getByRole("button", { name: /edit book metadata/i }),
    );
    await user.clear(screen.getByLabelText(/^title$/i));
    await user.type(screen.getByLabelText(/^title$/i), "Rayuela corregida");
    await user.click(screen.getByRole("button", { name: /save metadata/i }));
    expect(request).toHaveBeenCalledWith(
      "/api/entries/7",
      expect.objectContaining({ method: "PATCH" }),
    );
    expect(request).toHaveBeenCalledWith(
      "/api/items/3",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("renders all standard metadata fields", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    await screen.findByRole("heading", { name: "Rayuela" });
    expect(screen.getByText("Sudamericana")).toBeVisible();
    expect(screen.getByText("es")).toBeVisible();
    expect(screen.getByText("736")).toBeVisible();
    expect(screen.getByText(/isbn13.*9788437604572/i)).toBeVisible();
    expect(screen.getByText("openlibrary (primary)")).toBeVisible();
    expect(screen.getByText("Argentine fiction")).toBeVisible();
    expect(screen.getByText("Favorites")).toBeVisible();
  });

  it("confirmed deletion calls DELETE and returns to library", async () => {
    const requests: Array<[string, RequestInit?]> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      requests.push([url, init]);
      if (url === "/api/shelves") return new Response("[]");
      if (init?.method === "DELETE" && url === "/api/entries/7")
        return new Response(null, { status: 204 });
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    // Click the delete entry button in the main page (not the dialog one)
    await user.click(
      screen.getAllByRole("button", { name: /delete entry/i })[0],
    );
    // Confirmation dialog appears
    expect(
      screen.getByRole("dialog", { name: /confirm entry deletion/i }),
    ).toBeVisible();
    // Click the confirm button inside the dialog
    await user.click(
      screen.getAllByRole("button", { name: /delete entry/i })[1],
    );
    // DELETE was called
    const deleteReq = requests.find(
      ([url, init]) => url === "/api/entries/7" && init?.method === "DELETE",
    );
    expect(deleteReq).toBeDefined();
    // Navigated back to library
    await waitFor(() => expect(screen.getByText("Library page")).toBeVisible());
    // The confirmation is shown on the visible toast surface, not stashed in
    // storage for the next route to render into a hidden paragraph.
    expect(
      await findToast("Book removed from your library"),
    ).toBeInTheDocument();
  });

  it("cancel preserves the entry and does not call DELETE", async () => {
    const requests: Array<[string, RequestInit?]> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      requests.push([url, init]);
      if (url === "/api/shelves") return new Response("[]");
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(screen.getByRole("button", { name: /delete entry/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    const deleteReq = requests.find(
      ([url, init]) => url === "/api/entries/7" && init?.method === "DELETE",
    );
    expect(deleteReq).toBeUndefined();
    // Entry is still visible
    expect(screen.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  });

  it("delete failure preserves the entry with an error", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (init?.method === "DELETE" && url === "/api/entries/7")
        return new Response(
          JSON.stringify({ error: { code: "entry_not_found" } }),
          { status: 404 },
        );
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(
      screen.getAllByRole("button", { name: /delete entry/i })[0],
    );
    await user.click(
      screen.getAllByRole("button", { name: /delete entry/i })[1],
    );
    // Entry remains visible with error
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  });

  it("Escape closes dialogs", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(screen.getByRole("button", { name: /delete entry/i }));
    expect(
      screen.getByRole("dialog", { name: /confirm entry deletion/i }),
    ).toBeVisible();
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("dialog", { name: /confirm entry deletion/i }),
    ).not.toBeInTheDocument();
  });
});
