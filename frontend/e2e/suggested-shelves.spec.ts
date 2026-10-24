import { expect, test } from "./console";
import { stubSuggestions } from "./suggestions-fixture";

/** Suggested shelves (Sprint 119, DEC-176). */

test("a suggested shelf is made in one tap and joins the room", async ({
  page,
}) => {
  const posts: unknown[] = [];
  await stubSuggestions(page, posts);
  await page.goto("/shelves");
  const suggested = page.getByRole("region", { name: "Suggested shelves" });
  await suggested
    .getByRole("group", { name: "Ursula K. Le Guin" })
    .getByRole("button", { name: "Make this a shelf" })
    .click();
  await expect(
    suggested.getByRole("group", { name: "Ursula K. Le Guin" }),
  ).toHaveCount(0);
  await expect(page.getByText("Ursula K. Le Guin").first()).toBeVisible();
  expect(posts).toEqual([
    {
      url: "/api/shelves/suggestions/accept",
      body: { key: "creator:ursula k le guin" },
    },
  ]);
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("the suggestions scroll inside themselves", async ({ page }) => {
    await stubSuggestions(page);
    await page.goto("/shelves");
    await expect(
      page.getByRole("region", { name: "Suggested shelves" }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
  });
});
