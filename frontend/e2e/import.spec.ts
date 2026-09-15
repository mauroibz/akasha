import { fileURLToPath } from "node:url";

import { expect, test } from "./console";

import { chooseOption } from "./radix";
import {
  albumItemType,
  bookItemType,
  entry,
  stubExports,
  stubImporters,
  stubItemTypes,
} from "./seed";

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
  await page.getByRole("tab", { name: /calibre/i }).press("Enter");
  // The mount is the alternate now; reaching it is part of the keyboard path.
  await page
    .getByRole("button", { name: /import from a mounted/i })
    .press("Enter");
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
  // Finding 3 (AC3): a legible sentence, not the raw field/code a reader
  // used to see.
  await expect(page.getByText("date_read: invalid_date")).toHaveCount(0);
  await expect(
    page.getByText("Date read isn't a date we can read."),
  ).toBeVisible();
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
  await page.getByRole("button", { name: /import from a mounted/i }).click();

  // Guidance the connector published, not copy this screen owns.
  await expect(
    page.getByText(/choose your calibre library folder/i).first(),
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
  await page.getByRole("button", { name: /import from a mounted/i }).click();
  await page.getByRole("button", { name: "Locked" }).click();
  await page.getByRole("button", { name: /preview calibre library/i }).click();

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("could not read this library");
  await expect(alert).toContainText("Close Calibre and try again");
});

test("a Calibre folder is chosen in the browser, with no mount involved", async ({
  page,
}) => {
  // The flow only a real browser can prove: `webkitdirectory` hands the page the
  // whole tree, and what the client sends is the small part of it (DEC-081).
  let members: string[] = [];
  // The folder flow plans before it previews; this spec is about the filter, so the
  // plan simply wants everything it was offered.
  await page.route("**/api/import/calibre/plan", async (route) => {
    const body = route.request().postData() ?? "";
    const manifest = /name="manifest"\r?\n\r?\n([\s\S]*?)\r?\n--/.exec(body);
    await route.fulfill({
      json: {
        wanted: JSON.parse(manifest?.[1] ?? "[]").map(
          (row: { path: string }) => row.path,
        ),
        holding: 0,
        reason: null,
      },
    });
  });
  await page.route("**/api/import/calibre/preview", async (route) => {
    const body = route.request().postData() ?? "";
    members = [...body.matchAll(/filename="([^"]+)"/g)].map(
      (match) => match[1],
    );
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "folder-1",
        fingerprint: "db",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [{ ...record, title: "Mistborn" }],
      },
    });
  });

  await page.goto("/import?tab=calibre");
  await page
    .getByLabel("Calibre folder", { exact: true })
    .setInputFiles(
      fileURLToPath(new URL("fixtures/Calibre Library", import.meta.url)),
    );

  // Counted and sized before anything leaves the machine.
  await expect(
    page.getByText(/sending metadata\.db and 1 cover/i),
  ).toBeVisible();
  // Four left behind: the ebook, the opf, the prefs backup and the trash cover.
  await expect(
    page.getByText(/4 other files stay on your machine/i),
  ).toBeVisible();

  await page.getByRole("button", { name: /preview calibre library/i }).click();
  await expect(
    page.getByRole("heading", { name: /preview: 1 row/i }),
  ).toBeVisible();

  // The ebook, the opf, the prefs backup and the trash cover all stayed behind.
  expect(members).toEqual([
    "metadata.db",
    "Brandon Sanderson/Mistborn_ The Final Empire (2)/cover.jpg",
  ]);
});

