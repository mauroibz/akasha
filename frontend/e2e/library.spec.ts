import { expect, test } from "@playwright/test";

function entry(id: number) {
  return {
    id,
    item_id: id,
    status: "read",
    score: (id % 10) + 1,
    notes: null,
    date_added: "2026-07-22T00:00:00Z",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    score_provisional: id % 3 === 0,
    suggested_status: null,
    item: {
      id,
      type: "book",
      title: `Seeded book ${String(id).padStart(4, "0")}`,
      subtitle: null,
      year: 1900 + (id % 126),
      sort_author: `Author ${id % 200}`,
      cover_path: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    shelves: [],
  };
}

async function seedLibrary(page: import("@playwright/test").Page) {
  const items = Array.from({ length: 5000 }, (_, index) => entry(index + 1));
  await page.route("**/api/entries?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items,
        next_cursor: null,
        total: 5000,
        facets: { status_counts: { read: 5000, unsorted: 27 } },
      }),
    });
  });
}

test("the deterministic 5,000-entry library mounts only overscanned rows", async ({
  page,
}) => {
  await seedLibrary(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0001" }),
  ).toBeVisible();
  const library = page.getByRole("feed", { name: "Library" });
  expect(Number(await library.getAttribute("data-mounted-count"))).toBeLessThan(
    20,
  );
  await library.evaluate((element) => {
    element.scrollTop = 250_000;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect
    .poll(async () => Number(await library.getAttribute("data-mounted-count")))
    .toBeLessThan(20);
  expect(await page.locator("[data-entry-id]").count()).toBeLessThan(20);
});

test("keyboard guards and reduced motion remain effective", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await seedLibrary(page);
  await page.goto("/");
  await page.keyboard.press("/");
  await expect(
    page.getByRole("searchbox", { name: "Search library" }),
  ).toBeFocused();
  await page.keyboard.type("a");
  await expect(page).toHaveURL("/");
  await expect(
    page.getByRole("searchbox", { name: "Search library" }),
  ).toHaveValue("a");
  const duration = await page
    .locator("article")
    .first()
    .evaluate((element) => getComputedStyle(element).transitionDuration);
  expect(["0s", "0.00001s", "1e-05s"]).toContain(duration);
  await page.getByRole("feed", { name: "Library" }).focus();
  await page.keyboard.press("a");
  await expect(page).toHaveURL("/add");
});
