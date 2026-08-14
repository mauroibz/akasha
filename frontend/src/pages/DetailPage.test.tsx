import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
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
  it("offers the editions of the work as covers and installs the chosen one", async () => {
    const candidates = {
      candidates: [
        {
          cover_url: "https://covers.openlibrary.org/b/id/15104001-L.jpg",
          source_id: "OL59588323M",
          title: "Il gioco del mondo",
          year: 1969,
        },
        {
          cover_url: "https://covers.openlibrary.org/b/id/15103989-L.jpg",
          source_id: "OL59587941M",
          title: "Marelle",
          year: 1966,
        },
      ],
      reason: null,
    };
    const request = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (url === "/api/shelves") return new Response("[]");
        if (url.includes("/cover-candidates"))
          return new Response(JSON.stringify(candidates));
        if (init?.method === "POST")
          return new Response(
            JSON.stringify({
              ...entry.item,
              cover_url: "/api/items/3/cover",
            }),
          );
        return new Response(JSON.stringify(entry));
      });
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "Rayuela" }),
    ).toBeVisible();
    const user = userEvent.setup();

    // Candidates must not be fetched until the chooser is opened: a library page
    // that reaches a provider on render is the invariant this feature must not break.
    expect(
      request.mock.calls.filter(([url]) =>
        String(url).includes("/cover-candidates"),
      ),
    ).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: /choose a cover/i }));
    const chooser = await screen.findByRole("dialog");
    expect(
      await within(chooser).findByRole("button", { name: /1969 edition/i }),
    ).toBeVisible();

    await user.click(
      within(chooser).getByRole("button", { name: /1966 edition/i }),
    );
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/items/3/cover",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            cover_url: "https://covers.openlibrary.org/b/id/15103989-L.jpg",
          }),
        }),
      ),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("explains an empty chooser instead of showing an empty grid", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (url.includes("/cover-candidates"))
        return new Response(
          JSON.stringify({ candidates: [], reason: "no_provider_reference" }),
        );
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "Rayuela" }),
    ).toBeVisible();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /choose a cover/i }));
    const chooser = await screen.findByRole("dialog");
    expect(
      await within(chooser).findByText(/nothing to look editions up by/i),
    ).toBeVisible();
  });

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
      screen.getByRole("alertdialog", { name: /remove this book/i }),
    ).toBeVisible();
    // Click the confirm button inside the dialog
    await user.click(
      within(
        screen.getByRole("alertdialog", { name: /remove this book/i }),
      ).getByRole("button", { name: /delete entry/i }),
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
      within(
        screen.getByRole("alertdialog", { name: /remove this book/i }),
      ).getByRole("button", { name: /delete entry/i }),
    );
    // The failure is reported inside the dialog, which is still open. An alert
    // rendered behind a modal is an alert nobody sees.
    const dialog = screen.getByRole("alertdialog", {
      name: /remove this book/i,
    });
    expect(await within(dialog).findByRole("alert")).toBeVisible();
    // Nothing was deleted: dismissing the dialog reveals the entry again.
    await user.keyboard("{Escape}");
    expect(
      await screen.findByRole("heading", { name: "Rayuela" }),
    ).toBeVisible();
  });

  it("refuses an impossible date range and keeps the typed values", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      if (init?.method === "PATCH") throw new Error("must not be reached");
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(screen.getByRole("button", { name: /edit opinion/i }));

    await user.type(screen.getByLabelText(/^started$/i), "2026-05-10");
    await user.type(screen.getByLabelText(/^finished$/i), "2026-01-02");
    await user.type(screen.getByLabelText(/^notes$/i), " and a note");
    await user.click(screen.getByRole("button", { name: /save opinion/i }));

    const finished = screen.getByLabelText(/^finished$/i);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /finished cannot be before started/i,
    );
    expect(finished).toHaveAttribute("aria-invalid", "true");
    // The dialog is still open and nothing typed was thrown away.
    expect(
      screen.getByRole("dialog", { name: /edit your opinion/i }),
    ).toBeVisible();
    expect(screen.getByLabelText(/^started$/i)).toHaveValue("2026-05-10");
    expect(screen.getByLabelText(/^notes$/i)).toHaveValue(
      "Cached note and a note",
    );
  });

  it("refuses an out-of-range reread count", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(screen.getByRole("button", { name: /edit opinion/i }));
    const rereads = screen.getByLabelText(/reread count/i);
    await user.clear(rereads);
    await user.type(rereads, "99999");
    await user.click(screen.getByRole("button", { name: /save opinion/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /rereads must be between 0 and 9999/i,
    );
  });

  it("keeps typed metadata when the write fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      if (init?.method === "PATCH")
        return new Response(JSON.stringify({ error: { code: "conflict" } }), {
          status: 409,
        });
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(
      screen.getByRole("button", { name: /edit book metadata/i }),
    );
    await user.clear(screen.getByLabelText(/^title$/i));
    await user.type(screen.getByLabelText(/^title$/i), "Rayuela corregida");
    await user.click(screen.getByRole("button", { name: /save metadata/i }));

    // Technical spec section 8: a failed write announces an error and never
    // silently loses input.
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(
      screen.getByRole("dialog", { name: /edit shared book metadata/i }),
    ).toBeVisible();
    expect(screen.getByLabelText(/^title$/i)).toHaveValue("Rayuela corregida");
  });

  it("rejects an empty title on the metadata form", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(
      screen.getByRole("button", { name: /edit book metadata/i }),
    );
    await user.clear(screen.getByLabelText(/^title$/i));
    await user.click(screen.getByRole("button", { name: /save metadata/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /a book needs a title/i,
    );
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
      screen.getByRole("alertdialog", { name: /remove this book/i }),
    ).toBeVisible();
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("alertdialog", { name: /remove this book/i }),
    ).not.toBeInTheDocument();
  });
  it("shows the score as a filled chip, the same treatment as the library", () => {
    // DEC-026: the ramp means the same thing wherever the eye lands, so the
    // detail page carries the chip rather than the coloured text it used to.
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/shelves"
        ? new Response("[]")
        : new Response(JSON.stringify(entry)),
    );
    renderPage();
    return waitFor(() => {
      const score = document.querySelector("[data-fact='score'] span");
      expect(score?.className).toContain("bg-score-high");
      expect(score?.className).toContain("text-background");
    });
  });
});
