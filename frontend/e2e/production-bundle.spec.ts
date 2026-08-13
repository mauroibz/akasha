import { expect, test } from "./console";
import { seedLibrary } from "./seed";

/**
 * The production bundle, loaded the way a browser loads it.
 *
 * Everything else in this suite runs against the dev server, which serves
 * unbundled modules and therefore cannot fail the way a wrongly split bundle
 * fails. Sprint 017 split vendor code by naming packages, which left their
 * transitive runtime unassigned, put part of React in the wrong chunk and threw
 * `Cannot read properties of undefined (reading 'createContext')` before the
 * first render. Every gate was green and the deployed application was a blank
 * page (DEC-041).
 *
 * The console fixture already fails these on any page error, which is most of
 * the point; the assertions below are what proves the app got as far as
 * rendering. Behaviour belongs in the chromium project, which is faster.
 */
test.describe("production bundle", () => {
  test("the entry chunk boots and renders the library", async ({ page }) => {
    await seedLibrary(page, 3);
    await page.goto("/");

    await expect(page.getByRole("feed")).toBeVisible();
  });

  test("a lazily loaded route chunk initialises too", async ({ page }) => {
    await seedLibrary(page, 1);
    await page.goto("/");
    // Navigate rather than deep-link, so the chunk arrives after the entry has
    // already evaluated: that ordering is what a cyclic split breaks.
    await page.getByRole("link", { name: /add/i }).first().click();

    await expect(
      page.getByRole("searchbox", { name: /search books/i }),
    ).toBeVisible();
  });
});
