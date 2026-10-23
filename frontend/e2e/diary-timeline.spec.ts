import { stubTimeline } from "./diary-fixture";
import { expect, test } from "./console";

/** The Diary across every year (Sprint 118, DEC-176). */

test("every year reads as one timeline, and earlier years load on asking", async ({
  page,
}) => {
  await stubTimeline(page);
  await page.goto("/diary");
  await page.getByRole("button", { name: "All years" }).click();
  const timeline = page.getByRole("list", { name: "Every year" });
  await expect(timeline.getByRole("heading", { name: "2026" })).toBeVisible();
  await expect(timeline).toContainText("7 → 9");
  await expect(timeline).toContainText("after a reread");
  await page.getByRole("button", { name: "Earlier" }).click();
  await expect(timeline.getByRole("heading", { name: "2019" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Earlier" })).toHaveCount(0);
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("the timeline fits without scrolling sideways", async ({ page }) => {
    await stubTimeline(page);
    await page.goto("/diary");
    await page.getByRole("button", { name: "All years" }).click();
    await expect(page.getByRole("list", { name: "Every year" })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
  });
});
