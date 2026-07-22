import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportPage } from "./ImportPage";

afterEach(() => vi.restoreAllMocks());

describe("ImportPage", () => {
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
    expect(
      await screen.findByLabelText(/choice for Ficciones/i),
    ).toBeRequired();
    expect(screen.getByRole("button", { name: /import/i })).toBeDisabled();
  });
});
