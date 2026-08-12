import { type Page } from "@playwright/test";
import { expect, test } from "./console";

import { stillDurations } from "./motion";

/**
 * Product spec section 4.3 and technical spec section 8 require that every user
 * action produces *visible* feedback, and that an accessible live region is a
 * complement to it rather than a substitute.
 *
 * Before Sprint 015 every confirmation in this app was rendered into a
 * `<p className="sr-only" aria-live="assertive">`. The e2e suite passed anyway,
 * because Playwright's `toBeVisible()` accepts an `sr-only` element: it is
 * clipped to a 1x1 box, not `display: none`. That is how DEC-024 was allowed to
 * happen, so every assertion here checks the rendered geometry as well.
 */
async function expectVisibleToast(page: Page, text: string | RegExp) {
  const toast = page.locator("[data-sonner-toast]").filter({ hasText: text });
  await expect(toast).toBeVisible();
  const viewport = page.viewportSize()!;
  // Polled, because the toast slides in: the first frame is legitimately still
  // outside the viewport. What matters is where it comes to rest.
  await expect
    .poll(async () => {
      const box = await toast.boundingBox();
      if (!box) return null;
      return {
        // An sr-only element measures 1x1. A real toast cannot.
        wideEnough: box.width > 120,
        tallEnough: box.height > 24,
        // And it must come to rest inside the viewport, not clipped off-screen.
        onScreen:
          box.x >= 0 &&
          box.y >= 0 &&
          box.x + box.width <= viewport.width + 1 &&
          box.y + box.height <= viewport.height + 1,
      };
    })
    .toEqual({ wideEnough: true, tallEnough: true, onScreen: true });
  return toast;
}

const entry = {
  id: 7,
  item_id: 3,
  status: "reading",
  score: 8,
  notes: null,
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
    cover_url: null,
    cover_path: null,
    metadata: {},
    identifiers: {},
    sources: [],
  },
  shelves: [],
};

const emptyLibrary = {
  items: [],
  next_cursor: null,
  total: 0,
  facets: { status_counts: {} },
};

async function stubLibrary(page: Page) {
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({ json: emptyLibrary }),
  );
  await page.route("**/api/entries/7", (route) =>
    route.fulfill({ json: entry }),
  );
  await page.route("**/api/health/providers", (route) =>
    route.fulfill({ json: { degraded: false, providers: [] } }),
  );
}

const widths = [
  { name: "375px", width: 375, height: 740 },
  { name: "1440px", width: 1440, height: 900 },
];

