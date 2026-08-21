import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportPage } from "./ImportPage";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

function renderImportPage(path = "/import") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <ImportPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const importers = [
  {
    id: "goodreads",
    label: "Goodreads",
    item_type: "book",
    attachment_max_bytes: 25 * 1024 * 1024,
    input: {
      kind: "upload",
      label: "Goodreads CSV",
      field: "file",
      accept: ".csv,text/csv",
      placeholder: null,
      help: null,
      guide: [
        "Open goodreads.com/review/import on desktop web.",
        "Press Export Library and download the file.",
        "Ratings are doubled and marked provisional.",
      ],
      empty_state: "Drop goodreads_library_export.csv here, or choose a file.",
      help_url: "https://www.goodreads.com/review/import",
      browsable: false,
      accepts_files: false,
      max_bytes: null,
      max_files: null,
      alternate: null,
    },
  },
  {
    id: "calibre",
    label: "Calibre",
    item_type: "book",
    attachment_max_bytes: 25 * 1024 * 1024,
    input: {
      kind: "directory",
      label: "Calibre folder",
      field: "files",
      accept: null,
      placeholder: null,
      help: "Akasha reads the library you choose and copies nothing but metadata and covers.",
      guide: [
        "Choose your Calibre library folder — the one that holds metadata.db.",
        "Only metadata.db and the covers are sent; your ebooks are never uploaded.",
      ],
      empty_state: "Choose your Calibre library folder.",
      help_url: "https://manual.calibre-ebook.com/gui.html",
      browsable: false,
      incremental: true,
      accepts_files: true,
      max_bytes: 256 * 1024 * 1024,
      max_files: 10000,
      alternate: {
        kind: "path",
        label: "Calibre library path",
        field: "library_path",
        accept: null,
        placeholder: "Library",
        help: "Or read a library the server can already see.",
        guide: [],
        empty_state: "No folders here. Mount your Calibre library and reload.",
        help_url: null,
        browsable: true,
        incremental: false,
        accepts_files: false,
        max_bytes: null,
        max_files: null,
        alternate: null,
      },
    },
  },
];

/** A File carrying the relative path a directory pick would give it. */
function pick(path: string, size = 1024): File {
  const file = new File([new Uint8Array(size)], path.split("/").pop() ?? path);
  Object.defineProperty(file, "webkitRelativePath", { value: path });
  return file;
}

/** Everything the folded screen asks for that a given test does not care about. */
function stubRegistry(
  handler: (input: string) => Response | undefined = () => undefined,
) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const answered = handler(url);
    if (answered) return answered;
    if (url === "/api/importers")
      return new Response(JSON.stringify(importers));
    return new Response(JSON.stringify({}), { status: 404 });
  });
}