test("a Calibre export's part files are dropped in together and sent as-is", async ({
  page,
}) => {
  // The export alternate is the third way in (DEC-081, generalized): unlike the
  // folder picker, there is no tree to filter, so what arrives is exactly what
  // was offered — this drives the real `<input type="file" multiple>` the way a
  // reader dropping two exported files would.
  let parts: string[] = [];
  await page.route("**/api/import/calibre/preview", async (route) => {
    const body = route.request().postData() ?? "";
    parts = [...body.matchAll(/name="parts"; filename="([^"]+)"/g)].map(
      (match) => match[1],
    );
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "export-1",
        fingerprint: "db",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [{ ...record, title: "Mistborn" }],
      },
    });
  });

  await page.goto("/import?tab=calibre");
  await page.getByRole("button", { name: /calibre's own export/i }).click();
  await page.getByLabel("Calibre export", { exact: true }).setInputFiles([
    {
      name: "part-0001.calibre-data",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("part one bytes"),
    },
    {
      name: "part-0002.calibre-data",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("part two bytes, including a manifest"),
    },
  ]);

  await expect(page.getByText(/2 files selected/i)).toBeVisible();

  await page.getByRole("button", { name: /preview calibre library/i }).click();
  await expect(
    page.getByRole("heading", { name: /preview: 1 row/i }),
  ).toBeVisible();

  expect(parts).toEqual(["part-0001.calibre-data", "part-0002.calibre-data"]);
});

test("Calibre attaches one ebook after commit and sends none on re-sync", async ({
  page,
}) => {
  const previews: string[][] = [];
  const attachments: string[] = [];
  let plans = 0;
  let batches = 0;
  await page.route("**/api/import/calibre/plan", async (route) => {
    plans += 1;
    const body = route.request().postData() ?? "";
    const manifest = /name="manifest"\r?\n\r?\n([\s\S]*?)\r?\n--/.exec(body);
    const offered = JSON.parse(manifest?.[1] ?? "[]") as Array<{
      path: string;
    }>;
    await route.fulfill({
      json:
        plans === 1
          ? {
              wanted: offered.map((row) => row.path),
              holding: 0,
              reason: null,
            }
          : {
              wanted: ["metadata.db"],
              holding: 2,
              reason:
                "1 already in your library with a cover and 1 whose file you already have",
            },
    });
  });
  await page.route("**/api/import/calibre/preview", async (route) => {
    batches += 1;
    const body = route.request().postData() ?? "";
    previews.push(
      [...body.matchAll(/filename="([^"]+)"/g)].map((match) => match[1]),
    );
    await route.fulfill({
      status: 201,
      json: {
        batch_id: `ebooks-${batches}`,
        fingerprint: `db-${batches}`,
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [{ ...record, title: "Mistborn" }],
      },
    });
  });
  await page.route("**/api/import/calibre/commit", (route) =>
    route.fulfill({
      json: {
        batch_id: `ebooks-${batches}`,
        state: "committed",
        created_items: batches === 1 ? 1 : 0,
        created_entries: batches === 1 ? 1 : 0,
        unchanged_entries: batches === 1 ? 0 : 1,
        unsorted_entries: 1,
      },
    }),
  );
  await page.route("**/api/import/calibre/batches/*/files", async (route) => {
    const body = route.request().postData() ?? "";
    const path = /name="path"\r?\n\r?\n([\s\S]*?)\r?\n--/.exec(body);
    attachments.push(path?.[1] ?? "");
    // The request remains open while the screen names the file in flight; a final
    // success count alone would not prove visible per-file progress.
    await expect(page.getByText(/attaching ebook 1 of 1/i)).toBeVisible();
    await route.fulfill({
      status: 201,
      json: {
        id: 1,
        item_id: 1,
        filename: "book.epub",
        byte_size: 40_000,
        sha256: "a".repeat(64),
      },
    });
  });

  const selectAndAttach = async () => {
    await page
      .getByLabel("Calibre folder", { exact: true })
      .setInputFiles(
        fileURLToPath(new URL("fixtures/Calibre Library", import.meta.url)),
      );
    await page
      .getByRole("checkbox", { name: /also attach the ebook files/i })
      .check();
    await page
      .getByRole("button", { name: /preview calibre library/i })
      .click();
    await page.getByRole("button", { name: /import 1 ready row/i }).click();
  };

  await page.goto("/import?tab=calibre");
  await selectAndAttach();
  await expect(page.getByText(/attached 1 of 1 ebook/i)).toBeVisible();
  expect(previews[0]).toEqual([
    "metadata.db",
    "Brandon Sanderson/Mistborn_ The Final Empire (2)/cover.jpg",
  ]);
  expect(attachments).toEqual([
    "Brandon Sanderson/Mistborn_ The Final Empire (2)/book.epub",
  ]);

  await page.reload();
  await selectAndAttach();
  await expect(page.getByText(/1 whose file you already have/i)).toBeVisible();
  expect(previews[1]).toEqual(["metadata.db"]);
  expect(attachments).toHaveLength(1);
});

