import AxeBuilder from "@axe-core/playwright";

import { expect, test } from "./console";
import { entry } from "./seed";

/**
 * Every day (Sprint 147, DEC-193): the Journal's first widget. A week or a month of
 * days; a tap on one asks what it was for, offering what is under way, and lights it.
 */

const reading = { ...entry(7), status: "reading" };

test.beforeEach(async ({ page }) => {
  // A fixed day, so the grid and the names of its days do not move.
  await page.clock.install({ time: new Date("2026-11-23T12:00:00") });
  await page.route("**/api/now", (route) => route.fulfill({ json: [reading] }));
});

test("a day is lit by hand for what was under way, from the keyboard", async ({
  page,
}) => {
  const lit: Array<{ day: string; entries: unknown[] }> = [];
  const puts: Array<{ day: string; body: { entry_ids: number[] } }> = [];
  await page.route("**/api/lit-days**", async (route) => {
    const request = route.request();
    if (request.method() === "PUT") {
      const day = new URL(request.url()).pathname.split("/").pop()!;
      const body = request.postDataJSON() as { entry_ids: number[] };
      puts.push({ day, body });
      lit.push({ day, entries: body.entry_ids.length ? [reading] : [] });
      return route.fulfill({ json: lit[lit.length - 1] });
    }
    return route.fulfill({ json: { days: lit } });
  });
  await page.goto("/journal");
  await expect(page.getByRole("tab", { name: "Every day" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  const grid = page.getByRole("list", { name: "0 days lit in November" });
  await expect(grid.getByRole("button")).toHaveCount(30);

  await grid
    .getByRole("button", { name: "Monday 23 November, not lit" })
    .focus();
  await page.keyboard.press("Enter");
  const question = page.getByRole("group", { name: "What was it for?" });
  await expect(question).toContainText("What was Monday 23 November for?");
  await question.getByRole("button", { name: reading.item.title }).focus();
  await page.keyboard.press("Space");
  await question.getByRole("button", { name: "Light it" }).focus();
  await page.keyboard.press("Enter");

  await expect(
    page.getByRole("button", {
      name: `Monday 23 November, lit for ${reading.item.title}`,
    }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("list", { name: "1 day lit in November" }),
  ).toBeVisible();
  expect(puts).toEqual([{ day: "2026-11-23", body: { entry_ids: [7] } }]);
});

for (const width of [390, 1440]) {
  test(`the widget has no serious axe violations and no overflow at ${width}px, asking and at rest`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/lit-days?**", (route) =>
      route.fulfill({
        json: {
          days: [
            { day: "2026-11-20", entries: [reading] },
            { day: "2026-11-21", entries: [] },
          ],
        },
      }),
    );
    await page.goto("/journal");
    await expect(
      page.getByRole("list", { name: "2 days lit in November" }),
    ).toBeVisible();
    const check = async () => {
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth -
            document.documentElement.clientWidth,
        ),
      ).toBe(0);
      const results = await new AxeBuilder({ page })
        .include('[aria-label="Something to do"]')
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(
        results.violations
          .filter((v) => v.impact === "serious" || v.impact === "critical")
          .map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`),
      ).toEqual([]);
    };
    await check();
    await page
      .getByRole("button", { name: "Monday 23 November, not lit" })
      .click();
    await expect(
      page.getByRole("group", { name: "What was it for?" }),
    ).toBeVisible();
    await check();
  });
}
