import { expect, test } from "./console";
import { bookItemType, stubItemTypes } from "./seed";

/**
 * The shelves room (Sprint 105, DEC-169): covers on a ledge that open when you
 * reach for them, and stay shut where motion is unwelcome.
 */

const preview = [
  ["Rayuela", 1963, 10],
  ["Ficciones", 1944, 9],
  ["Pedro Páramo", 1955, 8],
  ["Aura", 1962, null],
].map(([title, year, score], index) => ({
  entry_id: 10 + index,
  title,
  year,
  score,
  cover_url: null,
}));

async function stubRoom(page: import("@playwright/test").Page) {
  await stubItemTypes(page, [
    { ...bookItemType, plural_label: "Books" },
  ] as Parameters<typeof stubItemTypes>[1]);
  await page.route("**/api/shelves", (route) =>
    route.fulfill({
      json: [
        {
          id: 1,
          name: "Latin American",
          slug: "latin-american",
          updated_at: "2026-10-01T00:00:00Z",
          entry_count: 12,
          covers: [],
          members_by_type: { book: 12 },
          preview,
          finished_count: 9,
          mean_score: 8.6,
        },
        {
          id: 2,
          name: "Walkthrough",
          slug: "walkthrough",
          updated_at: "2026-10-01T00:00:00Z",
          entry_count: 0,
          covers: [],
          members_by_type: {},
          preview: [],
          finished_count: 0,
          mean_score: null,
        },
      ],
    }),
  );
}

const front = (page: import("@playwright/test").Page) =>
  page.locator("[data-cover-front]").first();
const turned = (page: import("@playwright/test").Page) =>
  front(page).evaluate((node) => getComputedStyle(node).transform);

test("a cover opens when reached for, by pointer or keyboard", async ({
  page,
}) => {
  await stubRoom(page);
  await page.goto("/shelves");
  const cover = page.getByRole("link", { name: "Rayuela, 1963, scored 10" });
  await expect(cover).toBeVisible();
  expect(await turned(page)).toBe("none");

  await cover.hover();
  await expect.poll(() => turned(page)).not.toBe("none");

  await page.mouse.move(0, 0);
  await expect.poll(() => turned(page)).toBe("none");
  await cover.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  await expect.poll(() => turned(page)).not.toBe("none");
});

test("with reduced motion, a cover stays shut and still links", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await stubRoom(page);
  await page.goto("/shelves");
  const cover = page.getByRole("link", { name: "Rayuela, 1963, scored 10" });
  await cover.hover();
  await page.waitForTimeout(500);
  expect(await turned(page)).toBe("none");
  await expect(cover).toHaveAttribute("href", "/books/10");
});

test("the room fits a phone, nothing scrolling sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stubRoom(page);
  await page.goto("/shelves");
  await expect(
    page.getByRole("link", { name: "Latin American", exact: true }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  // Two covers stand on a phone's ledge; the rest are a link away.
  await expect(page.locator("[data-opening-cover]:visible")).toHaveCount(2);
  await expect(page.getByRole("link", { name: /All 12/ })).toBeVisible();
});
