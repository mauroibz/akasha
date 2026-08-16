import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { findToast } from "@/test/toast";
import { AddPage } from "./AddPage";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/add"]}>
        <Routes>
          <Route path="/add" element={<AddPage />} />
          <Route path="/books/:id" element={<h1>Book detail</h1>} />
          <Route path="/" element={<h1>Library page</h1>} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

/** The two domains `GET /api/item-types` publishes (DEC-052 seam 3). */
const itemTypes = [
  { id: "book", label: "Book", fields: [] },
  { id: "album", label: "Album", fields: [] },
];

describe("AddPage", () => {
  it("debounces provider search and offers keyboard-accessible manual fallback", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/item-types"
        ? new Response(JSON.stringify(itemTypes))
        : String(input) === "/api/shelves" ||
            String(input) === "/api/health/providers"
          ? new Response(
              String(input) === "/api/shelves"
                ? "[]"
                : JSON.stringify({ providers: [], degraded: false }),
            )
          : new Response(
              JSON.stringify([
                {
                  source: "openlibrary",
                  source_id: "OL1M",
                  source_refs: [{ source: "openlibrary", source_id: "OL1M" }],
                  title: "Rayuela",
                  subtitle: null,
                  creators: ["Julio Cortázar"],
                  year: 1963,
                  cover_url: null,
                  identifiers: {},
                  language: "es",
                  metadata: {},
                },
              ]),
              { status: 200 },
            ),
    );
    renderPage();
    await userEvent.type(
      await screen.findByRole("searchbox", { name: /search books/i }),
      "Rayuela",
    );
    // One search request for the whole typed string, not one per keystroke.
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.filter(([input]) =>
            String(input).startsWith("/api/search"),
          ),
      ).toHaveLength(1),
    );
    expect(
      await screen.findByRole("button", { name: /Rayuela/i }),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    expect(screen.getByLabelText(/^title$/i)).toHaveFocus();
  });

  it("aborts a superseded search and reports no error for it", async () => {
    // Provider search takes about five seconds against the real backend, so a
    // second query routinely starts while the first is still open. Two things
    // must hold: the first request is actually cancelled rather than left to
    // run against a rate-limited free API, and its abort is never shown to the
    // reader as a failure.
    const signals: AbortSignal[] = [];
    let resolveFirst: ((value: Response) => void) | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input, init) =>
        new Promise<Response>((resolve) => {
          const url = String(input);
          if (url === "/api/item-types")
            return resolve(new Response(JSON.stringify(itemTypes)));
          if (url === "/api/shelves") return resolve(new Response("[]"));
          if (url === "/api/health/providers")
            return resolve(
              new Response(JSON.stringify({ providers: [], degraded: false })),
            );
          signals.push(init!.signal as AbortSignal);
          if (signals.length === 1) {
            resolveFirst = resolve;
            return;
          }
          resolve(
            new Response(
              JSON.stringify([
                {
                  source: "openlibrary",
                  source_id: "OL2M",
                  source_refs: [{ source: "openlibrary", source_id: "OL2M" }],
                  title: "Second search result",
                  subtitle: null,
                  creators: ["Someone"],
                  year: 1970,
                  cover_url: null,
                  identifiers: {},
                  language: "es",
                  metadata: {},
                },
              ]),
              { status: 200 },
            ),
          );
        }),
    );
    renderPage();
    const search = await screen.findByRole("searchbox", {
      name: /search books/i,
    });
    await userEvent.type(search, "first");
    await waitFor(() => expect(signals).toHaveLength(1));
    await userEvent.clear(search);
    await userEvent.type(search, "second");
    await waitFor(() => expect(signals).toHaveLength(2));

    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);

    // Let the abandoned request answer late. It must change nothing.
    resolveFirst?.(new Response("[]", { status: 200 }));
    expect(
      await screen.findByRole("button", { name: /Second search result/i }),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the manual escape hatch when providers fail outright", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/health/providers")
        return new Response(JSON.stringify({ providers: [], degraded: false }));
      return new Response("upstream is down", { status: 502 });
    });
    renderPage();
    await userEvent.type(
      await screen.findByRole("searchbox", { name: /search books/i }),
      "Rayuela",
    );
    // A failed search is a dead end unless it says so and offers the way past
    // it. Both halves are the behaviour, not just the error text.
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /providers are unavailable/i,
    );
    expect(screen.getByText(/still enter it by hand/i)).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    expect(screen.getByLabelText(/^title$/i)).toHaveFocus();
  });

  it("submits a manual entry once and announces exact duplicates", async () => {
    const request = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input) === "/api/item-types"
          ? new Response(JSON.stringify(itemTypes))
          : String(input) === "/api/shelves"
            ? new Response("[]")
            : String(input) === "/api/health/providers"
              ? new Response(JSON.stringify({ providers: [], degraded: false }))
              : new Response(
                  JSON.stringify({
                    entry: { id: 7 },
                    already_exists: true,
                    near_matches: [],
                  }),
                  { status: 200 },
                ),
      );
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(screen.getByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    await screen.findByRole("heading", { name: /book detail/i });
    expect(
      request.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
    expect(await findToast("Already in your library")).toBeInTheDocument();
  });

  it("confirms a successful add on the visible toast surface", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/item-types"
        ? new Response(JSON.stringify(itemTypes))
        : String(input) === "/api/shelves"
          ? new Response("[]")
          : String(input) === "/api/health/providers"
            ? new Response(JSON.stringify({ providers: [], degraded: false }))
            : new Response(
                JSON.stringify({
                  entry: { id: 11 },
                  already_exists: false,
                  near_matches: [],
                }),
                { status: 201 },
              ),
    );
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(screen.getByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    await screen.findByRole("heading", { name: /library page/i });
    expect(await findToast("Book added")).toBeInTheDocument();
  });

  it("refuses an empty title and keeps everything else typed", async () => {
    const request = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input) === "/api/shelves"
          ? new Response("[]")
          : new Response(JSON.stringify({ providers: [], degraded: false })),
      );
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(
      screen.getByLabelText(/^creators, comma separated$/i),
      "Julio Cortázar",
    );
    await userEvent.type(screen.getByLabelText(/^year$/i), "1963");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );

    // The field error is announced and tied to the control that caused it.
    const title = screen.getByLabelText(/^title$/i);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /a book needs a title/i,
    );
    expect(title).toHaveAttribute("aria-invalid", "true");
    expect(title).toHaveAttribute(
      "aria-describedby",
      screen.getByRole("alert").id,
    );
    // Nothing was sent, and nothing typed was discarded.
    expect(
      request.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(0);
    expect(screen.getByLabelText(/^creators, comma separated$/i)).toHaveValue(
      "Julio Cortázar",
    );
    expect(screen.getByLabelText(/^year$/i)).toHaveValue(1963);
  });

  it("refuses a malformed ISBN without discarding the rest of the form", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/shelves"
        ? new Response("[]")
        : new Response(JSON.stringify({ providers: [], degraded: false })),
    );
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(screen.getByLabelText(/^title$/i), "Rayuela");
    await userEvent.type(screen.getByLabelText(/^isbn$/i), "not-an-isbn");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/isbn/i);
    expect(screen.getByLabelText(/^title$/i)).toHaveValue("Rayuela");
    expect(screen.getByLabelText(/^isbn$/i)).toHaveValue("not-an-isbn");
  });

  it("asks the providers of the domain the reader chose", async () => {
    // AC5 from the reader's side: choosing Albums sends `type=album`, and the
    // backend answers it with MusicBrainz alone. Nothing filters a mixed result
    // set on the client, because a mixed result set is never fetched.
    const searched: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/health/providers")
        return new Response(JSON.stringify({ providers: [], degraded: false }));
      searched.push(url);
      return new Response(JSON.stringify([]));
    });
    renderPage();
    const user = userEvent.setup();
    const albums = await screen.findByRole("radio", { name: "Album" });
    await user.click(albums);
    await user.type(screen.getByRole("searchbox"), "Kind of Blue");
    await waitFor(() => expect(searched.length).toBeGreaterThan(0));

    expect(albums).toHaveAttribute("aria-checked", "true");
    expect(searched.at(-1)).toContain("type=album");
    expect(searched.some((url) => url.includes("type=book"))).toBe(false);
  });

  it("requires explicit confirmation before adding a near-match edition", async () => {
    let posts = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      if (String(input) === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (String(input) === "/api/health/providers")
        return new Response(JSON.stringify({ providers: [], degraded: false }));
      posts += 1;
      if (posts === 1)
        return new Response(
          JSON.stringify({
            error: {
              code: "near_match_confirmation_required",
              details: { entry_ids: [4] },
            },
          }),
          { status: 409 },
        );
      return new Response(
        JSON.stringify({
          entry: { id: 8 },
          already_exists: false,
          near_matches: [4],
        }),
        { status: 201 },
      );
    });
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(screen.getByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /similar edition/i,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /add separate edition/i }),
    );
    await screen.findByRole("heading", { name: /library page/i });
    expect(posts).toBe(2);
  });

  /**
   * The owner's report: "the search page, after you clicked on an item, feels
   * empty." Measured before designing — the search response already carries far
   * more than the three fields the confirm screen rendered, so showing the rest
   * costs no request and no wait.
   */
  const richCandidate = {
    source: "openlibrary",
    source_id: "OL1M",
    source_refs: [{ source: "openlibrary", source_id: "OL1M" }],
    title: "Rayuela",
    subtitle: "Una novela",
    creators: ["Julio Cortázar"],
    credit: "Julio Cortázar",
    year: 1963,
    original_year: 1963,
    cover_url: null,
    identifiers: { isbn13: "9788437604572" },
    language: "es",
    metadata: { publisher: "Sudamericana" },
  };

  const bookFields = [
    {
      name: "publisher",
      label: "Publisher",
      type: "text",
      multiplicity: "one",
    },
    // Declared by both real domains, and the candidate carries one of its own.
    { name: "language", label: "Language", type: "text", multiplicity: "one" },
    {
      name: "page_count",
      label: "Page count",
      type: "number",
      multiplicity: "one",
    },
    {
      name: "description",
      label: "Description",
      type: "long_text",
      multiplicity: "one",
    },
  ];

  function stubAdd({
    candidate = richCandidate,
    preview,
    fields = bookFields,
  }: {
    candidate?: unknown;
    preview?: () => Response;
    fields?: unknown[];
  } = {}) {
    return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(
          JSON.stringify([
            {
              id: "book",
              label: "Book",
              fields,
              formats: [],
              entry_fields: [],
            },
            {
              id: "album",
              label: "Album",
              fields: [],
              formats: [],
              entry_fields: [],
            },
          ]),
        );
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/health/providers")
        return new Response(JSON.stringify({ providers: [], degraded: false }));
      if (url.startsWith("/api/search/preview"))
        return preview
          ? preview()
          : new Response(JSON.stringify(candidate), { status: 200 });
      return new Response(JSON.stringify([candidate]));
    });
  }

  async function selectFirstResult() {
    const user = userEvent.setup();
    await user.type(screen.getByRole("searchbox"), "Rayuela");
    await user.click(await screen.findByRole("button", { name: /Rayuela/ }));
    return user;
  }

  it("shows what the search already returned, without asking a provider again", async () => {
    const request = stubAdd();
    renderPage();
    await selectFirstResult();

    // Everything the candidate carried, not just cover/title/credit.
    const panel = await screen.findByRole("region", { name: "What we know" });
    const text = panel.textContent ?? "";
    for (const value of [
      "Una novela",
      "1963",
      "es",
      "9788437604572",
      "Sudamericana",
    ])
      expect(text, `missing ${value}`).toContain(value);
    // Both domains declare `language` as a field and the candidate carries one of
    // its own, so a naive panel renders that label twice.
    expect(text.match(/Language/g) ?? []).toHaveLength(1);

    // And nothing was fetched to show it.
    expect(
      request.mock.calls.filter(([url]) =>
        String(url).startsWith("/api/search/preview"),
      ),
    ).toHaveLength(0);
  });

  it("fetches the full record only when asked, and exactly once", async () => {
    const request = stubAdd({
      preview: () =>
        new Response(
          JSON.stringify({
            ...richCandidate,
            metadata: {
              publisher: "Sudamericana",
              page_count: 736,
              description: "A novel that can be read in more than one order.",
            },
          }),
        ),
    });
    renderPage();
    const user = await selectFirstResult();

    const button = await screen.findByRole("button", {
      name: "Load full details",
    });
    await user.click(button);

    expect(
      await screen.findByText(/read in more than one order/),
    ).toBeVisible();
    expect(screen.getByText("736")).toBeVisible();
    await waitFor(() =>
      expect(
        request.mock.calls.filter(([url]) =>
          String(url).startsWith("/api/search/preview"),
        ),
      ).toHaveLength(1),
    );
    // Nothing left to load, so nothing left to press.
    expect(
      screen.queryByRole("button", { name: "Load full details" }),
    ).toBeNull();
  });

  it("says so when the full record cannot be fetched, and still lets you add", async () => {
    stubAdd({
      preview: () =>
        new Response(JSON.stringify({ error: { code: "provider_failure" } }), {
          status: 502,
        }),
    });
    renderPage();
    const user = await selectFirstResult();

    await user.click(
      await screen.findByRole("button", { name: "Load full details" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /could not be loaded/i,
    );
    // The point of the guard: a failed preview costs the reader nothing.
    expect(
      screen.getByRole("button", { name: /Add to library/ }),
    ).toBeEnabled();
  });

  it("creates a shelf from the add screen and adds with it", async () => {
    const bodies: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(
          JSON.stringify([
            {
              id: "book",
              label: "Book",
              fields: [],
              formats: [],
              entry_fields: [],
            },
          ]),
        );
      if (url === "/api/health/providers")
        return new Response(JSON.stringify({ providers: [], degraded: false }));
      if (url === "/api/shelves" && init?.method === "POST")
        return new Response(
          JSON.stringify({
            id: 5,
            name: "Ensayo",
            slug: "ensayo",
            entry_count: 0,
          }),
        );
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/entries" && init?.method === "POST") {
        bodies.push(String(init.body));
        return new Response(
          JSON.stringify({
            entry: { id: 3, item: { id: 1 } },
            already_exists: false,
            near_matches: [],
          }),
          { status: 201 },
        );
      }
      return new Response(JSON.stringify([richCandidate]));
    });
    renderPage();
    const user = await selectFirstResult();

    await user.click(
      await screen.findByRole("button", { name: "Add to a shelf" }),
    );
    await user.type(
      await screen.findByRole("combobox", { name: "Find or create a shelf" }),
      "Ensayo",
    );
    await user.click(
      await screen.findByRole("option", { name: /Create .Ensayo./ }),
    );
    await user.click(screen.getByRole("button", { name: /Add to library/ }));

    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(JSON.parse(bodies[0]).shelf_ids).toEqual([5]);
  });

  it("sets notes, format and the domain's own date fields while adding", async () => {
    const bodies: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(
          JSON.stringify([
            {
              id: "book",
              label: "Book",
              fields: [],
              formats: [
                { value: "physical", label: "Physical" },
                { value: "digital", label: "Digital" },
              ],
              entry_fields: ["date_started", "date_finished", "reread_count"],
              default_status: "read",
            },
          ]),
        );
      if (url === "/api/health/providers")
        return new Response(JSON.stringify({ providers: [], degraded: false }));
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/entries" && init?.method === "POST") {
        bodies.push(String(init.body));
        return new Response(
          JSON.stringify({
            entry: { id: 3, item: { id: 1 } },
            already_exists: false,
            near_matches: [],
          }),
          { status: 201 },
        );
      }
      return new Response(JSON.stringify([richCandidate]));
    });
    renderPage();
    const user = await selectFirstResult();

    await user.type(screen.getByRole("textbox", { name: "Notes" }), "Finally.");
    await user.click(screen.getByRole("combobox", { name: "Format" }));
    await user.click(await screen.findByRole("option", { name: "Physical" }));
    await user.keyboard("{Escape}");
    await user.type(screen.getByLabelText("Finished"), "2026-02-03");
    await user.click(screen.getByRole("button", { name: /Add to library/ }));

    await waitFor(() => expect(bodies).toHaveLength(1));
    const body = JSON.parse(bodies[0]);
    expect(body.notes).toBe("Finally.");
    expect(body.formats).toEqual(["physical"]);
    expect(body.date_finished).toBe("2026-02-03");
  });

  it("offers a record none of the fields it has no meaning for", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(
          JSON.stringify([
            {
              id: "book",
              label: "Book",
              fields: [],
              formats: [],
              entry_fields: ["reread_count"],
            },
            {
              id: "album",
              label: "Album",
              fields: [],
              formats: [{ value: "vinyl", label: "Vinyl" }],
              entry_fields: [],
              default_status: "owned",
            },
          ]),
        );
      if (url === "/api/health/providers")
        return new Response(JSON.stringify({ providers: [], degraded: false }));
      if (url === "/api/shelves") return new Response("[]");
      return new Response(JSON.stringify([richCandidate]));
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("radio", { name: "Album" }));
    await user.type(screen.getByRole("searchbox"), "Kind of Blue");
    await user.click(await screen.findByRole("button", { name: /Rayuela/ }));

    // DEC-057: a record has no reread count and no started/finished dates.
    expect(screen.queryByLabelText("Finished")).toBeNull();
    expect(screen.queryByLabelText("Reread count")).toBeNull();
    // But it does have notes and its own formats.
    expect(screen.getByRole("textbox", { name: "Notes" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Format" })).toBeVisible();
  });
});
