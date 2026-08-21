import { expect, test } from "./console";

import { chooseOption } from "./radix";
import { entry, stubImporters } from "./seed";

const record = {
  record_id: 1,
  row_number: 2,
  goodreads_book_id: "101",
  title: "Rayuela",
  creators: ["Julio Cortázar"],
  isbn: "9788437604572",
  suggested_status: "read",
  score: 8,
  score_provisional: true,
  shelves: ["favoritos"],
  errors: [],
  planned_action: "create_item",
  match_kind: "new",
  candidates: [],
};

test.beforeEach(async ({ page }) => {
  await stubImporters(page);
});

test("Goodreads preview and commit stay keyboard-complete at mobile width", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 740 });
  let previews = 0;
  let commitBody: unknown;
  // Followed at the end of this test, so triage has to have something to show,
  // and the three rows it shows are the three the result panel promised.
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: [1, 2, 3].map((id) => ({
          ...entry(id),
          status: "unsorted",
        })),
        next_cursor: null,
        total: 3,
        facets: {
          status_counts: { unsorted: 3 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/import/goodreads/preview", async (route) => {
    previews += 1;
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "batch-1",
        fingerprint: "abc",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [record],
      },
    });
  });
  await page.route("**/api/import/goodreads/commit", async (route) => {
    commitBody = route.request().postDataJSON();
    await route.fulfill({
      json: {
        batch_id: "batch-1",
        state: "committed",
        created_items: 1,
        created_entries: 1,
        unchanged_entries: 0,
        unsorted_entries: 3,
      },
    });
  });
  await page.goto("/import");
  await expect(page.getByLabel("Goodreads CSV", { exact: true })).toBeFocused();
  await page.getByLabel("Goodreads CSV", { exact: true }).setInputFiles({
    name: "library.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("csv"),
  });
  await page.getByRole("button", { name: /preview import/i }).press("Enter");
  await expect(
    page.getByRole("heading", { name: /preview: 1 row/i }),
  ).toBeFocused();
  await page
    .getByRole("button", { name: /import 1 ready row/i })
    .press("Enter");
  await expect(page.getByRole("status")).toContainText("1 entry added");
  // Imports land `unsorted` and the default library view hides `unsorted`, so
  // the result panel names the pile and offers the click that reaches it.
  await expect(page.getByRole("status")).toContainText(
    "3 entries are waiting in Triage",
  );
  await page.getByRole("link", { name: /open triage/i }).click();
  await expect(page).toHaveURL(/\/import\?tab=triage/);
  await expect(
    page.getByRole("heading", { level: 1, name: /inbox/i }),
  ).toContainText("3 unsorted");
  expect(previews).toBe(1);
  expect(commitBody).toEqual({ batch_id: "batch-1", choices: [] });
  await expect(page.locator("main")).toBeVisible();
});

test("Calibre preview and re-sync are keyboard-complete at mobile width", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 740 });
  let previewBody: unknown;
  let commitBody: unknown;
  await page.route("**/api/import/calibre/preview", async (route) => {
    previewBody = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "calibre-1",
        fingerprint: "db",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [
          {
            ...record,
            goodreads_book_id: null,
            calibre_book_id: "1",
            calibre_uuid: "uuid-1",
            title: "Ficciones",
            creators: ["Jorge Luis Borges"],
            score: 9,
            score_provisional: false,
            cover_staged: true,
          },
        ],
      },
    });
  });
  await page.route("**/api/import/calibre/commit", async (route) => {
    commitBody = route.request().postDataJSON();
    await route.fulfill({
      json: {
        batch_id: "calibre-1",
        state: "committed",
        created_items: 1,
        created_entries: 1,
        unchanged_entries: 0,
        unsorted_entries: 3,
      },
    });
  });
  await page.goto("/import");
  await page.getByRole("tab", { name: "Calibre" }).press("Enter");
  await expect(page.getByLabel(/calibre library path/i)).toBeFocused();
  await page.getByLabel(/calibre library path/i).fill("Library");
  await page.getByRole("button", { name: /preview calibre/i }).press("Enter");
  await expect(page.getByText(/local cover staged/i)).toBeVisible();
  await page
    .getByRole("button", { name: /import 1 ready row/i })
    .press("Enter");
  await expect(page.getByRole("status")).toContainText("1 entry added");
  expect(previewBody).toEqual({ library_path: "Library" });
  expect(commitBody).toEqual({ batch_id: "calibre-1", choices: [] });
});

