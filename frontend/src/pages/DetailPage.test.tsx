import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { findToast } from "@/test/toast";
import { DetailPage } from "./DetailPage";

/** What `GET /api/item-types` publishes for a book (DEC-052 seam 3). */
const itemTypes = [
  {
    id: "book",
    label: "Book",
    fields: [
      {
        name: "creators",
        label: "Creators",
        type: "text",
        multiplicity: "many",
      },
      {
        name: "publisher",
        label: "Publisher",
        type: "text",
        multiplicity: "one",
      },
      {
        name: "language",
        label: "Language",
        type: "text",
        multiplicity: "one",
      },
      {
        name: "page_count",
        label: "Page count",
        type: "number",
        multiplicity: "one",
        minimum: 1,
        maximum: 100000,
      },
      {
        name: "description",
        label: "Description",
        type: "long_text",
        multiplicity: "one",
      },
      {
        name: "subjects",
        label: "Subjects",
        type: "text",
        multiplicity: "many",
      },
      { name: "series", label: "Series", type: "text", multiplicity: "one" },
      {
        name: "original_year",
        label: "Original publication year",
        type: "number",
        multiplicity: "one",
        minimum: 0,
        maximum: 9999,
      },
    ],
  },
];

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
    creator: "Julio Cortázar",
    creator_sort: "Cortázar, Julio",
    cover_path: null,
    cover_url: null,
    metadata: {
      creators: ["Julio Cortázar"],
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
  formats: ["physical"],
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
        if (url === "/api/item-types")
          return new Response(JSON.stringify(itemTypes));
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
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
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
        if (url === "/api/item-types")
          return new Response(JSON.stringify(itemTypes));
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
    await user.click(screen.getByRole("button", { name: /edit metadata/i }));
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
      if (String(input) === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
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

  it("renders the fields the server declares, not a hardcoded book form", async () => {
    // The component is never edited for a new domain: the same code renders an
    // album's fields because the spec says so (DEC-052 seam 3, AC7).
    const albumTypes = [
      {
        id: "album",
        label: "Album",
        fields: [
          {
            name: "creators",
            label: "Artists",
            type: "text",
            multiplicity: "many",
          },
          { name: "label", label: "Label", type: "text", multiplicity: "one" },
          {
            name: "track_count",
            label: "Tracks",
            type: "number",
            multiplicity: "one",
            minimum: 1,
            maximum: 10000,
          },
        ],
      },
    ];
    const album = {
      ...entry,
      item: {
        ...entry.item,
        type: "album",
        title: "Discovery",
        creator: "Daft Punk",
        creator_sort: "Daft Punk",
        metadata: {
          creators: ["Daft Punk"],
          label: "Virgin",
          track_count: 14,
        },
      },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/item-types")
        return new Response(JSON.stringify(albumTypes));
      return new Response(JSON.stringify(album));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Discovery" });

    // The facts panel speaks the album's vocabulary and none of the book's.
    expect(document.querySelector("[data-fact='label'] dd")).toHaveTextContent(
      "Virgin",
    );
    expect(document.querySelector("[data-fact='page_count']")).toBeNull();

    await user.click(screen.getByRole("button", { name: /edit metadata/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText(/^label$/i)).toHaveValue("Virgin");
    expect(within(dialog).getByLabelText(/^tracks$/i)).toHaveValue(14);
    expect(
      within(dialog).getByLabelText(/^artists, comma separated$/i),
    ).toHaveValue("Daft Punk");
    expect(within(dialog).queryByLabelText(/page count/i)).toBeNull();
  });

  it("gives an album its own statuses, formats and heading", async () => {
    // Seam 5b (DEC-057): not the book vocabulary renamed. An album is `owned`, has
    // no reread count and no dates, and its personal region is not "reading data".
    const albumTypes = [
      {
        id: "album",
        label: "Album",
        fields: [],
        statuses: [
          { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
          {
            value: "wishlist",
            label: "Wishlist",
            choosable: true,
            hotkey: "w",
          },
          {
            value: "pending",
            label: "On the way",
            choosable: true,
            hotkey: "p",
          },
          { value: "owned", label: "Owned", choosable: true, hotkey: "o" },
        ],
        default_status: "owned",
        entry_fields: [],
        formats: [
          { value: "vinyl", label: "Vinyl" },
          { value: "cd", label: "CD" },
        ],
        entry_panel_label: "Your copy",
      },
    ];
    const album = {
      ...entry,
      status: "owned",
      formats: ["vinyl"],
      item: { ...entry.item, type: "album", title: "Discovery", metadata: {} },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/item-types")
        return new Response(JSON.stringify(albumTypes));
      return new Response(JSON.stringify(album));
    });
    renderPage();
    await screen.findByRole("heading", { name: "Discovery" });

    expect(document.querySelector("[data-fact='status'] dd")).toHaveTextContent(
      "Owned",
    );
    expect(
      document.querySelector("[data-fact='formats'] dd"),
    ).toHaveTextContent("Vinyl");
    expect(screen.getByRole("heading", { name: "Your copy" })).toBeVisible();
    // The three fields a record has no meaning for are gone, not blank.
    expect(document.querySelector("[data-fact='rereads']")).toBeNull();
    expect(document.querySelector("[data-fact='started']")).toBeNull();
    expect(document.querySelector("[data-fact='finished']")).toBeNull();
  });

  it("keeps a book's reading data, the half DEC-057 did not touch", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/item-types") return new Response("[]");
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    await screen.findByRole("heading", { name: "Rayuela" });

    expect(document.querySelector("[data-fact='rereads']")).not.toBeNull();
    expect(document.querySelector("[data-fact='started']")).not.toBeNull();
    expect(
      screen.getByRole("heading", { name: "Your reading data" }),
    ).toBeVisible();
  });

  it("corrects the creator sort name and clears it back to the automatic value", async () => {
    const bodies: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (init?.method === "PATCH") {
        bodies.push(String(init.body));
        return new Response(JSON.stringify(entry.item));
      }
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    await screen.findByRole("heading", { name: "Rayuela" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /edit metadata/i }));
    // The automatic value is offered as the placeholder rather than prefilled, so
    // an untouched field stays empty and the row keeps following its authors.
    const field = screen.getByLabelText(/sorts as/i);
    expect(field).toHaveValue("");
    expect(field).toHaveAttribute("placeholder", "Cortázar, Julio");
    await user.type(field, "Cortázar Ascasubi, Julio");
    await user.click(screen.getByRole("button", { name: /save metadata/i }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(JSON.parse(bodies[0]).creator_sort_override).toBe(
      "Cortázar Ascasubi, Julio",
    );
  });

  it("sends null when the sort name field is emptied", async () => {
    const bodies: string[] = [];
    const corrected = {
      ...entry,
      item: { ...entry.item, creator_sort_override: "Anything At All" },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (init?.method === "PATCH") {
        bodies.push(String(init.body));
        return new Response(JSON.stringify(corrected.item));
      }
      return new Response(JSON.stringify(corrected));
    });
    renderPage();
    await screen.findByRole("heading", { name: "Rayuela" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /edit metadata/i }));
    await user.clear(screen.getByLabelText(/sorts as/i));
    await user.click(screen.getByRole("button", { name: /save metadata/i }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(JSON.parse(bodies[0]).creator_sort_override).toBeNull();
  });

  it("confirmed deletion calls DELETE and returns to library", async () => {
    const requests: Array<[string, RequestInit?]> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      requests.push([url, init]);
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
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
      screen.getByRole("alertdialog", { name: /remove this/i }),
    ).toBeVisible();
    // Click the confirm button inside the dialog
    await user.click(
      within(
        screen.getByRole("alertdialog", { name: /remove this/i }),
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
    expect(await findToast("Removed from your library")).toBeInTheDocument();
  });

  it("cancel preserves the entry and does not call DELETE", async () => {
    const requests: Array<[string, RequestInit?]> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      requests.push([url, init]);
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
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
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
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
        screen.getByRole("alertdialog", { name: /remove this/i }),
      ).getByRole("button", { name: /delete entry/i }),
    );
    // The failure is reported inside the dialog, which is still open. An alert
    // rendered behind a modal is an alert nobody sees.
    const dialog = screen.getByRole("alertdialog", {
      name: /remove this/i,
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
      if (String(input) === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
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
      if (String(input) === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
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
      if (String(input) === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (init?.method === "PATCH")
        return new Response(JSON.stringify({ error: { code: "conflict" } }), {
          status: 409,
        });
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(screen.getByRole("button", { name: /edit metadata/i }));
    await user.clear(screen.getByLabelText(/^title$/i));
    await user.type(screen.getByLabelText(/^title$/i), "Rayuela corregida");
    await user.click(screen.getByRole("button", { name: /save metadata/i }));

    // Technical spec section 8: a failed write announces an error and never
    // silently loses input.
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(
      screen.getByRole("dialog", { name: /edit shared metadata/i }),
    ).toBeVisible();
    expect(screen.getByLabelText(/^title$/i)).toHaveValue("Rayuela corregida");
  });

  it("rejects an empty title on the metadata form", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      if (String(input) === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(screen.getByRole("button", { name: /edit metadata/i }));
    await user.clear(screen.getByLabelText(/^title$/i));
    await user.click(screen.getByRole("button", { name: /save metadata/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /a title is required/i,
    );
  });

  it("Escape closes dialogs", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      if (String(input) === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Rayuela" });
    await user.click(screen.getByRole("button", { name: /delete entry/i }));
    expect(
      screen.getByRole("alertdialog", { name: /remove this/i }),
    ).toBeVisible();
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("alertdialog", { name: /remove this/i }),
    ).not.toBeInTheDocument();
  });
  it("shows the score as a filled chip, the same treatment as the library", () => {
    // DEC-026: the ramp means the same thing wherever the eye lands, so the
    // detail page carries the chip rather than the coloured text it used to.
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      if (String(input) === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    return waitFor(() => {
      const score = document.querySelector("[data-fact='score'] span");
      expect(score?.className).toContain("bg-score-high");
      expect(score?.className).toContain("text-background");
    });
  });

  /**
   * The owner's words: "shelves kinda suck, having to create them by going on a
   * new screen + having to click 'edit opinion' to be able to change them is not
   * ideal." Both frictions are asserted here — one control, no dialog, no route.
   */
  function stubShelves(
    existing = [
      { id: 1, name: "Favorites", slug: "favorites", entry_count: 4 },
    ],
  ) {
    return vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (url === "/api/shelves" && init?.method === "POST") {
          const body = JSON.parse(String(init.body)) as { name: string };
          return new Response(
            JSON.stringify({
              id: 9,
              name: body.name,
              slug: body.name.toLowerCase(),
              entry_count: 0,
            }),
          );
        }
        if (url === "/api/shelves")
          return new Response(JSON.stringify(existing));
        if (url === "/api/item-types")
          return new Response(JSON.stringify(itemTypes));
        if (url.includes("/attachments"))
          return new Response('{"attachments":[]}');
        if (url === "/api/entries/7" && init?.method === "PATCH") {
          const body = JSON.parse(String(init.body)) as { shelf_ids: number[] };
          return new Response(
            JSON.stringify({
              ...entry,
              shelves: body.shelf_ids.map((id) => ({
                id,
                name: id === 9 ? "Ensayo" : "Favorites",
                slug: id === 9 ? "ensayo" : "favorites",
              })),
            }),
          );
        }
        return new Response(JSON.stringify(entry));
      });
  }

  it("creates a shelf and puts the book on it in one control", async () => {
    const request = stubShelves();
    renderPage();
    await screen.findByRole("heading", { name: "Rayuela" });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Add to a shelf" }));
    await user.type(
      await screen.findByRole("combobox", { name: "Find or create a shelf" }),
      "Ensayo",
    );
    await user.click(
      await screen.findByRole("option", { name: /Create .Ensayo./ }),
    );

    // Created, then assigned, without the opinion dialog and without /shelves.
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/shelves",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/entries/7",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ shelf_ids: [1, 9] }),
        }),
      ),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("adds an existing shelf from the same control", async () => {
    const request = stubShelves([
      { id: 1, name: "Favorites", slug: "favorites", entry_count: 4 },
      { id: 9, name: "Ensayo", slug: "ensayo", entry_count: 2 },
    ]);
    renderPage();
    await screen.findByRole("heading", { name: "Rayuela" });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Add to a shelf" }));
    await user.click(await screen.findByRole("option", { name: "Ensayo" }));

    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/entries/7",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ shelf_ids: [1, 9] }),
        }),
      ),
    );
    // Nothing was created: it already existed.
    expect(
      request.mock.calls.filter(
        ([url, init]) =>
          String(url) === "/api/shelves" &&
          (init as RequestInit | undefined)?.method === "POST",
      ),
    ).toHaveLength(0);
  });

  it("takes the book off a shelf from the same place", async () => {
    const request = stubShelves();
    renderPage();
    await screen.findByRole("heading", { name: "Rayuela" });
    const user = userEvent.setup();

    await user.click(
      screen.getByRole("button", { name: "Remove from Favorites" }),
    );

    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/entries/7",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ shelf_ids: [] }),
        }),
      ),
    );
  });

  it("does not offer shelves in the opinion dialog any more", async () => {
    stubShelves();
    // Re-stub with a domain that declares formats, so the assertion that the
    // format control *stayed* is about the dialog and not about the fixture.
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/item-types")
        return new Response(
          JSON.stringify([
            {
              ...itemTypes[0],
              formats: [
                { value: "physical", label: "Physical" },
                { value: "digital", label: "Digital" },
              ],
            },
          ]),
        );
      if (url.includes("/attachments"))
        return new Response('{"attachments":[]}');
      return new Response(JSON.stringify(entry));
    });
    renderPage();
    await screen.findByRole("heading", { name: "Rayuela" });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Edit opinion" }));
    const dialog = await screen.findByRole("dialog");
    // Shelf membership moved out; the format control did not, because a format is
    // not a shelf and the two must not converge (DEC-059).
    expect(within(dialog).queryByText("Shelves")).toBeNull();
    expect(
      within(dialog).queryByRole("textbox", { name: "New shelf name" }),
    ).toBeNull();
    expect(within(dialog).getByText("Format")).toBeVisible();
  });
});
