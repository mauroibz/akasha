import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { seedLibrary } from "./seed";

/**
 * Automated WCAG 2.1 A/AA checks on every screen a user can reach.
 *
 * These gate CI alongside the layout regressions, for the reason in DEC-025:
 * an unenforced check is a check that stops being true. axe only sees what it
 * can compute from the rendered tree, so it is half the acceptance criterion —
 * the keyboard and focus half is walked by hand each sprint and recorded in the
 * worklog.
 *
 * Only `serious` and `critical` violations fail. `moderate` and `minor` are
 * printed, so a real problem is visible without a rule-severity change in a
 * future axe release breaking an unrelated pull request.
 */

const detailEntry = {
  id: 7,
  item_id: 3,
  status: "reading",
  score: 8,
  notes: "Cached note",
  date_added: "2026-07-22",
  date_started: null,
  date_finished: null,
  reread_count: 0,
  score_provisional: false,
  suggested_status: null,
  item: {
    id: 3,
    type: "book",
    title: "Rayuela",
    subtitle: null,
    year: 1963,
    sort_author: "Julio Cortázar",
    cover_path: null,
    cover_url: null,
    metadata: {
      authors: ["Julio Cortázar"],
      publisher: "Sudamericana",
      language: "es",
      page_count: 736,
      subjects: ["Argentine fiction"],
      description: "A novel",
      original_year: 1963,
    },
    identifiers: { isbn13: "9788437604572" },
    sources: [{ source: "openlibrary", source_id: "OL1M", is_primary: true }],
  },
  shelves: [{ id: 1, name: "Favorites", slug: "favorites" }],
};

async function stubShelves(page: Page) {
  await page.route("**/api/shelves", (route) =>
    route.fulfill({
      json: [
        { id: 1, name: "Favorites", slug: "favorites", entry_count: 1 },
        { id: 2, name: "Pending", slug: "pending", entry_count: 4 },
      ],
    }),
  );
}

async function stubProviderHealth(page: Page, degraded = false) {
  await page.route("**/api/health/providers", (route) =>
    route.fulfill({
      json: {
        degraded,
        providers: [
          { name: "openlibrary", available: true, reason: null },
          {
            name: "googlebooks",
            available: !degraded,
            reason: degraded ? "no API key configured" : null,
          },
        ],
      },
    }),
  );
}

async function stubTriage(page: Page) {
  const entries = Array.from({ length: 30 }, (_, index) => ({
    id: index + 1,
    item_id: index + 1,
    status: "unsorted",
    score: index % 4 === 0 ? index % 10 : null,
    notes: null,
    date_added: "2026-01-01",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    score_provisional: index % 2 === 0,
    suggested_status:
      index % 3 === 0 ? "read" : index % 3 === 1 ? "to_read" : null,
    item: {
      id: index + 1,
      type: "book",
      title: `Book ${index + 1}`,
      subtitle: null,
      year: 2000 + (index % 50),
      sort_author: `Author ${index + 1}`,
      cover_url: null,
      metadata: { authors: [`Author ${index + 1}`] },
      identifiers: {},
      sources: [],
    },
    shelves: [],
  }));
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: { status_counts: { unsorted: entries.length } },
      },
    }),
  );
}

/**
 * Runs axe and fails on anything serious, naming the rule, its impact and the
 * element. A bare violation count tells whoever reads the failure nothing about
 * what to fix.
 */
async function expectNoSeriousViolations(page: Page, screen: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  const serious = results.violations.filter(
    (violation) =>
      violation.impact === "serious" || violation.impact === "critical",
  );
  const lesser = results.violations.filter(
    (violation) =>
      violation.impact !== "serious" && violation.impact !== "critical",
  );
  if (lesser.length) {
    console.log(
      `${screen}: ${lesser.length} non-blocking violation(s): ${lesser
        .map((violation) => `${violation.id} (${violation.impact})`)
        .join(", ")}`,
    );
  }

  // Asserted as compact strings rather than as the raw violation objects: a
  // failing diff of axe's node payloads is thousands of lines and tells the
  // reader less than one line naming the rule and the element.
  const summary = serious.map((violation) => {
    const targets = violation.nodes
      .slice(0, 3)
      .map((node) => node.target.join(" "))
      .join(" | ");
    return `${violation.id} [${violation.impact}] ${violation.help} -> ${targets}`;
  });
  expect(summary, screen).toEqual([]);
}

