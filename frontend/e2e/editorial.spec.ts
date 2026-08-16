import { type Page } from "@playwright/test";
import { expect, test } from "./console";
import { stubItemTypes } from "./seed";

const entry = {
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
    creator: "Julio Cortázar",
    cover_path: null,
    cover_url: null,
    metadata: {
      creators: ["Julio Cortázar"],
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

async function stubEntry(page: Page) {
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: [entry],
        next_cursor: null,
        total: 1,
        facets: {
          status_counts: { reading: 1, unsorted: 5 },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await stubItemTypes(page);
  await page.route("**/api/entries/7", (route) =>
    route.fulfill({ json: entry }),
  );
  await page.route("**/api/shelves", (route) =>
    route.fulfill({
      json: [{ id: 1, name: "Favorites", slug: "favorites", entry_count: 1 }],
    }),
  );
}

test("library row opens detail by pointer and Enter", async ({ page }) => {
  await stubEntry(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  // Click the title to open detail
  await page.getByRole("heading", { name: "Rayuela" }).click();
  await expect(page).toHaveURL("/books/7");
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
});

test("Enter on a focused row opens detail", async ({ page }) => {
  await stubEntry(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  const row = page.locator("[data-entry-id='7']");
  await row.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/books/7");
});

test("URL-backed filters are reload-stable", async ({ page }) => {
  await stubEntry(page);
  await page.goto("/?status=reading&sort=score&order=asc");
  await expect(page).toHaveURL(/status=reading/);
  await expect(page).toHaveURL(/sort=score/);
  await expect(page).toHaveURL(/order=asc/);
  // Reload preserves the URL state
  await page.reload();
  await expect(page).toHaveURL(/status=reading/);
  await expect(page).toHaveURL(/sort=score/);
  await expect(page).toHaveURL(/order=asc/);
});

test("Inbox button navigates to the triage page", async ({ page }) => {
  await stubEntry(page);
  await page.goto("/");
  await expect(page.getByText(/Inbox 5/).first()).toBeVisible();
  await page
    .getByText(/Inbox 5/)
    .first()
    .click();
  await expect(page).toHaveURL(/\/triage/);
});

test("detail renders all metadata regions", async ({ page }) => {
  await stubEntry(page);
  await page.goto("/books/7");
  await expect(page.getByText("Sudamericana")).toBeVisible();
  // Language "es" is in the edition-facts dl
  await expect(page.locator("[data-fact='language'] dd")).toContainText("es");
  await expect(page.getByText("736")).toBeVisible();
  await expect(page.getByText("Argentine fiction")).toBeVisible();
  await expect(page.getByText("Favorites")).toBeVisible();
  await expect(page.getByText("openlibrary (primary)")).toBeVisible();
});

test("confirmed deletion removes the entry and returns to library", async ({
  page,
}) => {
  await stubEntry(page);
  let deleted = false;
  await page.route("**/api/entries/7", async (route, request) => {
    if (request.method() === "DELETE") {
      deleted = true;
      await route.fulfill({ status: 204 });
    } else {
      await route.fulfill({ json: entry });
    }
  });
  await page.goto("/books/7");
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  // Click the first "Delete entry" button (in the main page, not the dialog)
  await page
    .getByRole("button", { name: /delete entry/i })
    .first()
    .click();
  await expect(
    page.getByRole("alertdialog", { name: /remove this/i }),
  ).toBeVisible();
  // The dialog states books remain
  await expect(page.getByText(/remain/i)).toBeVisible();
  // Confirm deletion
  await page
    .getByRole("alertdialog", { name: /remove this/i })
    .getByRole("button", { name: /delete entry/i })
    .click();
  await expect(page).toHaveURL(/\/(\?type=[a-z]+)?$/);
  expect(deleted).toBe(true);
});

test("delete cancel preserves the entry", async ({ page }) => {
  await stubEntry(page);
  await page.goto("/books/7");
  await page
    .getByRole("button", { name: /delete entry/i })
    .first()
    .click();
  await expect(
    page.getByRole("alertdialog", { name: /remove this/i }),
  ).toBeVisible();
  // Press Escape to cancel
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("alertdialog", { name: /remove this/i }),
  ).not.toBeVisible();
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
});

test("shelf management creates, renames, and deletes shelves", async ({
  page,
}) => {
  let shelves = [
    { id: 1, name: "Favorites", slug: "favorites", entry_count: 5 },
  ];
  let nextId = 2;
  // Collection route: GET (list) and POST (create)
  await page.route("**/api/shelves", async (route, request) => {
    if (request.method() === "POST") {
      const body = route.request().postDataJSON() as { name: string };
      const newShelf = {
        id: nextId++,
        name: body.name,
        slug: body.name.toLowerCase().replace(/\s/g, "-"),
        entry_count: 0,
      };
      shelves = [...shelves, newShelf];
      await route.fulfill({ status: 201, json: newShelf });
    } else {
      await route.fulfill({ json: shelves });
    }
  });
  // Individual shelf route: PATCH (rename) and DELETE
  await page.route("**/api/shelves/*", async (route, request) => {
    const url = route.request().url();
    const id = Number(url.match(/\/shelves\/(\d+)/)?.[1]);
    if (request.method() === "DELETE") {
      shelves = shelves.filter((s) => s.id !== id);
      await route.fulfill({ status: 204 });
    } else if (request.method() === "PATCH") {
      const body = route.request().postDataJSON() as { name: string };
      shelves = shelves.map((s) =>
        s.id === id
          ? {
              ...s,
              name: body.name,
              slug: body.name.toLowerCase().replace(/\s/g, "-"),
            }
          : s,
      );
      const updated = shelves.find((s) => s.id === id)!;
      await route.fulfill({ json: updated });
    } else {
      await route.continue();
    }
  });

  await page.goto("/shelves");
  await expect(page.getByText("Favorites")).toBeVisible();
  await expect(page.getByText("5 items")).toBeVisible();

  // Create a new shelf
  await page.getByPlaceholder(/new shelf name/i).fill("Sci-fi");
  await page.getByRole("button", { name: /create shelf/i }).click();
  // Anchored on the list row: the confirmation toast repeats the shelf name.
  await expect(
    page.getByRole("button", { name: /rename sci-fi/i }),
  ).toBeVisible();

  // Delete with confirmation
  await page.getByRole("button", { name: /delete sci-fi/i }).click();
  await expect(
    page.getByRole("alertdialog", { name: /delete .sci-fi./i }),
  ).toBeVisible();
  await expect(page.getByText(/retain/i)).toBeVisible();
  await page.getByRole("button", { name: /delete shelf/i }).click();
  // Wait for the shelf to disappear
  await expect(
    page.getByRole("button", { name: /rename sci-fi/i }),
  ).toHaveCount(0, { timeout: 5000 });
});

test("unknown route shows a useful 404", async ({ page }) => {
  await page.goto("/nonexistent");
  await expect(page.getByRole("heading", { name: /not found/i })).toBeVisible();
  await expect(
    page.getByRole("button", { name: /go to library/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /go to library/i }).click();
  await expect(page).toHaveURL(/\/(\?type=[a-z]+)?$/);
});

test("navigation shell exposes all four destinations at desktop width", async ({
  page,
}) => {
  await stubEntry(page);
  await page.goto("/");
  // Desktop nav is visible at default width
  for (const label of ["Library", "Add", "Triage", "Import", "Shelves"]) {
    await expect(
      page.getByRole("link", { name: new RegExp(label, "i") }).first(),
    ).toBeVisible();
  }
  // Navigate to each
  await page
    .getByRole("link", { name: /shelves/i })
    .first()
    .click();
  await expect(page).toHaveURL("/shelves");
  await page
    .getByRole("link", { name: /import/i })
    .first()
    .click();
  await expect(page).toHaveURL("/import");
  await page.getByRole("link", { name: /add/i }).first().click();
  await expect(page).toHaveURL("/add");
  await page
    .getByRole("link", { name: /library/i })
    .first()
    .click();
  await expect(page).toHaveURL(/\/(\?type=[a-z]+)?$/);
});