test("row errors and ambiguity require an explicit choice", async ({
  page,
}) => {
  await page.route("**/api/import/goodreads/preview", (route) =>
    route.fulfill({
      status: 201,
      json: {
        batch_id: "batch-2",
        fingerprint: "def",
        state: "previewed",
        summary: { total: 2, ready: 0, errors: 1, ambiguous: 1 },
        records: [
          {
            ...record,
            planned_action: "ambiguous",
            match_kind: "ambiguous",
            candidates: [7],
          },
          {
            ...record,
            record_id: 2,
            title: "Bad row",
            planned_action: "error",
            errors: [{ field: "date_read", code: "invalid_date" }],
          },
        ],
      },
    }),
  );
  await page.goto("/import");
  await page.getByLabel("Goodreads CSV", { exact: true }).setInputFiles({
    name: "library.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("csv"),
  });
  await page.getByRole("button", { name: /preview import/i }).click();
  await expect(page.getByText("date_read: invalid_date")).toBeVisible();
  const commit = page.getByRole("button", { name: /import 1 ready row/i });
  await expect(commit).toBeDisabled();
  await chooseOption(
    page,
    page.getByRole("combobox", { name: /choice for Rayuela/i }),
    "Create a separate edition",
  );
  await expect(commit).toBeEnabled();
});

test("malformed and oversized uploads remain recoverable", async ({ page }) => {
  let request = 0;
  await page.route("**/api/import/goodreads/preview", (route) => {
    request += 1;
    const oversized = request === 2;
    return route.fulfill({
      status: oversized ? 413 : 422,
      json: {
        error: {
          code: oversized ? "import_too_large" : "missing_columns",
          message: oversized
            ? "Goodreads CSV exceeds 5 MiB"
            : "Required Goodreads columns are missing",
          details: {},
        },
      },
    });
  });
  await page.goto("/import");
  const upload = page.getByLabel("Goodreads CSV", { exact: true });
  await upload.setInputFiles({
    name: "bad.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("bad"),
  });
  await page.getByRole("button", { name: /preview import/i }).click();
  await expect(page.getByRole("alert")).toContainText("columns are missing");
  await upload.setInputFiles({
    name: "large.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("large"),
  });
  await page.getByRole("button", { name: /preview import/i }).click();
  await expect(page.getByRole("alert")).toContainText("exceeds 5 MiB");
  await expect(upload).toBeVisible();
});

