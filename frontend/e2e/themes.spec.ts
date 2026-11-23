import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

import { expect, test } from "./console";
import { seedLibrary } from "./seed";

/**
 * The theme presets (Sprint 148, DEC-193): each is on the page before it paints,
 * and the Library and the Journal have no serious axe violation in any of them.
 */

async function serious(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`);
}

for (const theme of ["moss", "claret", "dusk", "sakura"]) {
  test(`${theme}: set before first paint, and the Library and the Journal pass axe`, async ({
    page,
  }) => {
    await page.addInitScript(
      (value) => localStorage.setItem("akasha:theme", value),
      theme,
    );
    await seedLibrary(page, 24);
    // Read as the document is first parsed: the pre-paint script has run by then.
    await page.addInitScript(() => {
      document.addEventListener("DOMContentLoaded", () => {
        (window as unknown as { themeAtParse?: string }).themeAtParse =
          document.documentElement.dataset.theme;
      });
    });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Seeded book 0003" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => (window as unknown as { themeAtParse?: string }).themeAtParse,
      ),
    ).toBe(theme);
    expect(await serious(page)).toEqual([]);

    await page.goto("/journal");
    await expect(page.getByRole("tab", { name: "Every day" })).toBeVisible();
    await expect(page.getByRole("list", { name: /lit in/ })).toBeVisible();
    expect(await serious(page)).toEqual([]);
  });
}

test("a preset is chosen from Settings and survives a reload", async ({
  page,
}) => {
  await page.goto("/settings");
  await page.getByRole("radio", { name: /^Dusk/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dusk");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dusk");
  await expect(page.getByRole("radio", { name: /^Dusk/ })).toBeChecked();
});