for (const size of widths) {
  test.describe(`visible feedback at ${size.name}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: size.width, height: size.height });
    });

    test("adding a book confirms on the toast surface", async ({ page }) => {
      await stubLibrary(page);
      await page.route("**/api/shelves", (route) =>
        route.fulfill({ json: [] }),
      );
      await page.route("**/api/entries", (route) =>
        route.fulfill({
          status: 201,
          json: { entry, already_exists: false, near_matches: [] },
        }),
      );
      await page.goto("/add");
      await page.getByRole("button", { name: /enter manually/i }).click();
      await page.getByLabel(/^title$/i).fill("Rayuela");
      await page.getByRole("button", { name: /add to library/i }).click();
      await expect(page).toHaveURL("/");
      await expectVisibleToast(page, "Book added");
    });

    test("adding a duplicate says so instead of failing silently", async ({
      page,
    }) => {
      await stubLibrary(page);
      await page.route("**/api/shelves", (route) =>
        route.fulfill({ json: [] }),
      );
      await page.route("**/api/entries", (route) =>
        route.fulfill({
          status: 200,
          json: { entry, already_exists: true, near_matches: [] },
        }),
      );
      await page.goto("/add");
      await page.getByRole("button", { name: /enter manually/i }).click();
      await page.getByLabel(/^title$/i).fill("Rayuela");
      await page.getByRole("button", { name: /add to library/i }).click();
      await expect(page).toHaveURL(/\/books\/7/);
      await expectVisibleToast(page, "Already in your library");
    });

    test("deleting an entry confirms on the toast surface", async ({
      page,
    }) => {
      await stubLibrary(page);
      await page.route("**/api/shelves", (route) =>
        route.fulfill({ json: [] }),
      );
      await page.route("**/api/entries/7", async (route) => {
        if (route.request().method() === "DELETE")
          return route.fulfill({ status: 204, body: "" });
        return route.fulfill({ json: entry });
      });
      await page.goto("/books/7");
      await page
        .getByRole("button", { name: /delete entry/i })
        .first()
        .click();
      await page
        .getByRole("alertdialog", { name: /remove this book/i })
        .getByRole("button", { name: /delete entry/i })
        .click();
      await expect(page).toHaveURL("/");
      await expectVisibleToast(page, "Book removed from your library");
    });

    test("renaming a shelf confirms on the toast surface", async ({ page }) => {
      let renamed = false;
      await page.route("**/api/shelves/1", (route) => {
        renamed = true;
        return route.fulfill({
          json: { id: 1, name: "Best", slug: "best", entry_count: 5 },
        });
      });
      await page.route("**/api/shelves", (route) =>
        route.fulfill({
          json: renamed
            ? [{ id: 1, name: "Best", slug: "best", entry_count: 5 }]
            : [{ id: 1, name: "Favorites", slug: "favorites", entry_count: 5 }],
        }),
      );
      await page.goto("/shelves");
      await page.getByRole("button", { name: /rename favorites/i }).click();
      await page
        .getByRole("textbox", { name: /new name for favorites/i })
        .fill("Best");
      await page.getByRole("button", { name: /^save$/i }).click();
      await expectVisibleToast(page, 'Shelf renamed to "Best"');
    });

    test("committing an import confirms on the toast surface", async ({
      page,
    }) => {
      await page.route("**/api/import/goodreads/preview", (route) =>
        route.fulfill({
          json: {
            batch_id: "batch-1",
            fingerprint: "abc",
            state: "previewed",
            summary: { total: 1, ready: 1, ambiguous: 0, errors: 0 },
            records: [
              {
                record_id: 1,
                row_number: 2,
                title: "Rayuela",
                authors: ["Julio Cortázar"],
                score: null,
                score_provisional: false,
                suggested_status: "read",
                planned_action: "create_item",
                candidates: [],
                errors: [],
                cover_staged: false,
              },
            ],
          },
        }),
      );
      await page.route("**/api/import/goodreads/commit", (route) =>
        route.fulfill({
          json: {
            batch_id: "batch-1",
            state: "committed",
            created_entries: 1,
            unchanged_entries: 0,
            created_items: 1,
          },
        }),
      );
      await page.goto("/import");
      await page.getByLabel(/goodreads csv/i).setInputFiles({
        name: "goodreads.csv",
        mimeType: "text/csv",
        buffer: Buffer.from("Title,Author\nRayuela,Julio Cortázar\n"),
      });
      await page.getByRole("button", { name: /preview import/i }).click();
      await page.getByRole("button", { name: /^Import 1 ready row$/ }).click();
      await expectVisibleToast(page, /Import complete: 1 book added/);
    });
  });
}

/**
 * The failure path, which this file has never covered. A confirmation that is
 * only ever tested when the write succeeds is half a feedback layer.
 */
test.describe("a rejected write", () => {
  async function stubOneEntryLibrary(page: Page) {
    await page.route("**/api/entries?**", (route) =>
      route.fulfill({
        json: {
          items: [entry],
          next_cursor: null,
          total: 1,
          facets: { status_counts: { reading: 1 } },
        },
      }),
    );
    await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
    await page.route("**/api/entries/7", async (route) => {
      if (route.request().method() !== "PATCH") return route.fallback();
      await route.fulfill({ status: 500, json: { error: { message: "no" } } });
    });
  }

  test("rolls the row back, shakes it, and says so on the toast surface", async ({
    page,
  }) => {
    await stubOneEntryLibrary(page);
    await page.goto("/");
    const row = page.locator("[data-entry-id='7']");
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: /score/i }).click();
    await page.getByRole("button", { name: "Score 3", exact: true }).click();

    await expectVisibleToast(page, /could not be saved/);
    await expect(row).toHaveAttribute("data-rollback", "true");
    const shake = await row.evaluate((element) => {
      const style = getComputedStyle(element);
      return { name: style.animationName, duration: style.animationDuration };
    });
    expect(shake.name).not.toBe("none");
    expect(shake.duration).toBe("0.32s");
    // The user's input is never silently lost: the prior score is what the
    // control reads once the write has failed.
    await expect(row.getByRole("button", { name: /score.*8/i })).toBeVisible();
  });

  test("shakes nothing when the reader asked for less motion", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await stubOneEntryLibrary(page);
    await page.goto("/");
    const row = page.locator("[data-entry-id='7']");
    await row.getByRole("button", { name: /score/i }).click();
    await page.getByRole("button", { name: "Score 3", exact: true }).click();

    // The failure is still reported and the marker is still set; only the
    // movement is gone.
    await expectVisibleToast(page, /could not be saved/);
    await expect(row).toHaveAttribute("data-rollback", "true");
    const duration = await row.evaluate(
      (element) => getComputedStyle(element).animationDuration,
    );
    expect(stillDurations).toContain(duration);
  });
});