describe("ImportPage", () => {
  it("renders importer tabs from the published registry instead of literals", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "storygraph",
            label: "StoryGraph",
            item_type: "book",
            input: {
              kind: "upload",
              label: "StoryGraph CSV",
              field: "file",
              accept: ".csv,text/csv",
              placeholder: null,
              help: null,
              guide: ["Export from thestorygraph.com."],
              empty_state: "Drop the StoryGraph export here.",
              help_url: null,
              browsable: false,
              incremental: false,
              accepts_files: false,
              max_bytes: null,
              max_files: null,
              alternate: null,
            },
          },
        ]),
      ),
    );
    renderImportPage();

    expect(
      await screen.findByRole("tab", { name: "StoryGraph" }),
    ).toBeVisible();
    expect(screen.queryByRole("tab", { name: "Goodreads" })).toBeNull();
  });

  it("previews and commits a confined Calibre library without asking for a file", async () => {
    const requests: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      requests.push([input, init]);
      if (String(input) === "/api/importers")
        return new Response(JSON.stringify(importers));
      if (String(input).includes("/browse"))
        return new Response(
          JSON.stringify({
            path: "",
            parent: null,
            directories: ["My Books"],
            importable: false,
          }),
        );
      if (String(input).endsWith("calibre/preview"))
        return new Response(
          JSON.stringify({
            batch_id: "calibre-1",
            fingerprint: "db",
            state: "previewed",
            summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
            records: [
              {
                record_id: 8,
                row_number: 2,
                calibre_book_id: "1",
                calibre_uuid: "uuid-1",
                title: "Ficciones",
                creators: ["Jorge Luis Borges"],
                isbn: "9780141187761",
                suggested_status: null,
                score: 9,
                score_provisional: false,
                shelves: ["cuentos"],
                errors: [],
                planned_action: "create_item",
                match_kind: "new",
                candidates: [],
                cover_staged: true,
              },
            ],
          }),
          { status: 201 },
        );
      return new Response(
        JSON.stringify({
          batch_id: "calibre-1",
          state: "committed",
          created_items: 1,
          created_entries: 1,
          unchanged_entries: 0,
          unsorted_entries: 4,
        }),
      );
    });
    renderImportPage();
    await userEvent.click(await screen.findByRole("tab", { name: /calibre/i }));
    // The mount is the alternate now, behind a disclosure (DEC-081).
    await userEvent.click(
      screen.getByRole("button", { name: /server can already see/i }),
    );
    await userEvent.type(screen.getByLabelText(/library path/i), "My Books");
    await userEvent.click(
      screen.getByRole("button", { name: /preview calibre/i }),
    );
    expect(await screen.findByText(/local cover staged/i)).toBeVisible();
    expect(screen.getByText(/rating 9/i)).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: /import 1 ready row/i }),
    );
    expect(
      requests.find(([input]) => String(input).endsWith("calibre/preview")),
    ).toEqual([
      "/api/import/calibre/preview",
      expect.objectContaining({
        body: JSON.stringify({ library_path: "My Books" }),
      }),
    ]);
    expect(
      requests.some(([input]) =>
        String(input).includes("/api/import/calibre/commit"),
      ),
    ).toBe(true);
  });

  it("previews once, exposes errors and commits only the recorded batch", async () => {
    const requests: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      requests.push([input, init]);
      if (String(input) === "/api/importers")
        return new Response(JSON.stringify(importers));
      if (String(input).endsWith("preview"))
        return new Response(
          JSON.stringify({
            batch_id: "batch-1",
            fingerprint: "abc",
            state: "previewed",
            summary: { total: 2, ready: 1, errors: 1, ambiguous: 0 },
            records: [
              {
                record_id: 1,
                row_number: 2,
                goodreads_book_id: "1",
                title: "Rayuela",
                creators: ["Julio Cortázar"],
                isbn: null,
                suggested_status: "read",
                score: 8,
                score_provisional: true,
                shelves: ["favoritos"],
                errors: [],
                planned_action: "create_item",
                match_kind: "new",
                candidates: [],
              },
              {
                record_id: 2,
                row_number: 3,
                goodreads_book_id: "2",
                title: "Bad date",
                creators: [],
                isbn: null,
                suggested_status: null,
                score: null,
                score_provisional: false,
                shelves: [],
                formats: [],
                errors: [{ field: "date_read", code: "invalid_date" }],
                planned_action: "error",
                match_kind: "new",
                candidates: [],
              },
            ],
          }),
          { status: 201 },
        );
      return new Response(
        JSON.stringify({
          batch_id: "batch-1",
          state: "committed",
          created_items: 1,
          created_entries: 1,
          unchanged_entries: 0,
          unsorted_entries: 4,
        }),
      );
    });
    renderImportPage();
    const file = new File(["csv"], "library.csv", { type: "text/csv" });
    await userEvent.upload(await screen.findByLabelText("Goodreads CSV"), file);
    await userEvent.click(
      screen.getByRole("button", { name: /preview import/i }),
    );
    expect(
      await screen.findByRole("heading", { name: /preview: 2 rows/i }),
    ).toHaveFocus();
    expect(screen.getByText(/date_read: invalid_date/i)).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: /import 1 ready row/i }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      /1 entry added/i,
    );
    const commit = requests.find(([input]) => String(input).endsWith("commit"));
    expect(JSON.parse(String(commit?.[1]?.body))).toEqual({
      batch_id: "batch-1",
      choices: [],
    });
    expect(
      requests.filter(([input]) => String(input).endsWith("preview")),
    ).toHaveLength(1);
  });

  it("requires an explicit choice for ambiguous rows", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(importers)))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            batch_id: "batch-2",
            fingerprint: "x",
            state: "previewed",
            summary: { total: 1, ready: 0, errors: 0, ambiguous: 1 },
            records: [
              {
                record_id: 4,
                row_number: 2,
                goodreads_book_id: "4",
                title: "Ficciones",
                creators: ["Borges"],
                isbn: null,
                suggested_status: null,
                score: null,
                score_provisional: false,
                shelves: [],
                formats: [],
                errors: [],
                planned_action: "ambiguous",
                match_kind: "ambiguous",
                candidates: [7],
              },
            ],
          }),
          { status: 201 },
        ),
      );
    renderImportPage();
    await userEvent.upload(
      await screen.findByLabelText("Goodreads CSV"),
      new File(["x"], "x.csv", { type: "text/csv" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /preview import/i }),
    );
    // Radix has no `required` attribute to assert; the enforcement is that the
    // commit stays disabled until every ambiguous row has an explicit choice.
    const choice = await screen.findByRole("combobox", {
      name: /choice for Ficciones/i,
    });
    expect(choice).toHaveTextContent(/choose/i);
    expect(screen.getByRole("button", { name: /import/i })).toBeDisabled();

    await userEvent.click(choice);
    await userEvent.click(
      await screen.findByRole("option", { name: /use existing item 7/i }),
    );
    expect(choice).toHaveTextContent(/use existing item 7/i);
    expect(screen.getByRole("button", { name: /import/i })).toBeEnabled();
  });
  it("sends a finished import to the rows it left unsorted", async () => {
    // The defect: a commit reported "1 entry added" and the library showed
    // nothing, because imports land `unsorted` and the default view hides
    // exactly that. The result panel now says where the rows went.
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/importers"
        ? new Response(JSON.stringify(importers))
        : String(input).endsWith("/preview")
          ? new Response(
              JSON.stringify({
                batch_id: "batch-9",
                fingerprint: "abc",
                state: "previewed",
                summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
                records: [
                  {
                    record_id: 1,
                    row_number: 2,
                    goodreads_book_id: "101",
                    title: "Rayuela",
                    creators: ["Julio Cort\u00e1zar"],
                    isbn: "9788437604572",
                    suggested_status: "read",
                    score: 8,
                    score_provisional: true,
                    shelves: [],
                    formats: [],
                    errors: [],
                    planned_action: "create_item",
                    match_kind: "new",
                    candidates: [],
                  },
                ],
              }),
              { status: 201 },
            )
          : new Response(
              JSON.stringify({
                batch_id: "batch-9",
                state: "committed",
                created_items: 1,
                created_entries: 1,
                unchanged_entries: 0,
                // More than this batch created: an earlier import left rows there
                // too, and the whole waiting pile is what the reader needs.
                unsorted_entries: 7,
              }),
            ),
    );
    renderImportPage();
    await userEvent.upload(
      await screen.findByLabelText("Goodreads CSV"),
      new File(["csv"], "library.csv", { type: "text/csv" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /preview import/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /import 1 ready row/i }),
    );
    const result = await screen.findByRole("status");
    expect(result).toHaveTextContent(/7 entries are waiting in triage/i);
    expect(screen.getByRole("link", { name: /triage/i })).toHaveAttribute(
      "href",
      "/import?tab=triage",
    );
  });

  it("folds triage into the import screen as a tab", async () => {
    // Triage was a top-level destination that is empty unless an import just
    // ran, so most visits met a dead page. It is the tail of this flow, and it
    // lives here now (DEC-079).
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/importers"
        ? new Response(JSON.stringify(importers))
        : String(input).startsWith("/api/item-types")
          ? new Response(JSON.stringify({ item_types: [] }))
          : String(input).startsWith("/api/shelves")
            ? new Response(JSON.stringify({ shelves: [] }))
            : new Response(
                JSON.stringify({
                  items: [],
                  next_cursor: null,
                  total: 0,
                  facets: {
                    status_counts: {},
                    status_counts_by_type: {},
                    format_counts: {},
                  },
                }),
              ),
    );
    renderImportPage();

    await userEvent.click(await screen.findByRole("tab", { name: /triage/i }));
    expect(
      await screen.findByRole("heading", { level: 1, name: /inbox/i }),
    ).toBeVisible();
    // One landmark, still: the triage surface brings its own <main> and the
    // import one is not rendered beside it.
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });

  it("opens on the triage tab when the URL asks for it", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/importers"
        ? new Response(JSON.stringify(importers))
        : String(input).startsWith("/api/item-types")
          ? new Response(JSON.stringify({ item_types: [] }))
          : String(input).startsWith("/api/shelves")
            ? new Response(JSON.stringify({ shelves: [] }))
            : new Response(
                JSON.stringify({
                  items: [],
                  next_cursor: null,
                  total: 0,
                  facets: {
                    status_counts: {},
                    status_counts_by_type: {},
                    format_counts: {},
                  },
                }),
              ),
    );
    renderImportPage("/import?tab=triage");

    expect(
      await screen.findByRole("heading", { level: 1, name: /inbox/i }),
    ).toBeVisible();
    expect(screen.queryByLabelText("Goodreads CSV")).toBeNull();
  });

  it("renders the guidance the connector publishes, not copy of its own", async () => {
    // The Goodreads tab was a bare file input: nothing said where the export
    // lives or why a four-star book arrives as an 8 (DEC-079). The steps come
    // from the connector's declaration, so the next one guides its own users
    // without editing this screen.
    stubRegistry();
    renderImportPage();

    const steps = await screen.findByRole("list", {
      name: /how to get a goodreads csv/i,
    });
    expect(steps).toHaveTextContent(/goodreads.com\/review\/import/i);
    expect(steps).toHaveTextContent(/provisional/i);
    expect(
      screen.getByRole("link", { name: /goodreads export page/i }),
    ).toHaveAttribute("href", "https://www.goodreads.com/review/import");
    expect(
      screen.getByText(/drop goodreads_library_export\.csv here/i),
    ).toBeVisible();
  });

  it("accepts a dropped CSV as well as a chosen one", async () => {
    const bodies: FormData[] = [];
    stubRegistry((url) => {
      if (!url.endsWith("goodreads/preview")) return undefined;
      return new Response(
        JSON.stringify({
          batch_id: "dropped",
          fingerprint: "abc",
          state: "previewed",
          summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
          records: [],
        }),
        { status: 201 },
      );
    });
    const original = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.body instanceof FormData) bodies.push(init.body);
      return original(input, init);
    });
    renderImportPage();

    const zone = await screen.findByTestId("goodreads-drop-zone");
    const file = new File(["csv"], "goodreads_library_export.csv", {
      type: "text/csv",
    });
    fireEvent.drop(zone, { dataTransfer: { files: [file], types: ["Files"] } });

    expect(
      await screen.findByText(/goodreads_library_export\.csv/i),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: /preview import/i }),
    );
    await screen.findByRole("heading", { name: /preview: 1 row/i });
    expect(bodies.at(-1)?.get("file")).toBe(file);
  });

  it("browses the Calibre mount instead of asking for a path", async () => {
    // "Enter a relative folder only" is unanswerable without knowing what
    // folders exist under the mount. The picker answers it (DEC-079).
    const requests: string[] = [];
    stubRegistry((url) => {
      if (!url.includes("/browse")) return undefined;
      requests.push(url);
      const path = new URL(url, "http://test").searchParams.get("path") ?? "";
      if (path === "")
        return new Response(
          JSON.stringify({
            path: "",
            parent: null,
            directories: ["Comics", "Fiction"],
            importable: false,
          }),
        );
      return new Response(
        JSON.stringify({
          path,
          parent: "",
          directories: [],
          importable: true,
        }),
      );
    });
    renderImportPage("/import?tab=calibre");
    await userEvent.click(
      await screen.findByRole("button", { name: /server can already see/i }),
    );

    expect(
      await screen.findByRole("button", { name: "Fiction" }),
    ).toBeVisible();
    // Nothing is importable at the mount root, so there is nothing to preview.
    expect(
      screen.getByRole("button", { name: /preview calibre library/i }),
    ).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Fiction" }));

    expect(
      await screen.findByRole("button", { name: /preview calibre library/i }),
    ).toBeEnabled();
    expect(screen.getByLabelText(/library path/i)).toHaveValue("Fiction");
    // A breadcrumb back to the mount, so the picker is not a one-way trip.
    expect(
      screen.getByRole("button", { name: /calibre library root/i }),
    ).toBeVisible();
    expect(requests.some((url) => url.includes("path=Fiction"))).toBe(true);
  });

  it("renders what the connector says to do about a failure", async () => {
    stubRegistry((url) => {
      if (!url.endsWith("calibre/preview")) return undefined;
      return new Response(
        JSON.stringify({
          error: {
            code: "invalid_calibre_database",
            message: "Calibre database could not be read",
            user_message: "Akasha could not read this library's metadata.db.",
            action: "Close Calibre and try again.",
          },
        }),
        { status: 422 },
      );
    });
    renderImportPage("/import?tab=calibre");

    await userEvent.click(
      await screen.findByRole("button", { name: /server can already see/i }),
    );
    await userEvent.type(screen.getByLabelText(/library path/i), "Locked");
    await userEvent.click(
      screen.getByRole("button", { name: /preview calibre library/i }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not read this library/i);
    expect(alert).toHaveTextContent(/close calibre and try again/i);
  });

  it("keeps a preview with its connector, and through Triage", async () => {
    // Found in the walkthrough: after a Goodreads commit, switching to the
    // Calibre tab showed the Goodreads result and no Calibre form. A staged
    // source belongs to the connector that produced it — but Triage is not a
    // connector, so a trip through it must not discard the undo window.
    stubRegistry((url) => {
      if (url.includes("/browse"))
        return new Response(
          JSON.stringify({
            path: "",
            parent: null,
            directories: ["Fiction"],
            importable: false,
          }),
        );
      if (url.endsWith("/preview"))
        return new Response(
          JSON.stringify({
            batch_id: "batch-3",
            fingerprint: "abc",
            state: "previewed",
            summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
            records: [],
          }),
          { status: 201 },
        );
      if (url.startsWith("/api/item-types"))
        return new Response(JSON.stringify({ item_types: [] }));
      if (url.startsWith("/api/shelves"))
        return new Response(JSON.stringify({ shelves: [] }));
      if (url.startsWith("/api/entries"))
        return new Response(
          JSON.stringify({
            items: [],
            next_cursor: null,
            total: 0,
            facets: {
              status_counts: {},
              status_counts_by_type: {},
              format_counts: {},
            },
          }),
        );
      return undefined;
    });
    renderImportPage();

    await userEvent.upload(
      await screen.findByLabelText("Goodreads CSV"),
      new File(["csv"], "library.csv", { type: "text/csv" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /preview import/i }),
    );
    await screen.findByRole("heading", { name: /preview: 1 row/i });

    // Through Triage and back: the preview survives.
    await userEvent.click(screen.getByRole("tab", { name: /triage/i }));
    await screen.findByRole("heading", { level: 1, name: /inbox/i });
    await userEvent.click(screen.getByRole("tab", { name: /goodreads/i }));
    expect(
      await screen.findByRole("heading", { name: /preview: 1 row/i }),
    ).toBeVisible();

    // Another connector: a clean form, not somebody else's preview.
    await userEvent.click(screen.getByRole("tab", { name: /calibre/i }));
    expect(
      screen.queryByRole("heading", { name: /preview: 1 row/i }),
    ).toBeNull();
    expect(await screen.findByLabelText("Calibre folder")).toBeVisible();
    // And the alternate is collapsed again rather than left open from before.
    expect(
      screen.getByRole("button", { name: /server can already see/i }),
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("imports a Calibre folder and sends only the database and the covers", async () => {
    // The point of DEC-081: no mount, no restart, and a 32 MB library becomes a
    // 2.4 MB upload because the ebooks never leave the machine.
    let sent: FormData | null = null;
    stubRegistry((url) => {
      if (!url.endsWith("calibre/preview")) return undefined;
      return new Response(
        JSON.stringify({
          batch_id: "folder-1",
          fingerprint: "db",
          state: "previewed",
          summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
          records: [],
        }),
        { status: 201 },
      );
    });
    const inner = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.body instanceof FormData) sent = init.body;
      return inner(input, init);
    });
    renderImportPage("/import?tab=calibre");

    await userEvent.upload(await screen.findByLabelText("Calibre folder"), [
      pick("Calibre Library/metadata.db", 416 * 1024),
      pick("Calibre Library/Sanderson/Mistborn (2)/cover.jpg", 1200),
      pick("Calibre Library/Sanderson/Mistborn (2)/book.epub", 9_000_000),
      pick("Calibre Library/.caltrash/b/1/cover.jpg"),
    ]);

    expect(
      screen.getByRole("checkbox", { name: /also attach the ebook files/i }),
    ).not.toBeChecked();

    // Said before anything is sent, because "choose a folder" and "upload your
    // whole ebook collection" are otherwise indistinguishable.
    expect(
      await screen.findByText(/sending metadata\.db and 1 cover/i),
    ).toBeVisible();
    expect(
      screen.getByText(/2 other files stay on your machine/i),
    ).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: /preview calibre library/i }),
    );
    await screen.findByRole("heading", { name: /preview: 1 row/i });

    const parts = [...(sent as unknown as FormData).getAll("files")] as File[];
    expect(parts).toHaveLength(2);
    expect(parts.map((part) => part.name)).toEqual([
      "metadata.db",
      "Sanderson/Mistborn (2)/cover.jpg",
    ]);
  });

  it("counts preferred ebooks, skips over-cap files, and attaches after commit", async () => {
    const requests: Array<{ url: string; body: FormData | null }> = [];
    let fileRequest = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      requests.push({
        url,
        body: init?.body instanceof FormData ? init.body : null,
      });
      if (url === "/api/importers") {
        const registry = structuredClone(importers);
        registry[1].attachment_max_bytes = 1_000_000;
        return new Response(JSON.stringify(registry));
      }
      if (url.endsWith("calibre/plan")) {
        const manifest = JSON.parse(
          String((init?.body as FormData).get("manifest")),
        ) as Array<{ path: string }>;
        return new Response(
          JSON.stringify({
            wanted: manifest.map((row) => row.path),
            holding: 0,
            reason: null,
          }),
        );
      }
      if (url.endsWith("calibre/preview"))
        return new Response(
          JSON.stringify({
            batch_id: "files-1",
            fingerprint: "db",
            state: "previewed",
            summary: { total: 3, ready: 3, errors: 0, ambiguous: 0 },
            records: [],
          }),
          { status: 201 },
        );
      if (url.endsWith("calibre/commit"))
        return new Response(
          JSON.stringify({
            batch_id: "files-1",
            state: "committed",
            created_items: 3,
            created_entries: 3,
            unchanged_entries: 0,
            unsorted_entries: 3,
          }),
        );
      if (url.endsWith("/batches/files-1/files")) {
        fileRequest += 1;
        return fileRequest === 1
          ? new Response(
              JSON.stringify({
                id: 1,
                item_id: 1,
                filename: "one.epub",
                byte_size: 700_000,
                sha256: "a".repeat(64),
              }),
              { status: 201 },
            )
          : new Response(
              JSON.stringify({
                error: {
                  code: "invalid_attachment",
                  user_message: "That file could not be stored.",
                },
              }),
              { status: 422 },
            );
      }
      return new Response(JSON.stringify({}), { status: 404 });
    });
    renderImportPage("/import?tab=calibre");

    await userEvent.upload(await screen.findByLabelText("Calibre folder"), [
      pick("Lib/metadata.db", 100),
      pick("Lib/A/One (1)/cover.jpg", 10),
      pick("Lib/A/One (1)/one.azw3", 600_000),
      pick("Lib/A/One (1)/one.epub", 700_000),
      pick("Lib/B/Two (2)/two.pdf", 800_000),
      pick("Lib/C/Three (3)/three.epub", 1_100_000),
    ]);
    await userEvent.click(
      screen.getByRole("checkbox", { name: /also attach the ebook files/i }),
    );

    expect(await screen.findByText(/attaching 2 ebooks/i)).toBeVisible();
    expect(screen.getByText(/attaching 2 ebooks.*1\.4 MB/i)).toBeVisible();
    expect(screen.getByText(/three\.epub.*1\.0 MB/i)).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: /preview calibre library/i }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /import 3 ready rows/i }),
    );

    expect(await screen.findByText(/attached 1 of 2 ebooks/i)).toBeVisible();
    expect(screen.getByText(/B\/Two \(2\)\/two\.pdf/)).toBeVisible();
    expect(screen.getByText(/import complete: 3 entries added/i)).toBeVisible();

    const preview = requests.find((request) =>
      request.url.endsWith("calibre/preview"),
    );
    expect(
      (preview?.body?.getAll("files") as File[]).map((file) => file.name),
    ).toEqual(["metadata.db", "A/One (1)/cover.jpg"]);
    const uploads = requests.filter((request) =>
      request.url.endsWith("/batches/files-1/files"),
    );
    expect(uploads).toHaveLength(2);
    expect(uploads.map((request) => request.body?.get("path"))).toEqual([
      "A/One (1)/one.epub",
      "B/Two (2)/two.pdf",
    ]);
  });

  it("refuses the wrong folder in the browser, before any request", async () => {
    const calls: string[] = [];
    stubRegistry((url) => {
      calls.push(url);
      return undefined;
    });
    renderImportPage("/import?tab=calibre");

    await userEvent.upload(await screen.findByLabelText("Calibre folder"), [
      pick("Documents/notes.txt"),
    ]);

    expect(await screen.findByText(/holds no metadata\.db/i)).toBeVisible();
    expect(
      screen.getByRole("button", { name: /preview calibre library/i }),
    ).toBeDisabled();
    expect(calls.some((url) => url.includes("/preview"))).toBe(false);
  });

  it("asks what is already imported and sends only the rest", async () => {
    // Content-addressing dedupes storage but not transfer, so an unchanged
    // re-sync would otherwise pay full price every time (DEC-082).
    const sent: FormData[] = [];
    stubRegistry((url) => {
      if (url.endsWith("calibre/plan"))
        return new Response(
          JSON.stringify({
            wanted: ["metadata.db"],
            holding: 1,
            reason: "1 already in your library with a cover",
          }),
        );
      if (url.endsWith("calibre/preview"))
        return new Response(
          JSON.stringify({
            batch_id: "inc-1",
            fingerprint: "db",
            state: "previewed",
            summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
            records: [],
          }),
          { status: 201 },
        );
      return undefined;
    });
    const inner = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.body instanceof FormData) sent.push(init.body);
      return inner(input, init);
    });
    renderImportPage("/import?tab=calibre");

    await userEvent.upload(await screen.findByLabelText("Calibre folder"), [
      pick("Calibre Library/metadata.db", 416 * 1024),
      pick("Calibre Library/A/One (1)/cover.jpg", 1200),
    ]);
    await userEvent.click(
      screen.getByRole("button", { name: /preview calibre library/i }),
    );
    await screen.findByRole("heading", { name: /preview: 1 row/i });

    // Two requests: the plan carries only the database plus the manifest, and
    // the preview carries only what the plan asked for.
    const [plan, preview] = sent;
    expect((plan.getAll("files") as File[]).map((f) => f.name)).toEqual([
      "metadata.db",
    ]);
    expect(JSON.parse(String(plan.get("manifest")))).toEqual([
      { path: "metadata.db", size: 416 * 1024 },
      { path: "A/One (1)/cover.jpg", size: 1200 },
    ]);
    expect((preview.getAll("files") as File[]).map((f) => f.name)).toEqual([
      "metadata.db",
    ]);

    expect(
      await screen.findByText(/skipped 1 file .* already in your library/i),
    ).toBeVisible();
  });

  it("sends everything and says so when the plan fails", async () => {
    // An optimisation that can fail closed turns a working import into a broken
    // one, so a rejected plan degrades rather than stopping (DEC-082).
    const sent: FormData[] = [];
    stubRegistry((url) => {
      if (url.endsWith("calibre/plan"))
        return new Response(JSON.stringify({ error: { code: "boom" } }), {
          status: 500,
        });
      if (url.endsWith("calibre/preview"))
        return new Response(
          JSON.stringify({
            batch_id: "inc-2",
            fingerprint: "db",
            state: "previewed",
            summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
            records: [],
          }),
          { status: 201 },
        );
      return undefined;
    });
    const inner = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.body instanceof FormData) sent.push(init.body);
      return inner(input, init);
    });
    renderImportPage("/import?tab=calibre");

    await userEvent.upload(await screen.findByLabelText("Calibre folder"), [
      pick("Calibre Library/metadata.db", 416 * 1024),
      pick("Calibre Library/A/One (1)/cover.jpg", 1200),
    ]);
    await userEvent.click(
      screen.getByRole("button", { name: /preview calibre library/i }),
    );

    // The import still completed, with everything.
    await screen.findByRole("heading", { name: /preview: 1 row/i });
    expect((sent.at(-1)?.getAll("files") as File[]).map((f) => f.name)).toEqual(
      ["metadata.db", "A/One (1)/cover.jpg"],
    );
    expect(
      await screen.findByText(/could not check what is already imported/i),
    ).toBeVisible();
  });

  it("opens on the importer used last", async () => {
    // The same rule the library tab follows (DEC-062): the default is what you
    // did last, because a person importing a Calibre library does it more than
    // once and the wrong default costs a click every time.
    localStorage.setItem("akasha.import.source", "calibre");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(importers)),
    );
    renderImportPage();

    expect(await screen.findByLabelText("Calibre folder")).toBeVisible();
  });
});
