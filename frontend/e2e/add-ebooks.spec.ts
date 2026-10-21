import { expect, test } from "./console";

import { entry, stubItemTypes } from "./seed";

/**
 * The owner's 2026-10-19 flow (Sprint 086): open Akasha, click Add, drag three
 * EPUBs in, and have them land in Triage. The drop is a real `drop` event
 * carrying a `DataTransfer`, the way a file manager delivers one.
 */
const epubImporter = {
  id: "epub",
  label: "Ebook files",
  item_types: ["book"],
  attachment_max_bytes: 25 * 1024 * 1024,
  input: {
    kind: "export",
    label: "EPUB files",
    field: "files",
    accept: ".epub",
    placeholder: null,
    help: "Drop EPUB files and each one becomes a book, with its cover and the file attached.",
    guide: [],
    empty_state: "Drop .epub files here.",
    help_url: null,
    browsable: false,
    incremental: false,
    accepts_files: true,
    max_bytes: null,
    max_files: 100,
    quick_add: true,
    alternates: [],
  },
};

const titles = [
  "Designing Data-Intensive Applications",
  "Ficciones",
  "Rayuela",
];

test("three EPUBs dropped on Add are previewed, committed and waiting in the Inbox", async ({
  page,
}) => {
  await stubItemTypes(page);
  await page.route("**/api/importers", (route) =>
    route.fulfill({ json: [epubImporter] }),
  );
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: [1, 2, 3].map((id) => ({ ...entry(id), status: "unsorted" })),
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
  let sent: string[] = [];
  await page.route("**/api/import/epub/preview", async (route) => {
    const body = route.request().postData() ?? "";
    sent = [...body.matchAll(/name="files"; filename="([^"]+)"/g)].map(
      (match) => match[1],
    );
    await route.fulfill({
      status: 201,
      json: {
        batch_id: "epub-1",
        fingerprint: "f",
        state: "previewed",
        summary: { total: 3, ready: 3, errors: 0, ambiguous: 0 },
        records: titles.map((title, index) => ({
          record_id: index + 1,
          row_number: index + 1,
          title,
          creators: [],
          suggested_status: null,
          score: null,
          score_provisional: false,
          shelves: [],
          errors: [],
          planned_action: "create_item",
          match_kind: "new",
          candidates: [],
          cover_staged: true,
          attachment_staged: true,
        })),
      },
    });
  });
  let committed: unknown;
  await page.route("**/api/import/epub/commit", async (route) => {
    committed = route.request().postDataJSON();
    await route.fulfill({
      json: {
        batch_id: "epub-1",
        state: "committed",
        created_items: 3,
        created_entries: 3,
        unchanged_entries: 0,
        unsorted_entries: 3,
      },
    });
  });

  await page.goto("/");
  await page.getByRole("link", { name: /add/i }).first().click();
  await expect(page).toHaveURL("/add");

  const zone = page.getByTestId("epub-export-drop-zone");
  await expect(zone).toBeVisible();
  const transfer = await page.evaluateHandle(
    (names) => {
      const data = new DataTransfer();
      for (const name of names)
        data.items.add(
          new File([`epub bytes of ${name}`], name, {
            type: "application/epub+zip",
          }),
        );
      return data;
    },
    ["ddia.epub", "ficciones.epub", "rayuela.epub"],
  );
  await zone.dispatchEvent("drop", { dataTransfer: transfer });

  await expect(page).toHaveURL("/import?tab=epub");
  await expect(
    page.getByRole("heading", { name: /preview: 3 rows/i }),
  ).toBeVisible();
  expect(sent).toEqual(["ddia.epub", "ficciones.epub", "rayuela.epub"]);
  for (const title of titles) await expect(page.getByText(title)).toBeVisible();

  await page.getByRole("button", { name: /import 3 ready rows/i }).click();
  await expect(page.getByRole("status").first()).toContainText(
    "3 entries added",
  );
  expect(committed).toEqual({ batch_id: "epub-1", choices: [] });
  await page.getByRole("link", { name: /review in inbox/i }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: /inbox/i }),
  ).toContainText("3 unsorted");
});