test("a second import of the same folder sends the database and nothing else", async ({
  page,
}) => {
  // The point of DEC-082: an unchanged re-sync is a 416 KB round trip, not the
  // whole bundle. The server answers from identities it already holds.
  const previews: string[][] = [];
  await page.route("**/api/import/calibre/plan", (route) =>
    // Second time round, the library already holds the book with its cover.
    route.fulfill({
      json: {
        wanted: ["metadata.db"],
        holding: 1,
        reason: "1 already in your library with a cover",
      },
    }),
  );
  await page.route("**/api/import/calibre/preview", async (route) => {
    const body = route.request().postData() ?? "";
    previews.push([...body.matchAll(/filename="([^"]+)"/g)].map((m) => m[1]));
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "resync",
        fingerprint: "db",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [{ ...record, title: "Mistborn" }],
      },
    });
  });

  await page.goto("/import?tab=calibre");
  await page
    .getByLabel("Calibre folder", { exact: true })
    .setInputFiles(
      fileURLToPath(new URL("fixtures/Calibre Library", import.meta.url)),
    );
  await page.getByRole("button", { name: /preview calibre library/i }).click();
  await expect(
    page.getByRole("heading", { name: /preview: 1 row/i }),
  ).toBeVisible();

  await expect(
    page.getByText(/skipped 1 file .* already in your library/i),
  ).toBeVisible();
  // The cover stayed home even though the reader chose the same folder.
  expect(previews.at(-1)).toEqual(["metadata.db"]);
});

test.describe("the export tab (Sprint 069)", () => {
  test.beforeEach(async ({ page }) => {
    await stubExports(page);
  });

  test("/export reaches the tab, and it survives a reload", async ({
    page,
  }) => {
    await page.goto("/export");
    await expect(page).toHaveURL(/\/import\?tab=export/);
    await expect(page.getByRole("heading", { name: "Export" })).toBeVisible();

    await page.reload();
    await expect(page).toHaveURL(/\/import\?tab=export/);
    await expect(page.getByRole("heading", { name: "Export" })).toBeVisible();
  });

  test("downloads a real file end to end, for the lossless row and a declared view", async ({
    page,
  }) => {
    await page.goto("/import?tab=export");
    await expect(page.getByRole("heading", { name: "Export" })).toBeVisible();

    const losslessRow = page.locator('[data-export-row="lossless"]');
    const [lossless] = await Promise.all([
      page.waitForEvent("download"),
      losslessRow.getByRole("button", { name: /download/i }).click(),
    ]);
    expect(lossless.suggestedFilename()).toBe("akasha-export.json");

    const bookRow = page.locator("article", { hasText: "Goodreads" });
    const [goodreads] = await Promise.all([
      page.waitForEvent("download"),
      bookRow.getByRole("button", { name: /download/i }).click(),
    ]);
    expect(goodreads.suggestedFilename()).toBe("akasha-book-goodreads.csv");
    const path = await goodreads.path();
    expect(path).not.toBeNull();
  });

  test("a zero-entry domain offers no download and says why", async ({
    page,
  }) => {
    await page.goto("/import?tab=export");
    const albumRow = page.locator("article", { hasText: "Table (Albums)" });
    await expect(albumRow.getByText("0 entries")).toBeVisible();
    await expect(
      albumRow.getByRole("button", { name: /download/i }),
    ).toBeDisabled();
    await expect(albumRow.getByText(/nothing to export yet/i)).toBeVisible();
  });

  test("the export tab fits a phone, and nothing makes the body scroll sideways", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/import?tab=export");
    await expect(page.getByRole("heading", { name: "Export" })).toBeVisible();

    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);

    const short = await page.evaluate(() =>
      [...document.querySelectorAll("main button, main a[href]")]
        .filter((node) => (node as HTMLElement).offsetParent !== null)
        .map((node) => ({
          text: (node.textContent ?? "").trim().slice(0, 30),
          height: node.getBoundingClientRect().height,
        }))
        .filter((row) => row.height > 0 && row.height < 44),
    );
    expect(short).toEqual([]);
  });
});

