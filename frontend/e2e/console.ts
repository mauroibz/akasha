import { test as base, expect } from "@playwright/test";

import { bookItemType } from "./seed";

/**
 * Every test in this suite fails if the page logged an error or threw.
 *
 * This is Sprint 017's fourth acceptance criterion, and it is a fixture rather
 * than an assertion in each spec because the errors worth catching are the ones
 * nobody thought to look for: a React warning about a key, a rejected promise
 * in an effect, a chunk that failed to load after the routes were split. Those
 * appear in the console of a test that otherwise passes.
 *
 * A test that deliberately provokes an error opts out by annotating itself:
 *
 *     test("...", { annotation: { type: ALLOW_CONSOLE_ERRORS } }, async () => {})
 */
export const ALLOW_CONSOLE_ERRORS = "allow-console-errors";

export const test = base.extend<{
  failOnConsoleErrors: void;
  stubCommonEndpoints: void;
}>({
  // `/api/item-types` and `/api/shelves` are fetched by nearly every screen
  // (the domain chooser, shelf pickers) and no spec exercises either one
  // failing. ci.yml's e2e job runs no backend, so an unstubbed call here is
  // always a real ECONNREFUSED — wasted retries competing for CPU with the
  // browser under test on a runner with far less headroom than a dev
  // workstation, which is exactly what turned into cross-spec flakiness.
  // Registered before the test body runs, so it still yields to whatever a
  // test stubs itself: Playwright resolves overlapping routes most-recently-
  // registered first, and `stubItemTypes(page, [...])` or a test's own
  // `page.route("**/api/shelves", ...)` is always registered after this one.
  stubCommonEndpoints: [
    async ({ page }, use) => {
      await page.route("**/api/item-types", (route) =>
        route.fulfill({ json: [bookItemType] }),
      );
      await page.route("**/api/shelves", (route) =>
        route.fulfill({ json: [] }),
      );
      await use();
    },
    { auto: true },
  ],
  failOnConsoleErrors: [
    async ({ page }, use, testInfo) => {
      const problems: string[] = [];
      page.on("console", (message) => {
        if (message.type() !== "error") return;
        // A 4xx/5xx the application handles is reported by the browser as a
        // resource error and is not the application misbehaving. Only the
        // page's own console errors count.
        const text = message.text();
        if (text.startsWith("Failed to load resource")) return;
        problems.push(`console.error: ${text}`);
      });
      page.on("pageerror", (error) => {
        problems.push(`pageerror: ${error.message}`);
      });

      await use();

      if (
        testInfo.annotations.some(
          (annotation) => annotation.type === ALLOW_CONSOLE_ERRORS,
        )
      ) {
        return;
      }
      expect(problems, problems.join("\n")).toEqual([]);
    },
    { auto: true },
  ],
});

export { expect } from "@playwright/test";
