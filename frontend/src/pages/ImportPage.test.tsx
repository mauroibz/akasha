import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportPage } from "./ImportPage";

afterEach(() => vi.restoreAllMocks());

describe("ImportPage", () => {
  it("previews and commits a confined Calibre library without asking for a file", async () => {
    const requests: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      requests.push([input, init]);
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
                authors: ["Jorge Luis Borges"],
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
    render(
      <MemoryRouter>
        <ImportPage />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("tab", { name: /calibre/i }));
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
    expect(requests[0]).toEqual([
      "/api/import/calibre/preview",
      expect.objectContaining({
        body: JSON.stringify({ library_path: "My Books" }),
      }),
    ]);
    expect(String(requests[1][0])).toContain("/api/import/calibre/commit");
  });

  it("previews once, exposes errors and commits only the recorded batch", async () => {
    const requests: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      requests.push([input, init]);
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
                authors: ["Julio Cortázar"],
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
                authors: [],
                isbn: null,
                suggested_status: null,
                score: null,
                score_provisional: false,
                shelves: [],
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
    render(
      <MemoryRouter>
        <ImportPage />
      </MemoryRouter>,
    );
    const file = new File(["csv"], "library.csv", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText(/goodreads csv/i), file);
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
      /1 book added/i,
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
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
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
              authors: ["Borges"],
              isbn: null,
              suggested_status: null,
              score: null,
              score_provisional: false,
              shelves: [],
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
    render(
      <MemoryRouter>
        <ImportPage />
      </MemoryRouter>,
    );
    await userEvent.upload(
      screen.getByLabelText(/goodreads csv/i),
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
    // The defect: a commit reported "1 book added" and the library showed
    // nothing, because imports land `unsorted` and the default view hides
    // exactly that. The result panel now says where the rows went.
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input).endsWith("/preview")
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
                  authors: ["Julio Cort\u00e1zar"],
                  isbn: "9788437604572",
                  suggested_status: "read",
                  score: 8,
                  score_provisional: true,
                  shelves: [],
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
    render(
      <MemoryRouter>
        <ImportPage />
      </MemoryRouter>,
    );
    await userEvent.upload(
      screen.getByLabelText(/goodreads csv/i),
      new File(["csv"], "library.csv", { type: "text/csv" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /preview import/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /import 1 ready row/i }),
    );
    const result = await screen.findByRole("status");
    expect(result).toHaveTextContent(/7 books are waiting in triage/i);
    expect(screen.getByRole("link", { name: /triage/i })).toHaveAttribute(
      "href",
      "/triage",
    );
  });
});
