import { expect, test } from "./console";
import { stubDiaryWithGoal } from "./goal-fixture";

/**
 * The goal leads the Diary (Sprint 127, DEC-179): without one, an invitation set in one
 * tap; with one, slots the year's covers fill. At a phone's width.
 */

test.use({ viewport: { width: 390, height: 844 } });

test("no goal: one tap sets one from the invitation", async ({ page }) => {
  await stubDiaryWithGoal(page, []);
  let put: unknown = null;
  await page.route("**/api/goals/book", async (route) => {
    put = route.request().postDataJSON();
    await route.fulfill({
      json: { item_type: "book", count: 6, period: "year", suggest: true },
    });
  });
  await page.goto("/diary");
  const invite = page.getByRole("region", {
    name: "Want something to aim at this year?",
  });
  await expect(invite).toContainText("You've finished 2 books in");
  await invite.getByRole("button", { name: /^6/ }).click();
  await invite.getByRole("button", { name: "Aim for 6" }).click();
  await expect
    .poll(() => put)
    .toEqual({
      count: 6,
      period: "year",
      suggest: true,
    });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
});

test("a goal: slots fill with the year's covers, in order", async ({
  page,
}) => {
  await stubDiaryWithGoal(page);
  await page.goto("/diary");
  const slots = page.getByRole("list", { name: /2 of 24 books in/ });
  await expect(slots).toBeVisible();
  await expect(slots.locator('[data-slot="filled"] a').first()).toHaveAttribute(
    "aria-label",
    "Rayuela",
  );
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
});
