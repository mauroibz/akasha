import { expect, test } from "./console";

import { sampleAnimations } from "./motion";
import { chooseOption } from "./radix";
import { stubImporters, stubItemTypes } from "./seed";

// Triage lives on `/import` now (DEC-079), so the screen around it asks the
// registry which connectors exist.
test.beforeEach(async ({ page }) => {
  await stubImporters(page);
  await stubItemTypes(page);
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
});

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
      creator: `Author ${i + 1}`,
      cover_url: null,
      metadata: { creators: [`Author ${i + 1}`] },
      identifiers: {},
      sources: [],
    },
    shelves: [],
    formats: [],
  }));
  return entries;
}

test("a provisional score is marked and the marker is explained", async ({
  page,
}) => {
  // The walkthrough recorded this cell rendering as a bare "6·". A marker with
  // no legend is not a marker; it reads as a typo.
  const entries = makeEntries(6).map((entry, index) => ({
    ...entry,
    score: 6,
    score_provisional: index === 0,
  }));
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: {
          status_counts: { unsorted: entries.length },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.goto("/import?tab=triage");
  await expect(page.getByRole("heading", { name: /inbox/i })).toBeVisible();

  const marked = page.locator("[data-entry-id='1'][data-provisional='true']");
  await expect(marked).toHaveCount(1);
  await expect(marked).toContainText("6*");
  // Screen readers get the word, not the glyph.
  await expect(
    marked.getByRole("combobox", { name: /score for book 1/i }),
  ).toHaveAccessibleName(/provisional/i);
  await expect(
    page.getByText(/converted from an imported rating/i),
  ).toBeVisible();

  // A row that is not provisional carries neither the glyph nor the word.
  const plain = page.locator("[data-entry-id='2']");
  await expect(plain).not.toContainText("6*");

  // The score is a filled chip here exactly as it is on a library card: one
  // ramp, one treatment, whichever screen the eye lands on (DEC-026). Asserted
  // as painted colour rather than as a class name, because the class only
  // matters if Tailwind emitted it.
  const chip = plain.getByRole("combobox", { name: /score for book 2:/i });
  // Amber, the 4-6 band -- not the lime of 7-8.
  await expect(chip).toHaveCSS("background-color", "rgb(251, 189, 35)");
  await expect(chip).toHaveCSS("color", "rgb(9, 9, 11)");
});

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
        facets: {
          status_counts: { unsorted: 30 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/accept-suggested", (route) =>
    route.fulfill({ json: { affected: 20 } }),
  );

  await page.goto("/import?tab=triage");
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
        facets: {
          status_counts: { unsorted: 5 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkBody = route.request().postDataJSON();
    return route.fulfill({ json: { affected: 1 } });
  });

  await page.goto("/import?tab=triage");
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

test("row controls edit one entry while only checkboxes select for bulk", async ({
  page,
}) => {
  const entries = makeEntries(3);
  const writes: unknown[] = [];
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: {
          status_counts: { unsorted: entries.length },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/1", (route) => {
    const changes = route.request().postDataJSON() as Partial<
      (typeof entries)[number]
    >;
    writes.push(route.request().postDataJSON());
    return route.fulfill({ json: { ...entries[0], ...changes } });
  });

  await page.goto("/import?tab=triage");
  const row = page.locator('[data-entry-id="1"]');
  await expect(row).toBeVisible();

  await row
    .getByRole("combobox", { name: /score for book 1: unscored/i })
    .selectOption("7");
  await row
    .getByRole("combobox", { name: "Status for Book 1" })
    .selectOption("read");

  await expect.poll(() => writes).toEqual([{ score: 7 }, { status: "read" }]);
  await expect(page.getByRole("toolbar", { name: "Bulk actions" })).toHaveCount(
    0,
  );

  await row.getByRole("checkbox", { name: "Select Book 1" }).click();
  await expect(
    page.getByRole("toolbar", { name: "Bulk actions" }),
  ).toBeVisible();
});

test("a failed row edit restores the previous score once", async ({ page }) => {
  const entries = makeEntries(2);
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: {
          status_counts: { unsorted: entries.length },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/1", (route) =>
    route.fulfill({ status: 500, json: { detail: "write failed" } }),
  );

  await page.goto("/import?tab=triage");
  const score = page
    .locator('[data-entry-id="1"]')
    .getByRole("combobox", { name: /score for book 1/i });
  await score.selectOption("7");

  await expect(
    page.getByText("Your change could not be saved", { exact: true }),
  ).toHaveCount(1);
  await expect(score).toHaveAccessibleName("Score for Book 1: unscored");
});

test("clicking a triage row opens it instead of selecting it", async ({
  page,
}) => {
  const entries = makeEntries(2);
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: {
          status_counts: { unsorted: entries.length },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );

  await page.goto("/import?tab=triage");
  await page.getByText("Book 1", { exact: true }).click();

  await expect(page).toHaveURL(/\/books\/1$/);
  await expect(page.getByRole("toolbar", { name: "Bulk actions" })).toHaveCount(
    0,
  );
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
        facets: {
          status_counts: { unsorted: 10 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkBody = route.request().postDataJSON();
    return route.fulfill({ json: { affected: 3 } });
  });

  await page.goto("/import?tab=triage");
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
        facets: {
          status_counts: { unsorted: 200 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkBody = route.request().postDataJSON();
    return route.fulfill({ json: { affected: 199 } });
  });

  await page.goto("/import?tab=triage");
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
        facets: {
          status_counts: { unsorted: 5 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );

  await page.goto("/import?tab=triage");
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
        facets: {
          status_counts: { unsorted: 200 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkCallCount += 1;
    return route.fulfill({ json: { affected: 200 } });
  });

  await page.goto("/import?tab=triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();

  // Ctrl+A to select all, then set status via keyboard
  await page.keyboard.press("Control+a");
  await expect(page.getByText("200 selected")).toBeVisible();

  // Press "r" to set all to read — one bulk request, not 200
  await page.keyboard.press("r");

  await expect(page.getByText("200 entries updated")).toBeVisible();
  expect(bulkCallCount).toBe(1);
});

test("the bulk action bar enters without animating a single row", async ({
  page,
}) => {
  const entries = makeEntries(12);
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: 12,
        facets: {
          status_counts: { unsorted: 12 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.goto("/import?tab=triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();

  const samples = await sampleAnimations(page, async () => {
    await page.locator('[data-entry-id="1"] [role="checkbox"]').click();
    await expect(
      page.getByRole("toolbar", { name: "Bulk actions" }),
    ).toBeVisible();
  });
  // Triage is the other virtualized list. Same rule, same proof: the bar is a
  // surface that does not scroll, the rows underneath it are not.
  const rowLevel = samples.filter(
    (sample) => sample.target === "row" || sample.target === "card",
  );
  expect(rowLevel, JSON.stringify(rowLevel.slice(0, 5))).toEqual([]);
});

test("digits score the focused row and Enter opens it", async ({ page }) => {
  // The MAL-style rhythm from product spec section 7: move, score, commit,
  // advance. `j`/`k` and the status letters were already covered; the digits
  // and Enter were not.
  const entries = makeEntries(5);
  const bulkBodies: unknown[] = [];
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: 5,
        facets: {
          status_counts: { unsorted: 5 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkBodies.push(route.request().postDataJSON());
    return route.fulfill({ json: { affected: 1 } });
  });
  await page.route("**/api/entries/2", (route) =>
    route.fulfill({ json: { ...entries[1], item: entries[1].item } }),
  );

  await page.goto("/import?tab=triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();
  await page.locator('[data-entry-id="1"]').focus();

  await page.keyboard.press("8");
  await expect
    .poll(() => bulkBodies.at(-1))
    .toEqual({ entry_ids: [1], set: { score: 8 } });

  // `0` is ten, and only in score context.
  await page.keyboard.press("0");
  await expect
    .poll(() => bulkBodies.at(-1))
    .toEqual({ entry_ids: [1], set: { score: 10 } });

  // With nothing selected, Enter opens the focused row rather than advancing.
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/books/1");
});

test("triage animates its action bar but not under reduced motion", async ({
  page,
}) => {
  // DEC-033: a reduced-motion assertion only means something paired with a
  // positive one. Sprint 016 proved this for the library; triage is the other
  // surface with an entering element.
  const entries = makeEntries(8);
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: 8,
        facets: {
          status_counts: { unsorted: 8 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );

  await page.goto("/import?tab=triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();
  const moving = await sampleAnimations(page, async () => {
    await page.locator('[data-entry-id="1"]').getByRole("checkbox").click();
    await expect(
      page.getByRole("combobox", { name: "Set status for selected" }),
    ).toBeVisible();
  });
  expect(
    moving.some((sample) => sample.duration > 0.01),
    JSON.stringify(moving.slice(0, 5)),
  ).toBe(true);

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();
  const still = await sampleAnimations(page, async () => {
    await page.locator('[data-entry-id="1"]').getByRole("checkbox").click();
    await expect(
      page.getByRole("combobox", { name: "Set status for selected" }),
    ).toBeVisible();
  });
  const long = still.filter((sample) => sample.duration > 0.01);
  expect(long, JSON.stringify(long.slice(0, 5))).toEqual([]);
});

test("triage puts a selection on a shelf in bulk", async ({ page }) => {
  // Listed in product spec section 7 as `Set status · Add shelves · Set score ·
  // Clear provisional` and never built: `add_shelves` existed on the bulk endpoint
  // and was tested, but no control ever sent it.
  const entries = makeEntries(10);
  let bulkBody: unknown = null;
  await page.route("**/api/shelves", (route) =>
    route.fulfill({
      json: [
        { id: 4, name: "Argentina", slug: "argentina", entry_count: 12 },
        { id: 7, name: "Ensayo", slug: "ensayo", entry_count: 3 },
      ],
    }),
  );
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: 10,
        facets: {
          status_counts: { unsorted: 10 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/bulk", (route) => {
    bulkBody = route.request().postDataJSON();
    return route.fulfill({ json: { affected: 2 } });
  });

  await page.goto("/import?tab=triage");
  await expect(page.getByText("Book 1", { exact: true })).toBeVisible();
  await page.locator('[data-entry-id="1"] [role="checkbox"]').click();
  await page.locator('[data-entry-id="2"] [role="checkbox"]').click();
  await expect(page.getByText("2 selected")).toBeVisible();

  await chooseOption(
    page,
    page.getByRole("combobox", { name: "Add selected to a shelf" }),
    "Ensayo",
  );

  await expect
    .poll(() => bulkBody)
    .toEqual({
      entry_ids: [1, 2],
      set: { add_shelves: [7] },
    });
  await expect(page.getByText("2 entries updated")).toBeVisible();
});

test("the retired /triage address still lands on the folded tab", async ({
  page,
}) => {
  // It was a top-level nav item for thirty sprints, so it is in bookmarks and
  // in history. Folding the screen is not a reason to break those (DEC-079).
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: makeEntries(3),
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

  await page.goto("/triage");

  await expect(page).toHaveURL(/\/import\?tab=triage/);
  await expect(page.getByRole("tab", { name: /triage/i })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("3 unsorted")).toBeVisible();
});

test("the import screen reaches triage and comes back without leaving", async ({
  page,
}) => {
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: makeEntries(2),
        next_cursor: null,
        total: 2,
        facets: {
          status_counts: { unsorted: 2 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );

  await page.goto("/import");
  await expect(page.getByRole("tab", { name: "Goodreads" })).toBeVisible();
  await page.getByRole("tab", { name: /triage/i }).click();
  await expect(page.getByText("2 unsorted")).toBeVisible();
  await page.getByRole("tab", { name: /import/i }).click();
  await page.getByRole("tab", { name: "Calibre" }).click();
  // Calibre leads with the folder chooser; the mount is its alternate (DEC-081).
  await expect(
    page.getByLabel("Calibre folder", { exact: true }),
  ).toBeVisible();
});
