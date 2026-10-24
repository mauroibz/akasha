import { stubReview } from "./diary-fixture";
import { expect, test } from "./console";

/** The year in review (Sprint 120, DEC-178). */

for (const size of [
  { name: "a desktop", width: 1280, height: 900 },
  { name: "a phone", width: 390, height: 800 },
]) {
  test(`on ${size.name} the year reads back in numbered sections`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: size.width, height: size.height });
    await stubReview(page);
    await page.goto("/diary/2025/review");
    await expect(
      page.getByRole("heading", { level: 1, name: "2025" }),
    ).toBeVisible();
    for (const name of [
      "The best of it",
      "How you rate",
      "Month by month",
      "What you changed your mind about",
      "In your words",
    ])
      await expect(page.getByRole("heading", { name })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(size.width);
  });
}