test("the import source strip fits a phone with seven connectors, and scrolls within itself (DEC-137)", async ({
  page,
}) => {
  // DEC-137: found by Sprint 070's own walkthrough against the real backend's
  // seven registered importers (Goodreads, Calibre, MyAnimeList, Letterboxd,
  // IMDb, Trakt, Spotify) — a bare TabsList overflowed a 390px viewport by
  // about 205px. Out of that sprint's scope; fixed here at the owner's
  // direction, the same structural fix DEC-134 applied to the domain strip.
  const sevenImporters = [
    // The list leads the strip now (Sprint 085), but this spec's concern is
    // width: seven fat tabs must fit a 390px viewport by scrolling.
    "list",
    "goodreads",
    "calibre",
    "myanimelist",
    "letterboxd",
    "imdb",
    "trakt",
  ].map((id) => ({
    id,
    label: id[0].toUpperCase() + id.slice(1),
    item_types: id === "list" ? ["book", "album"] : ["book"],
    attachment_max_bytes: 25 * 1024 * 1024,
    input: {
      kind: "upload",
      label: `${id} CSV`,
      field: "file",
      accept: ".csv,text/csv",
      placeholder: null,
      help: null,
      guide: [],
      empty_state: "Drop a file here, or choose one.",
      help_url: null,
      browsable: false,
      incremental: false,
      accepts_files: false,
      max_bytes: null,
      max_files: null,
      alternates: [],
    },
  }));
  await page.route("**/api/importers", (route) =>
    route.fulfill({ json: sevenImporters }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/import");

  const strip = page.getByRole("tablist", { name: "Import source" });
  await expect(strip.getByRole("tab")).toHaveCount(7);

  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow, "horizontal page overflow").toBeLessThanOrEqual(0);

  const stripBox = await strip.evaluate((node) => ({
    scrollWidth: node.scrollWidth,
    clientWidth: node.clientWidth,
    boundingWidth: node.getBoundingClientRect().width,
  }));
  expect(stripBox.scrollWidth).toBeGreaterThan(stripBox.clientWidth);
  expect(stripBox.boundingWidth).toBeLessThanOrEqual(390);

  const heights = await strip
    .getByRole("tab")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().height),
    );
  for (const height of heights) expect(height).toBeGreaterThanOrEqual(44);
});

