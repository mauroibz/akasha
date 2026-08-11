import { expect, test } from "@playwright/test";

import { chooseOption } from "./radix";

function makeEntries(count: number) {
  const entries = Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    item_id: i + 1,
    status: "unsorted",
    score: null,
    notes: null,
    date_added: "2026-01-01",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    score_provisional: false,
    suggested_status: i % 3 === 0 ? "read" : i % 3 === 1 ? "to_read" : null,
    item: {
      id: i + 1,
      type: "book",
      title: `Book ${i + 1}`,
      subtitle: null,
      year: 2000 + (i % 50),
      sort_author: `Author ${i + 1}`,
      cover_url: null,
      metadata: { authors: [`Author ${i + 1}`] },
      identifiers: {},
      sources: [],
    },
    shelves: [],
  }));
  return entries;
}

test("triage page renders and bulk-accepts suggested statuses", async ({
  page,
}) => {
  const entries = makeEntries(30);
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries.slice(0, 100),
        next_cursor: null,
        total: entries.length,
        facets: { status_counts: { unsorted: 30 } },
      },
    }),
  );
  await page.route("**/api/entries/accept-suggested", (route) =>
    route.fulfill({ json: { affected: 20 } }),
  );

  await page.goto("/triage");
  await expect(page.getByRole("heading", { name: /inbox/i })).toBeVisible();
  await expect(page.getByText("30 unsorted")).toBeVisible();

  // Accept all suggested
  const acceptButton = page.getByRole("button", {
    name: /accept all suggested/i,
  });
  await acceptButton.click();
  await expect(page.getByText("20 suggested statuses accepted")).toBeVisible();
});

test("triage keyboard shortcuts set status on focused row", async ({
  page,
}) => {
  const entries = makeEntries(5);
  let bulkBody: unknown = null;
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: 5,
        facets: { status_counts: { unsorted: 5 } },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkBody = route.request().postDataJSON();
    return route.fulfill({ json: { affected: 1 } });
  });

  await page.goto("/triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();

  // Focus first row and press "r" for read
  await page.locator('[data-entry-id="1"]').focus();
  await page.keyboard.press("r");

  await expect
    .poll(() => bulkBody)
    .toEqual({
      entry_ids: [1],
      set: { status: "read" },
    });
});

test("triage bulk status update with selection", async ({ page }) => {
  const entries = makeEntries(10);
  let bulkBody: unknown = null;
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: 10,
        facets: { status_counts: { unsorted: 10 } },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkBody = route.request().postDataJSON();
    return route.fulfill({ json: { affected: 3 } });
  });

  await page.goto("/triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();

  // Select rows 1-3 via checkboxes
  await page.locator('[data-entry-id="1"] [role="checkbox"]').click();
  await page.locator('[data-entry-id="2"] [role="checkbox"]').click();
  await page.locator('[data-entry-id="3"] [role="checkbox"]').click();

  // Bulk action bar should appear
  await expect(page.getByText("3 selected")).toBeVisible();

  // Set status to read
  await chooseOption(
    page,
    page.getByRole("combobox", { name: "Set status for selected" }),
    "Read",
  );

  await expect
    .poll(() => bulkBody)
    .toEqual({
      entry_ids: [1, 2, 3],
      set: { status: "read" },
    });
  await expect(page.getByText("3 entries updated")).toBeVisible();
});

test("triage Ctrl+A selects all matching with server-side exclusions", async ({
  page,
}) => {
  const entries = makeEntries(100);
  let bulkBody: unknown = null;
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries.slice(0, 100),
        next_cursor: null,
        total: 200,
        facets: { status_counts: { unsorted: 200 } },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkBody = route.request().postDataJSON();
    return route.fulfill({ json: { affected: 199 } });
  });

  await page.goto("/triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();

  // Ctrl/Cmd+A selects all matching
  await page.keyboard.press("Control+a");

  // Should show 200 selected (all matching, no exclusions yet)
  await expect(page.getByText("200 selected")).toBeVisible();

  // Deselect row 1 (exclusion)
  await page.locator('[data-entry-id="1"] [role="checkbox"]').click();

  // Should show 199 selected
  await expect(page.getByText("199 selected")).toBeVisible();

  // Set status to read
  await chooseOption(
    page,
    page.getByRole("combobox", { name: "Set status for selected" }),
    "Read",
  );

  // The bulk body should use filter + exclusions, not entry_ids
  await expect
    .poll(() => bulkBody)
    .toMatchObject({
      filter: { status: ["unsorted"] },
      excluded_entry_ids: [1],
      set: { status: "read" },
    });
});

test("triage j/k navigation moves focus between rows", async ({ page }) => {
  const entries = makeEntries(5);
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: 5,
        facets: { status_counts: { unsorted: 5 } },
      },
    }),
  );

  await page.goto("/triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();

  // Focus first row and press j to move down
  await page.locator('[data-entry-id="1"]').focus();
  await expect(page.locator('[data-entry-id="1"]')).toBeFocused();
  await page.keyboard.press("j");

  // Focus should move to row 2
  await expect(page.locator('[data-entry-id="2"]')).toBeFocused({
    timeout: 8000,
  });

  // Press k to move up
  await page.keyboard.press("k");
  await expect(page.locator('[data-entry-id="1"]')).toBeFocused({
    timeout: 8000,
  });
});

test("triage hundreds of rows without per-row requests", async ({ page }) => {
  const entries = makeEntries(200);
  let bulkCallCount = 0;
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: 200,
        facets: { status_counts: { unsorted: 200 } },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkCallCount += 1;
    return route.fulfill({ json: { affected: 200 } });
  });

  await page.goto("/triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();

  // Ctrl+A to select all, then set status via keyboard
  await page.keyboard.press("Control+a");
  await expect(page.getByText("200 selected")).toBeVisible();

  // Press "r" to set all to read — one bulk request, not 200
  await page.keyboard.press("r");

  await expect(page.getByText("200 entries updated")).toBeVisible();
  expect(bulkCallCount).toBe(1);
});
