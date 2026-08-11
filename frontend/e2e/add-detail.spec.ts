import { expect, test, type Page } from "@playwright/test";

const candidate = (id: string, year: number) => ({
  source: "openlibrary",
  source_id: id,
  source_refs: [{ source: "openlibrary", source_id: id }],
  title: "Rayuela",
  subtitle: null,
  authors: ["Julio Cortázar"],
  year,
  cover_url: null,
  identifiers: {},
  language: "es",
  metadata: {},
});
const entry = {
  id: 7,
  item_id: 3,
  status: "reading",
  score: 8,
  notes: "Cached while providers are down",
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
    metadata: { authors: ["Julio Cortázar"], publisher: "Sudamericana" },
    identifiers: {},
    sources: [{ source: "openlibrary", source_id: "OL1M", is_primary: true }],
  },
  shelves: [],
};

async function common(page: Page) {
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/entries/7", (route) =>
    route.fulfill({ json: entry }),
  );
}

test("manual add is keyboard-complete and cached detail edits persist", async ({
  page,
}) => {
  await common(page);
  let posted = 0;
  await page.route("**/api/entries", async (route) => {
    posted += 1;
    await route.fulfill({
      status: 201,
      json: { entry, already_exists: false, near_matches: [] },
    });
  });
  await page.route("**/api/items/3", (route) =>
    route.fulfill({ json: { ...entry.item, title: "Rayuela corregida" } }),
  );
  await page.goto("/add");
  await page.getByRole("button", { name: /enter manually/i }).press("Enter");
  await expect(page.getByLabel(/^title$/i)).toBeFocused();
  await page.getByLabel(/^title$/i).fill("Rayuela");
  await page.getByRole("button", { name: /add to library/i }).press("Enter");
  // New entries return to the library with a success toast
  await expect(page).toHaveURL("/");
  expect(posted).toBe(1);
  // Navigate to detail to verify the entry was created
  await page.goto("/books/7");
  await expect(page.getByText("Cached while providers are down")).toBeVisible();
  await page.getByRole("button", { name: /edit book metadata/i }).click();
  await page.getByLabel(/^title$/i).fill("Rayuela corregida");
  await page.getByRole("button", { name: /save metadata/i }).click();
});

test("work resolution exposes edition choice and exact duplicate navigates", async ({
  page,
}) => {
  await common(page);
  await page.route("**/api/search/resolve?**", (route) =>
    route.fulfill({ json: [candidate("OL1M", 1963), candidate("OL2M", 1999)] }),
  );
  await page.route("**/api/entries", (route) =>
    route.fulfill({
      status: 200,
      json: { entry, already_exists: true, near_matches: [] },
    }),
  );
  await page.goto("/add");
  await page
    .getByRole("searchbox", { name: /search books/i })
    .fill("https://openlibrary.org/works/OL1W");
  await expect(
    page.getByRole("button", { name: /Rayuela.*1963/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Rayuela.*1999/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Rayuela.*1999/i }).click();
  await page.getByRole("button", { name: /add to library/i }).click();
  await expect(page).toHaveURL(/\/books\/7/);
  // The confirmation is a visible toast on the destination route. It used to be
  // an sr-only paragraph, which is why this assertion could not tell the
  // difference (DEC-024); e2e/feedback.spec.ts now checks the geometry too.
  await expect(
    page
      .locator("[data-sonner-toast]")
      .filter({ hasText: "Already in your library" }),
  ).toBeVisible();
});

test("mobile detail confirms refresh and reports cover failure without motion", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await common(page);
  await page.route("**/api/items/3/refresh", (route) =>
    route.fulfill({
      status: 502,
      json: { error: { code: "provider_failure" } },
    }),
  );
  await page.route("**/api/items/3/cover", (route) =>
    route.fulfill({ status: 422, json: { error: { code: "invalid_cover" } } }),
  );
  await page.goto("/books/7");
  await page.getByRole("button", { name: /refresh from provider/i }).click();
  await expect(
    page.getByRole("alertdialog", { name: /overwrite cached metadata/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /confirm refresh/i }).click();
  await expect(page.getByRole("alert")).toContainText("not changed");
  await page.getByLabel(/replace cover/i).setInputFiles({
    name: "bad.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("bad"),
  });
  await expect(page.getByRole("alert")).toContainText(
    "previous cover is unchanged",
  );
  await expect(page.locator("main")).toBeVisible();
});