test("the list connector searches, proposes, and takes the owner's answers before commit (Sprint 083)", async ({
  page,
}) => {
  // The search-then-confirm flow against stubbed routes: the batch stages in
  // `matching` with a live job progress, the poll drains it to `previewed`,
  // each row's proposals render with Confirm/Discard controls, and the
  // answers ride the proposal route the backend defines. The provider half of
  // the real flow is proven against recorded Open Library responses in the
  // backend suite (DEC-025); this spec pins the screen's contract.
  const listRecord = (overrides: Record<string, unknown> = {}) => ({
    record_id: 1,
    row_number: 2,
    title: "Rayuela",
    creators: ["Julio Cortázar"],
    suggested_status: null,
    score: null,
    score_provisional: false,
    shelves: [],
    errors: [],
    planned_action: "create_item",
    match_kind: "new",
    candidates: [],
    item: {
      title: "Rayuela",
      subtitle: null,
      year: null,
      identifiers: {},
      metadata: { creators: ["Julio Cortázar"] },
      creator_sort: null,
    },
    entry: {
      score: null,
      notes: null,
      date_added: null,
      values: {},
      score_provisional: false,
      suggested_status: null,
    },
    source_fields: { Editorial: "Sudamericana" },
    proposals: [],
    ...overrides,
  });
  const proposal = {
    source: "openlibrary",
    source_id: "OL1M",
    rank: 0,
    chosen: null,
    payload: {
      title: "Rayuela",
      subtitle: null,
      creators: ["Julio Cortázar"],
      year: 1963,
      identifiers: { isbn: "9788437604572" },
      language: "es",
      metadata: { publisher: "Sudamericana" },
      cover_url: null,
      cover_fallback_urls: [],
    },
  };

  let answered = false;
  let excluded = false;
  let commitBody: unknown;
  await stubItemTypes(page, [bookItemType]);
  await page.route("**/api/import/list/preview", async (route) => {
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "list-1",
        fingerprint: "csv",
        state: "matching",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        search_progress: { searched: 0, total: 1, job_state: "running" },
        records: [listRecord({ proposals: [] })],
      },
    });
  });
  await page.route("**/api/import/list/batches/list-1", async (route) => {
    await route.fulfill({
      json: {
        batch_id: "list-1",
        fingerprint: "csv",
        state: "previewed",
        summary: { total: 1, ready: excluded ? 0 : 1, errors: 0, ambiguous: 0 },
        records: [
          listRecord({
            planned_action: excluded ? "excluded" : "create_item",
            proposals: [{ ...proposal, chosen: answered ? true : null }],
          }),
        ],
      },
    });
  });
  await page.route(
    "**/api/import/list/batches/list-1/records/1/exclude",
    async (route) => {
      excluded = true;
      await route.fulfill({ status: 200, json: { ok: true } });
    },
  );
  await page.route(
    "**/api/import/list/batches/list-1/records/1/include",
    async (route) => {
      excluded = false;
      await route.fulfill({ status: 200, json: { ok: true } });
    },
  );
  await page.route(
    "**/api/import/list/batches/list-1/records/1/proposal",
    async (route) => {
      answered = true;
      await route.fulfill({
        json: {
          batch_id: "list-1",
          fingerprint: "csv",
          state: "previewed",
          summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
          records: [listRecord({ proposals: [{ ...proposal, chosen: true }] })],
        },
      });
    },
  );
  await page.route("**/api/import/list/commit", async (route) => {
    commitBody = route.request().postDataJSON();
    await route.fulfill({
      json: {
        batch_id: "list-1",
        state: "committed",
        created_items: 1,
        created_entries: 1,
        unchanged_entries: 0,
        unsorted_entries: 1,
      },
    });
  });

  await page.goto("/import");
  await page.getByRole("tab", { name: /custom list/i }).click();
  // The declared column mapping renders from the catalog's declaration,
  // in the picked library's own words (books call the second column
  // Creators — the domain's field label, Sprint 084).
  await expect(page.getByLabel(/title is column/i)).toBeVisible();
  await expect(page.getByLabel(/creators is column/i)).toBeVisible();
  // The drop-zone's label also names its guide list, so the file input is
  // reached by id rather than by label (the input is the drop zone's own).
  await page.locator("#list-source").setInputFiles({
    name: "libros.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("Título del libro,Autor\r\nRayuela,Julio Cortázar"),
  });
  await page.getByRole("button", { name: /preview/i }).click();

  // The searching banner shows the job's live counts, and the commit gate is
  // closed while the batch is still matching.
  await expect(page.getByTestId("search-progress")).toContainText(
    "Searching for matches: 0 of 1 rows searched.",
  );
  const gate = page.getByRole("button", {
    name: /waiting for the search/i,
  });
  await expect(gate).toBeDisabled();

  // The poll (2s interval) drains the batch and the proposals render.
  const confirm = page.getByRole("button", { name: "Confirm", exact: true });
  await expect(confirm).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole("button", { name: /import 1 ready row/i }),
  ).toBeEnabled();
  await expect(page.getByText(/is one of these the book\?/i)).toBeVisible();
  await expect(page.getByText("openlibrary")).toBeVisible();

  // The row's own way out exists before any answer.
  await expect(
    page.getByRole("button", { name: /none of these — keep as typed/i }),
  ).toBeEnabled();

  // Confirming rides the proposal route.
  await confirm.click();
  await expect(page.getByText("Confirmed")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /undo my answer/i }),
  ).toBeEnabled();

  // The owner's 2026-09-14 batch: a row can leave the import entirely, and
  // the exclusion is its own undo. Excluded, the commit gate counts it out.
  const exclude = page.getByRole("button", { name: /don't import this row/i });
  await exclude.click();
  await expect(
    page.getByRole("button", { name: /import this row after all/i }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole("button", { name: /import 0 ready rows/i }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: /import this row after all/i })
    .click();
  await expect(
    page.getByRole("button", { name: /import 1 ready row/i }),
  ).toBeEnabled({ timeout: 10_000 });

  await page.getByRole("button", { name: /import 1 ready row/i }).click();
  await expect(page.getByRole("status")).toContainText("1 entry added");
  expect(commitBody).toEqual({ batch_id: "list-1", choices: [] });
});

test("the list connector picks its library before the file, and the choice rides the preview (Sprint 084)", async ({
  page,
}) => {
  const sent: string[] = [];
  // The domain dropdown and the creators-word label read the domains' own
  // published labels: books and albums, the way the real API serves them.
  await stubItemTypes(page, [bookItemType, albumItemType]);
  await page.route("**/api/import/list/preview", async (route) => {
    // Multipart: read the targets field off the request body
    const body = route.request().postData() ?? "";
    const match = body.match(/name="targets"\r\n\r\n([^\r]+)\r\n/);
    sent.push(match ? match[1] : "(none)");
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "list-1",
        fingerprint: "csv#album",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [],
      },
    });
  });

  await page.goto("/import");
  await page.getByRole("tab", { name: /custom list/i }).click();

  // The dropdown renders from the declaration — one pick, not checkboxes.
  const dropdown = page.getByRole("combobox", {
    name: /which library is this list for\?/i,
  });
  await expect(dropdown).toBeVisible();
  // The tick-many checkboxes are absent: the reader refuses a mixed batch.
  await expect(page.getByRole("checkbox", { name: /albums?/i })).toHaveCount(0);

  // Pick albums; the mapping label follows the album domain's own word.
  await dropdown.selectOption("album");
  // The album domain's own creators word (Artists, per its field spec).
  await expect(page.getByText(/artists is column/i)).toBeVisible();

  await page.locator("#list-source").setInputFiles({
    name: "discos.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("Álbum,Artista\r\nKind of Blue,Miles Davis"),
  });
  await page.getByRole("button", { name: /preview/i }).click();
  // No dropdown assertion here on purpose: once the preview response lands
  // the screen transitions from the source form to the batch surface, so the
  // dropdown's post-preview existence is a render race, not a contract. The
  // contract this spec pins is the choice riding the multipart body.
  expect(sent).toEqual(["album"]);
});

