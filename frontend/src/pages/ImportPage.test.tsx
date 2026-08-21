import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
    input: {
      kind: "upload",
      label: "Goodreads CSV",
      field: "file",
      accept: ".csv,text/csv",
      placeholder: null,
      help: null,
    },
  },
  {
    id: "calibre",
    label: "Calibre",
    item_type: "book",
    input: {
      kind: "path",
      label: "Calibre library path",
      field: "library_path",
      accept: null,
      placeholder: "Library",
      help: "Akasha opens this library read-only inside the configured Calibre mount.",
    },
  },
];

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
    expect(screen.getByText(/read-only/i)).toBeVisible();
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
    await userEvent.upload(
      await screen.findByLabelText(/goodreads csv/i),
      file,
    );
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
      await screen.findByLabelText(/goodreads csv/i),
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
      await screen.findByLabelText(/goodreads csv/i),
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
    expect(screen.queryByLabelText(/goodreads csv/i)).toBeNull();
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

    expect(await screen.findByLabelText(/library path/i)).toBeVisible();
  });
});