test("library in grid view has no serious accessibility violations", async ({
  page,
}) => {
  await seedLibrary(page);
  await stubShelves(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();
  await expectNoSeriousViolations(page, "library (grid)");
});

test("library in table view has no serious accessibility violations", async ({
  page,
}) => {
  await seedLibrary(page);
  await stubShelves(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Table view" }).click();
  await expect(page.getByRole("feed", { name: "Library" })).toBeVisible();
  await expectNoSeriousViolations(page, "library (table)");
});

test("the expanded score picker overlay is accessible inside its card", async ({
  page,
}) => {
  await seedLibrary(page);
  await stubShelves(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();
  // The compact picker is an overlay anchored inside a fixed-height card
  // (DEC-023). Auditing it open is required precisely because it may not be
  // repaired by portalling it out of the card.
  await page
    .getByRole("button", { name: /^Score for Seeded book 0003/ })
    .click();
  await expect(page.getByRole("button", { name: "Score 7" })).toBeVisible();
  await expectNoSeriousViolations(page, "library (score picker open)");
});

test("triage has no serious accessibility violations", async ({ page }) => {
  await stubTriage(page);
  await stubShelves(page);
  await page.goto("/triage");
  await expect(page.getByRole("heading", { name: /inbox/i })).toBeVisible();
  await expectNoSeriousViolations(page, "triage");
});

test("triage with a selection and its action bar has no serious violations", async ({
  page,
}) => {
  await stubTriage(page);
  await stubShelves(page);
  await page.goto("/triage");
  await expect(page.getByRole("heading", { name: /inbox/i })).toBeVisible();
  await page.getByRole("checkbox").nth(1).click();
  await expect(
    page.getByRole("combobox", { name: "Set status for selected" }),
  ).toBeVisible();
  await expectNoSeriousViolations(page, "triage (selection)");
});

test("detail has no serious accessibility violations", async ({ page }) => {
  await page.route("**/api/entries/7", (route) =>
    route.fulfill({ json: detailEntry }),
  );
  await stubShelves(page);
  await page.goto("/books/7");
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  await expectNoSeriousViolations(page, "detail");
});

test("the detail opinion dialog has no serious accessibility violations", async ({
  page,
}) => {
  await page.route("**/api/entries/7", (route) =>
    route.fulfill({ json: detailEntry }),
  );
  await stubShelves(page);
  await page.goto("/books/7");
  await page.getByRole("button", { name: /edit opinion/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expectNoSeriousViolations(page, "detail (opinion dialog)");
});

test("add has no serious accessibility violations", async ({ page }) => {
  await stubShelves(page);
  await stubProviderHealth(page);
  await page.goto("/add");
  await expect(
    page.getByRole("heading", { name: /add a book/i }),
  ).toBeVisible();
  await expectNoSeriousViolations(page, "add");
});

test("the add manual form has no serious accessibility violations", async ({
  page,
}) => {
  await stubShelves(page);
  await stubProviderHealth(page);
  // The manual escape hatch sits at the end of a result list, so the form is
  // only reachable once a search has come back.
  await page.route("**/api/search**", (route) => route.fulfill({ json: [] }));
  await page.goto("/add");
  await page.getByRole("searchbox", { name: "Search books" }).fill("rayuela");
  await page
    .getByRole("button", { name: /enter manually/i })
    .click({ timeout: 15_000 });
  await expect(page.getByLabel("Title", { exact: true })).toBeVisible();
  await expectNoSeriousViolations(page, "add (manual form)");
});

test("the degraded provider notice has no serious accessibility violations", async ({
  page,
}) => {
  await stubShelves(page);
  await stubProviderHealth(page, true);
  await page.goto("/add");
  await expect(page.getByText(/running on fewer providers/i)).toBeVisible();
  await expectNoSeriousViolations(page, "add (degraded providers)");
});

test("import has no serious accessibility violations", async ({ page }) => {
  await page.goto("/import");
  await expect(page.getByLabel(/goodreads csv/i)).toBeVisible();
  await expectNoSeriousViolations(page, "import");
});

test("shelves has no serious accessibility violations", async ({ page }) => {
  await stubShelves(page);
  await page.goto("/shelves");
  await expect(page.getByRole("heading", { name: /shelves/i })).toBeVisible();
  await expectNoSeriousViolations(page, "shelves");
});