test("the list leads the strip, names its domains, and typed entries import with no file (Sprint 085)", async ({
  page,
}) => {
  const sent: string[] = [];
  await stubImporters(page);
  await stubItemTypes(page, [bookItemType, albumItemType]);
  await page.route("**/api/import/list/preview", async (route) => {
    // Playwright exposes the multipart body as a Buffer; parse the parts.
    const body = route.request().postDataBuffer()?.toString("latin1") ?? "";
    const flag = /name="no_creators"\r\n\r\n([^\r]+)\r\n/.exec(body);
    sent.push(flag ? flag[1] : "(none)");
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "list-typed",
        fingerprint: "csv#book",
        state: "matching",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        search_progress: { searched: 0, total: 1, job_state: "running" },
        records: [],
      },
    });
  });

  await page.goto("/import");

  // The custom list is the very first tab (the owner's ask), and every tab
  // names the library it serves from its own declaration.
  const firstTab = page
    .getByRole("tablist", { name: "Import source" })
    .getByRole("tab")
    .first();
  await expect(firstTab).toContainText(/custom list/i);
  await expect(firstTab).toContainText(/any library/i);
  await expect(page.getByRole("tab", { name: /goodreads/i })).toContainText(
    /book/i,
  );

  // Type three entries straight into the editor; no file is chosen.
  await page
    .getByRole("textbox", { name: /or type your list here/i })
    .fill("Título,Autor\r\nRayuela,Julio Cortázar\r\nEl Hobbit,Tolkien");
  // The creators checkbox is the owner's opt-out; leave it unchecked first.
  await page.getByRole("button", { name: /preview/i }).click();
  // The typed rows previewed: the search-progress surface replaced the form
  // and the request carried no no_creators flag.
  await expect(page.getByText(/searching for matches/i)).toBeVisible();
  await expect(sent).toEqual(["(none)"]);
});

