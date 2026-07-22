import { expect, test } from "@playwright/test";

const record = {
  record_id: 1,
  row_number: 2,
  goodreads_book_id: "101",
  title: "Rayuela",
  authors: ["Julio Cortázar"],
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

test("Goodreads preview and commit stay keyboard-complete at mobile width", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 740 });
  let previews = 0;
  let commitBody: unknown;
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
      },
    });
  });
  await page.goto("/import");
  await expect(page.getByLabel(/goodreads csv/i)).toBeFocused();
  await page.getByLabel(/goodreads csv/i).setInputFiles({
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
  await expect(page.getByRole("status")).toContainText("1 book added");
  expect(previews).toBe(1);
  expect(commitBody).toEqual({ batch_id: "batch-1", choices: [] });
  await expect(page.locator("main")).toBeVisible();
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
  await page.getByLabel(/goodreads csv/i).setInputFiles({
    name: "library.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("csv"),
  });
  await page.getByRole("button", { name: /preview import/i }).click();
  await expect(page.getByText("date_read: invalid_date")).toBeVisible();
  const commit = page.getByRole("button", { name: /import 1 ready row/i });
  await expect(commit).toBeDisabled();
  await page.getByLabel(/choice for Rayuela/i).selectOption("new");
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
  const upload = page.getByLabel(/goodreads csv/i);
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