test("undo flow from import history", async ({ page }) => {
  let commitCount = 0;
  await page.route("**/api/import/goodreads/preview", (route) =>
    route.fulfill({
      status: 201,
      json: {
        batch_id: "undo-batch",
        fingerprint: "abc",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [record],
      },
    }),
  );
  await page.route("**/api/import/goodreads/commit", (route) => {
    commitCount += 1;
    return route.fulfill({
      json: {
        batch_id: "undo-batch",
        state: "committed",
        created_items: 1,
        created_entries: 1,
        unchanged_entries: 0,
        unsorted_entries: 3,
      },
    });
  });
  await page.route("**/api/import/batches/undo-batch", (route) =>
    route.fulfill({
      json: {
        batch_id: "undo-batch",
        state: "undone",
        reverted: 2,
        retained: 0,
        skipped: 0,
        reverted_entries: 1,
        reverted_items: 1,
        retained_items: 0,
      },
    }),
  );
  await page.goto("/import");
  await page.getByLabel("Goodreads CSV", { exact: true }).setInputFiles({
    name: "library.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("csv"),
  });
  await page.getByRole("button", { name: /preview import/i }).click();
  await page.getByRole("button", { name: /import 1 ready row/i }).click();
  await expect(page.getByRole("status")).toContainText("1 entry added");
  await expect(
    page.getByRole("button", { name: /undo this import/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /undo this import/i }).click();
  await expect(
    page.getByRole("button", { name: /confirm undo/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /confirm undo/i }).click();
  // The in-page record of the undo, plus the toast that confirms it happened.
  await expect(
    page.getByRole("heading", { name: "Import undone" }),
  ).toBeVisible();
  await expect(
    page.getByText("2 changes reverted", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator("[data-sonner-toast]")
      .filter({ hasText: "Import undone: 2 changes reverted" }),
  ).toBeVisible();
  expect(commitCount).toBe(1);
});

test("undo expired batch shows error", async ({ page }) => {
  await page.route("**/api/import/goodreads/preview", (route) =>
    route.fulfill({
      status: 201,
      json: {
        batch_id: "expired-batch",
        fingerprint: "abc",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [record],
      },
    }),
  );
  await page.route("**/api/import/goodreads/commit", (route) =>
    route.fulfill({
      json: {
        batch_id: "expired-batch",
        state: "committed",
        created_items: 1,
        created_entries: 1,
        unchanged_entries: 0,
        unsorted_entries: 3,
      },
    }),
  );
  await page.route("**/api/import/batches/expired-batch", (route) =>
    route.fulfill({
      status: 409,
      json: {
        error: {
          code: "undo_expired",
          message: "Undo window has expired (24 hours since commit)",
          details: {},
        },
      },
    }),
  );
  await page.goto("/import");
  await page.getByLabel("Goodreads CSV", { exact: true }).setInputFiles({
    name: "library.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("csv"),
  });
  await page.getByRole("button", { name: /preview import/i }).click();
  await page.getByRole("button", { name: /import 1 ready row/i }).click();
  await page.getByRole("button", { name: /undo this import/i }).click();
  await page.getByRole("button", { name: /confirm undo/i }).click();
  await expect(page.getByRole("alert")).toContainText("expired");
});

test("the Calibre tab is browsed into rather than typed blind", async ({
  page,
}) => {
  // The old guidance was "Enter a relative folder only", which nobody can act on
  // without seeing the mount. The picker is the answer (DEC-079).
  const browsed: string[] = [];
  await page.route("**/api/import/calibre/browse**", (route) => {
    const path = new URL(route.request().url()).searchParams.get("path") ?? "";
    browsed.push(path);
    route.fulfill({
      json:
        path === ""
          ? {
              path: "",
              parent: null,
              directories: ["Comics", "Fiction"],
              importable: false,
            }
          : { path, parent: "", directories: [], importable: true },
    });
  });
  let previewed: unknown = null;
  await page.route("**/api/import/calibre/preview", async (route) => {
    previewed = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "calibre-browse",
        fingerprint: "db",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [{ ...record, title: "Ficciones" }],
      },
    });
  });

  await page.goto("/import?tab=calibre");

  // Guidance the connector published, not copy this screen owns.
  await expect(
    page.getByText(/pick the folder that holds metadata\.db/i),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /preview calibre library/i }),
  ).toBeDisabled();

  await page.getByRole("button", { name: "Fiction" }).click();
  await expect(
    page.getByText(/this folder holds a calibre library/i),
  ).toBeVisible();
  await page.getByRole("button", { name: /preview calibre library/i }).click();

  await expect(
    page.getByRole("heading", { name: /preview: 1 row/i }),
  ).toBeVisible();
  expect(previewed).toEqual({ library_path: "Fiction" });
  // The mount root first, then the folder that was opened. Not an exact
  // sequence: StrictMode runs the effect twice in dev, which is the point of it.
  expect(browsed).toContain("");
  expect(browsed.at(-1)).toBe("Fiction");
});

test("a refused read says what to do about it", async ({ page }) => {
  await page.route("**/api/import/calibre/browse**", (route) =>
    route.fulfill({
      json: {
        path: "",
        parent: null,
        directories: ["Locked"],
        importable: false,
      },
    }),
  );
  await page.route("**/api/import/calibre/preview", (route) =>
    route.fulfill({
      status: 422,
      json: {
        error: {
          code: "invalid_calibre_database",
          message: "Calibre database could not be read",
          user_message: "Akasha could not read this library's metadata.db.",
          action:
            "Close Calibre and try again; it locks the database while it is writing.",
        },
      },
    }),
  );

  await page.goto("/import?tab=calibre");
  await page.getByRole("button", { name: "Locked" }).click();
  await page.getByRole("button", { name: /preview calibre library/i }).click();

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("could not read this library");
  await expect(alert).toContainText("Close Calibre and try again");
});
