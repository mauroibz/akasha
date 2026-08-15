import { ALLOW_CONSOLE_ERRORS, expect, test } from "./console";
import { seedLibrary } from "./seed";

/**
 * What the application does when something breaks.
 *
 * The route-level code split (DEC-037) introduced a failure mode that did not
 * exist before: a navigation can now fail because a chunk did not arrive. On a
 * LAN box behind a proxy that is not hypothetical, and the answer must be a
 * page that says so and offers a way out — not a blank screen.
 */

test(
  "a route whose code fails to load shows the fallback, not a blank page",
  { annotation: { type: ALLOW_CONSOLE_ERRORS } },
  async ({ page }) => {
    await seedLibrary(page);
    // The dev server serves each lazy route as its own module request; in a
    // built deployment this is the hashed chunk. Either way the browser is
    // asking for code that does not arrive.
    await page.route("**/TriagePage.tsx*", (route) => route.abort());
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Seeded book 0003" }),
    ).toBeVisible();

    await page.getByRole("link", { name: "Triage", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: /went wrong/i }),
    ).toBeVisible();

    // And the way out is a normal navigation, because the boundary is keyed on
    // the route. Before that it stayed on screen over every later page.
    await page.getByRole("link", { name: "Library", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Seeded book 0003" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /went wrong/i }),
    ).toHaveCount(0);
  },
);

test("a failed library load says so and can be retried", async ({ page }) => {
  // Driven by a flag rather than a request counter: the page legitimately
  // issues more than one request on mount (the URL-sync effect re-keys the
  // query), so "fail only the first" would have healed itself before the
  // reader ever saw the error.
  let healthy = false;
  let attempts = 0;
  await page.route("**/api/entries?**", async (route) => {
    attempts += 1;
    if (!healthy) return route.fulfill({ status: 503, body: "upstream down" });
    return route.fulfill({
      json: {
        items: [],
        next_cursor: null,
        total: 0,
        facets: { status_counts: {}, format_counts: {} },
      },
    });
  });

  await page.goto("/");
  const failure = page.getByRole("alert");
  await expect(failure).toContainText(/could not be loaded/i);

  const before = attempts;
  healthy = true;
  // An error state that cannot be left is a dead end.
  await failure.getByRole("button", { name: /try again/i }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(attempts).toBeGreaterThan(before);
});

test("a degraded provider is named on the add screen", async ({ page }) => {
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/health/providers", (route) =>
    route.fulfill({
      json: {
        degraded: true,
        providers: [
          { name: "openlibrary", available: true, reason: null },
          {
            name: "googlebooks",
            available: false,
            reason: "no API key configured",
          },
        ],
      },
    }),
  );
  await page.goto("/add");
  const notice = page
    .getByRole("status")
    .filter({ hasText: /fewer providers/i });
  await expect(notice).toBeVisible();
  // Naming the provider and the reason is the difference between a warning and
  // a shrug.
  await expect(notice).toContainText("googlebooks");
  await expect(notice).toContainText("no API key configured");
  await expect(notice).toContainText(/add a book manually/i);
});

test("library to detail and back is possible without a pointer", async ({
  page,
}) => {
  await seedLibrary(page);
  await page.route("**/api/entries/3", (route) =>
    route.fulfill({
      json: {
        id: 3,
        item_id: 3,
        status: "read",
        score: 4,
        notes: null,
        date_added: "2026-07-22T00:00:00Z",
        date_started: null,
        date_finished: null,
        reread_count: 0,
        score_provisional: true,
        suggested_status: null,
        item: {
          id: 3,
          type: "book",
          title: "Seeded book 0003",
          subtitle: null,
          year: 1903,
          creator: "Author 3",
          cover_path: null,
          cover_url: null,
          metadata: {},
          identifiers: {},
          sources: [],
        },
        shelves: [],
        formats: [],
      },
    }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();

  await page.locator("[data-entry-id='3']").focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/books/3");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();

  // Back out the way a keyboard user would: tab to the first link on the page
  // and activate it. If that link is not reachable, this flow is a trap.
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  await page
    .getByRole("link", { name: /library/i })
    .first()
    .focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();
});