test("the list connector unfolds deeper proposals behind Show more (2026-09-14 owner batch)", async ({
  page,
}) => {
  // Ten are stored per row; three render. The stub offers five so the fold is
  // visible without a real provider: the deeper answers exist for the rows
  // where the right result ranks badly.
  const listRecord = (overrides: Record<string, unknown> = {}) => ({
    record_id: 1,
    row_number: 2,
    title: "Rayuela",
    creators: ["Julio Cortázar"],
    suggested_status: null,
    score: null,
    score_provisional: false,
    shelves: [],
    errors: [],
    planned_action: "create_item",
    match_kind: "new",
    candidates: [],
    item: {
      title: "Rayuela",
      subtitle: null,
      year: null,
      identifiers: {},
      metadata: { creators: ["Julio Cortázar"] },
      creator_sort: null,
    },
    entry: {
      score: null,
      notes: null,
      date_added: null,
      values: {},
      score_provisional: false,
      suggested_status: null,
    },
    source_fields: {},
    proposals: [],
    ...overrides,
  });
  const five = [1, 2, 3, 4, 5].map((index) => ({
    source: "openlibrary",
    source_id: `OL${index}M`,
    rank: index - 1,
    chosen: null,
    payload: {
      title: `Rayuela edition ${index}`,
      subtitle: null,
      creators: ["Julio Cortázar"],
      year: 1963,
      identifiers: { isbn: `978000000000${index}` },
      language: "es",
      metadata: {},
      cover_url: null,
      cover_fallback_urls: [],
    },
  }));

  await page.route("**/api/import/list/preview", (route) =>
    route.fulfill({
      status: 201,
      json: {
        batch_id: "list-1",
        fingerprint: "csv",
        state: "previewed",
        summary: { total: 1, ready: 1, errors: 0, ambiguous: 0 },
        records: [listRecord({ proposals: five })],
      },
    }),
  );

  await page.goto("/import");
  await page.getByRole("tab", { name: /custom list/i }).click();
  await page.locator("#list-source").setInputFiles({
    name: "libros.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("Título del libro,Autor\r\nRayuela,Julio Cortázar"),
  });
  await page.getByRole("button", { name: /preview/i }).click();

  // Three render; Show more names the two it holds back.
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toHaveCount(3);
  await page.getByRole("button", { name: /show more \(2\)/i }).click();
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toHaveCount(5);
  // And it folds back.
  await page.getByRole("button", { name: /show fewer/i }).click();
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toHaveCount(3);

  // The edit-and-research affordance is on every drained row.
  await expect(
    page.getByRole("button", { name: /wrong text\? edit and search again/i }),
  ).toBeVisible();
});
